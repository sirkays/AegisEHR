from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import AccessRequest, ConsentPermission
from records.models import MedicalRecord
from accounts.models import PatientProfile, ProviderProfile
from blockchain.services import AlgorandService
from audit.models import AuditEvent

@login_required
def consent_management(request):
    if not request.user.is_patient_user() and not request.user.is_superuser:
        messages.warning(request, "Consent management is reserved for patient data owners.")
        return redirect('provider_dashboard')

    patient = getattr(request.user, 'patient_profile', None)
    if not patient:
        patient, _ = PatientProfile.objects.get_or_create(user=request.user)

    pending_requests = AccessRequest.objects.filter(
        patient=patient,
        status=AccessRequest.STATUS_PENDING
    ).select_related('provider__user', 'record').order_by('-created_at')

    active_permissions = ConsentPermission.objects.filter(
        patient=patient,
        is_revoked=False,
        expires_at__gt=timezone.now()
    ).select_related('provider__user', 'record').order_by('-granted_at')

    revoked_or_expired = ConsentPermission.objects.filter(
        patient=patient
    ).exclude(
        is_revoked=False,
        expires_at__gt=timezone.now()
    ).select_related('provider__user', 'record').order_by('-granted_at')

    context = {
        'patient': patient,
        'pending_requests': pending_requests,
        'active_permissions': active_permissions,
        'revoked_or_expired': revoked_or_expired,
    }
    return render(request, 'consent/consent_management.html', context)


@login_required
def create_access_request(request):
    provider = getattr(request.user, 'provider_profile', None)
    if not provider or not provider.is_verified:
        messages.error(request, "Only verified healthcare practitioners can request access to patient records.")
        return redirect('provider_dashboard')

    if request.method == 'POST':
        record_id = request.POST.get('record_id')
        purpose = request.POST.get('clinical_purpose', '').strip()
        duration_days = int(request.POST.get('duration_days', 7))

        record = get_object_or_404(MedicalRecord, record_id=record_id)
        
        # Prevent duplicate pending requests
        existing_req = AccessRequest.objects.filter(
            provider=provider,
            record=record,
            status=AccessRequest.STATUS_PENDING
        ).first()

        if existing_req:
            messages.info(request, "An active access request for this record is already awaiting patient review.")
            return redirect('provider_dashboard')

        req = AccessRequest.objects.create(
            patient=record.patient,
            provider=provider,
            record=record,
            clinical_purpose=purpose,
            requested_duration_days=duration_days
        )

        AuditEvent.log(
            event_type='access_requested',
            description=f"Provider Dr. {request.user.get_full_name()} requested access to '{record.title}' (Purpose: {purpose[:50]}...)",
            actor=request.user,
            record=record,
            is_on_chain=False,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )

        messages.success(request, f"Access request dispatched to Patient {record.patient.patient_code} for review.")
        return redirect('provider_dashboard')

    return redirect('provider_dashboard')


@login_required
def approve_request(request, request_id):
    patient = getattr(request.user, 'patient_profile', None)
    if not patient and not request.user.is_superuser:
        messages.error(request, "Unauthorized.")
        return redirect('dashboard_redirect')

    access_req = get_object_or_404(AccessRequest, request_id=request_id)
    if not request.user.is_superuser and access_req.patient != patient:
        messages.error(request, "You can only manage consent for your own health records.")
        return redirect('consent_management')

    expires_at = timezone.now() + timedelta(days=access_req.requested_duration_days)

    # 1. Commit Consent Grant on Algorand Smart Contract
    patient_addr = access_req.patient.user.algorand_address or "ALGO_PAT_ADDRESS"
    provider_addr = access_req.provider.user.algorand_address or "ALGO_PRV_ADDRESS"

    tx_receipt = AlgorandService.grant_consent_on_chain(
        record_id_str=str(access_req.record.record_id),
        patient_address=patient_addr,
        provider_address=provider_addr,
        expiry_timestamp=expires_at
    )

    # 2. Update Access Request & Create Permission Record
    access_req.status = AccessRequest.STATUS_APPROVED
    access_req.decision_at = timezone.now()
    access_req.save()

    permission = ConsentPermission.objects.create(
        request=access_req,
        patient=access_req.patient,
        provider=access_req.provider,
        record=access_req.record,
        expires_at=expires_at,
        algorand_grant_tx_id=tx_receipt['tx_id'],
        algorand_grant_round=tx_receipt['confirmation_round']
    )

    # 3. Log Immutable Audit Record
    AuditEvent.log(
        event_type='consent_granted',
        description=f"Patient {patient.patient_code} granted scoped access to Dr. {access_req.provider.user.get_full_name()} (Expires: {expires_at.strftime('%Y-%m-%d')})",
        actor=request.user,
        record=access_req.record,
        is_on_chain=True,
        tx_id=tx_receipt['tx_id'],
        round_num=tx_receipt['confirmation_round'],
        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
    )

    messages.success(request, f"Access approved! Consent transaction anchored on Algorand Ledger (TxID: {tx_receipt['tx_id'][:12]}...)")
    return redirect('consent_management')


@login_required
def reject_request(request, request_id):
    patient = getattr(request.user, 'patient_profile', None)
    access_req = get_object_or_404(AccessRequest, request_id=request_id)
    if not request.user.is_superuser and access_req.patient != patient:
        messages.error(request, "Unauthorized.")
        return redirect('consent_management')

    access_req.status = AccessRequest.STATUS_REJECTED
    access_req.decision_at = timezone.now()
    access_req.save()

    AuditEvent.log(
        event_type='system_operational',
        description=f"Patient {patient.patient_code} declined access request from Dr. {access_req.provider.user.get_full_name()}",
        actor=request.user,
        record=access_req.record,
        is_on_chain=False,
        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
    )

    messages.info(request, "Access request has been rejected.")
    return redirect('consent_management')


@login_required
def revoke_permission(request, permission_id):
    patient = getattr(request.user, 'patient_profile', None)
    perm = get_object_or_404(ConsentPermission, permission_id=permission_id)
    if not request.user.is_superuser and perm.patient != patient:
        messages.error(request, "Unauthorized.")
        return redirect('consent_management')

    # 1. Commit prospective revocation on Algorand Smart Contract
    patient_addr = perm.patient.user.algorand_address or "ALGO_PAT_ADDRESS"
    provider_addr = perm.provider.user.algorand_address or "ALGO_PRV_ADDRESS"

    tx_receipt = AlgorandService.revoke_consent_on_chain(
        record_id_str=str(perm.record.record_id),
        patient_address=patient_addr,
        provider_address=provider_addr
    )

    # 2. Update permission in application database
    perm.revoke(tx_id=tx_receipt['tx_id'], round_num=tx_receipt['confirmation_round'])

    # 3. Log on-chain audit event
    AuditEvent.log(
        event_type='consent_revoked',
        description=f"Consent REVOKED for Dr. {perm.provider.user.get_full_name()} regarding record '{perm.record.title}'",
        actor=request.user,
        record=perm.record,
        is_on_chain=True,
        tx_id=tx_receipt['tx_id'],
        round_num=tx_receipt['confirmation_round'],
        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
    )

    messages.warning(request, f"Permission REVOKED immediately. Revocation transaction confirmed on Algorand Ledger (TxID: {tx_receipt['tx_id'][:12]}...)")
    return redirect('consent_management')
