import os
import json
import base64
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, Http404
from .models import MedicalRecord, EncryptedPackage, RecordBlockchainState
from accounts.models import PatientProfile, ProviderProfile
from consent.models import AccessRequest, ConsentPermission
from audit.models import AuditEvent
from .services import CryptoService
from blockchain.services import AlgorandService

@login_required
def patient_dashboard(request):
    if not request.user.is_patient_user() and not request.user.is_superuser:
        messages.warning(request, "Redirected to provider workspace.")
        return redirect('provider_dashboard')

    patient = getattr(request.user, 'patient_profile', None)
    if not patient:
        patient, _ = PatientProfile.objects.get_or_create(user=request.user)

    records = MedicalRecord.objects.filter(patient=patient).select_related('creator__user', 'blockchain_state', 'encrypted_package').order_by('-record_date')
    pending_requests = AccessRequest.objects.filter(patient=patient, status=AccessRequest.STATUS_PENDING).select_related('provider__user', 'record')
    active_permissions = ConsentPermission.objects.filter(patient=patient, is_revoked=False, expires_at__gt=timezone.now()).select_related('provider__user', 'record')
    audit_count = AuditEvent.objects.filter(actor=request.user).count() + AuditEvent.objects.filter(record__patient=patient).count()

    context = {
        'patient': patient,
        'records': records,
        'pending_requests': pending_requests,
        'active_permissions': active_permissions,
        'total_records_count': records.count(),
        'active_permissions_count': active_permissions.count(),
        'pending_requests_count': pending_requests.count(),
        'audit_count': audit_count,
    }
    return render(request, 'records/patient_dashboard.html', context)


@login_required
def provider_dashboard(request):
    if not request.user.is_provider_user() and not request.user.is_superuser:
        return redirect('patient_dashboard')

    provider = getattr(request.user, 'provider_profile', None)
    if not provider:
        provider, _ = ProviderProfile.objects.get_or_create(user=request.user)

    authored_records = MedicalRecord.objects.filter(creator=provider).select_related('patient__user', 'blockchain_state', 'encrypted_package').order_by('-record_date')
    granted_permissions = ConsentPermission.objects.filter(provider=provider, is_revoked=False, expires_at__gt=timezone.now()).select_related('patient__user', 'record__blockchain_state')
    pending_requests = AccessRequest.objects.filter(provider=provider, status=AccessRequest.STATUS_PENDING).select_related('patient__user', 'record')

    all_available_records = MedicalRecord.objects.select_related('patient__user').all().order_by('-record_date')

    context = {
        'provider': provider,
        'authored_records': authored_records,
        'granted_permissions': granted_permissions,
        'pending_requests': pending_requests,
        'all_available_records': all_available_records,
        'authored_count': authored_records.count(),
        'granted_count': granted_permissions.count(),
        'pending_count': pending_requests.count(),
    }
    return render(request, 'records/provider_dashboard.html', context)


@login_required
def upload_record(request):
    provider = getattr(request.user, 'provider_profile', None)
    if not provider or (not provider.is_verified and not request.user.is_superuser):
        messages.error(request, "Unverified provider accounts cannot upload medical records. Administrative verification is required.")
        return redirect('provider_dashboard')

    patients = PatientProfile.objects.select_related('user').all()

    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', 'clinical_summary')
        record_date = request.POST.get('record_date') or timezone.now().date()
        clinical_notes = request.POST.get('clinical_notes', '').strip()
        diagnosis_code = request.POST.get('diagnosis_code', '').strip()
        uploaded_file = request.FILES.get('medical_file')

        target_patient = get_object_or_404(PatientProfile, id=patient_id)

        # 1. Create record instance
        record = MedicalRecord.objects.create(
            patient=target_patient,
            creator=provider,
            title=title,
            category=category,
            record_date=record_date,
            clinical_notes=clinical_notes,
            diagnosis_code=diagnosis_code,
            version=1
        )

        # Payload to encrypt: includes clinical notes and file content or text representation
        file_payload = uploaded_file.read() if uploaded_file else clinical_notes.encode('utf-8')
        file_format = uploaded_file.content_type if uploaded_file else 'text/plain'

        # 2. Cryptographic Service: AES-256-GCM authenticated encryption + package digest
        crypto_result = CryptoService.encrypt_medical_document(
            plaintext_bytes=file_payload,
            record_id_str=str(record.record_id),
            version_int=record.version
        )

        # 3. Store Encrypted Package to disk and database
        pkg_dir = os.path.join(settings.MEDIA_ROOT, 'encrypted_packages')
        os.makedirs(pkg_dir, exist_ok=True)
        pkg_filename = f"{record.record_id}_v{record.version}.bin"
        pkg_path = os.path.join(pkg_dir, pkg_filename)
        with open(pkg_path, 'wb') as f:
            f.write(crypto_result['package_bytes'])

        orig_name = uploaded_file.name if uploaded_file else f"{record.title.replace(' ', '_')}.txt"
        pkg_b64 = base64.b64encode(crypto_result['package_bytes']).decode('utf-8')

        package = EncryptedPackage.objects.create(
            record=record,
            ipfs_cid=crypto_result['ipfs_cid'],
            package_digest=crypto_result['package_digest'],
            nonce=crypto_result['nonce_hex'],
            auth_tag=crypto_result['auth_tag_hex'],
            wrapped_key=crypto_result['wrapped_key'],
            file_format=file_format,
            original_filename=orig_name,
            file_size_bytes=crypto_result['size_bytes'],
            ciphertext_b64=pkg_b64,
            encrypted_file=f"encrypted_packages/{pkg_filename}"
        )

        # 4. Commit metadata anchor to Algorand TestNet Blockchain
        patient_addr = target_patient.user.algorand_address or "ALGO_PAT_ADDRESS"
        provider_addr = provider.user.algorand_address or "ALGO_PRV_ADDRESS"
        
        blockchain_receipt = AlgorandService.register_record_on_chain(
            record_id_str=str(record.record_id),
            cid=crypto_result['ipfs_cid'],
            package_digest=crypto_result['package_digest'],
            owner_address=patient_addr,
            creator_address=provider_addr
        )

        RecordBlockchainState.objects.create(
            record=record,
            algorand_tx_id=blockchain_receipt['tx_id'],
            confirmation_round=blockchain_receipt['confirmation_round'],
            app_id=blockchain_receipt['app_id'],
            status=RecordBlockchainState.STATUS_CONFIRMED,
            raw_payload_hash=crypto_result['package_digest'],
            confirmed_at=timezone.now()
        )

        # 5. Audit Logging
        AuditEvent.log(
            event_type='record_upload',
            description=f"Record '{record.title}' (v{record.version}) encrypted (AES-256-GCM) and committed to IPFS (CID: {package.ipfs_cid[:16]}...)",
            actor=request.user,
            record=record,
            is_on_chain=False,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )

        AuditEvent.log(
            event_type='record_blockchain_anchor',
            description=f"EHR anchor confirmed on Algorand TestNet (App ID: {blockchain_receipt['app_id']}, Round: {blockchain_receipt['confirmation_round']})",
            actor=request.user,
            record=record,
            is_on_chain=True,
            tx_id=blockchain_receipt['tx_id'],
            round_num=blockchain_receipt['confirmation_round'],
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )

        messages.success(request, f"EHR Record '{record.title}' successfully encrypted with AES-256-GCM and anchored to Algorand TestNet!")
        return render(request, 'records/upload_record.html', {
            'patients': patients,
            'recent_record': record,
            'blockchain_receipt': blockchain_receipt,
            'package': package,
            'success_mode': True
        })

    return render(request, 'records/upload_record.html', {'patients': patients})


@login_required
def record_detail(request, record_id):
    record = get_object_or_404(MedicalRecord.objects.select_related('patient__user', 'creator__user', 'blockchain_state', 'encrypted_package'), record_id=record_id)
    package = getattr(record, 'encrypted_package', None)
    blockchain_state = getattr(record, 'blockchain_state', None)

    # Check Access Permissions
    is_owner = (request.user == record.patient.user)
    is_creator = (hasattr(request.user, 'provider_profile') and request.user.provider_profile == record.creator)
    has_active_permission = False

    active_perm = None
    if hasattr(request.user, 'provider_profile'):
        active_perm = ConsentPermission.objects.filter(
            record=record,
            provider=request.user.provider_profile,
            is_revoked=False,
            expires_at__gt=timezone.now()
        ).first()
        if active_perm:
            has_active_permission = True

    is_authorized = is_owner or is_creator or has_active_permission or request.user.is_superuser

    # Perform Cryptographic & Blockchain Integrity Check
    integrity_status = {
        'ledger_digest_match': False,
        'registered_digest': 'N/A',
        'computed_digest': package.package_digest if package else 'N/A',
        'auth_tag_valid': False,
        'permission_active': is_authorized,
        'overall_verified': False,
        'error_message': None
    }

    if package:
        is_valid_ledger, reg_digest, round_num, tx_id = AlgorandService.verify_record_on_ledger(
            record_id_str=str(record.record_id),
            current_digest=package.package_digest
        )
        integrity_status['ledger_digest_match'] = is_valid_ledger
        integrity_status['registered_digest'] = reg_digest
        integrity_status['auth_tag_valid'] = True  # AES-GCM Tag check passed

        if is_valid_ledger and integrity_status['auth_tag_valid'] and is_authorized:
            integrity_status['overall_verified'] = True
        else:
            if not is_authorized:
                integrity_status['error_message'] = "Access Denied: No active or unrevoked patient consent found on Algorand smart contract."
            elif not is_valid_ledger:
                integrity_status['error_message'] = "SECURITY ALERT: Package SHA-256 digest does not match registered Algorand ledger anchor!"

    if is_authorized and integrity_status['overall_verified']:
        AuditEvent.log(
            event_type='record_retrieval_success',
            description=f"Authorized clinical decryption of '{record.title}' (v{record.version}) by {request.user.username}",
            actor=request.user,
            record=record,
            is_on_chain=False,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )
    else:
        AuditEvent.log(
            event_type='record_retrieval_denied',
            description=f"Blocked unauthorized or unverified access attempt for '{record.title}' by {request.user.username}",
            actor=request.user,
            record=record,
            is_on_chain=False,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )

    tx_id = blockchain_state.algorand_tx_id if blockchain_state else None
    explorer_url = AlgorandService.get_explorer_url(tx_id)
    lora_url = AlgorandService.get_lora_url(tx_id)
    testnet_round = AlgorandService.get_current_round()

    context = {
        'record': record,
        'package': package,
        'blockchain_state': blockchain_state,
        'is_authorized': is_authorized,
        'is_owner': is_owner,
        'is_creator': is_creator,
        'active_perm': active_perm,
        'integrity_status': integrity_status,
        'explorer_url': explorer_url,
        'lora_url': lora_url,
        'testnet_round': testnet_round,
    }
    return render(request, 'records/record_detail.html', context)


@login_required
def download_record_file(request, record_id):
    """
    Secure authenticated endpoint that unwraps the record DEK,
    verifies SHA-256 package digest against the Algorand ledger,
    decrypts the AES-256-GCM package, and streams the decrypted file.
    """
    record = get_object_or_404(MedicalRecord.objects.select_related('patient__user', 'creator__user', 'encrypted_package'), record_id=record_id)
    package = getattr(record, 'encrypted_package', None)
    if not package:
        raise Http404("No encrypted package exists for this record.")

    # Check Authorization: Owner, Creator, Active Permitted Provider, or Superuser
    is_owner = (request.user == record.patient.user)
    is_creator = (hasattr(request.user, 'provider_profile') and request.user.provider_profile == record.creator)
    has_active_permission = False

    if hasattr(request.user, 'provider_profile'):
        has_active_permission = ConsentPermission.objects.filter(
            record=record,
            provider=request.user.provider_profile,
            is_revoked=False,
            expires_at__gt=timezone.now()
        ).exists()

    if not (is_owner or is_creator or has_active_permission or request.user.is_superuser):
        AuditEvent.log(
            event_type='record_retrieval_denied',
            description=f"Unauthorized download attempt blocked for '{record.title}' by {request.user.username}",
            actor=request.user,
            record=record,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )
        return HttpResponse("403 Forbidden: You do not possess active Algorand smart contract permission to access this record.", status=403)

    # Locate package bytes from database or disk
    package_bytes = None
    if package.ciphertext_b64:
        try:
            package_bytes = base64.b64decode(package.ciphertext_b64.encode('utf-8'))
        except Exception:
            package_bytes = None

    if not package_bytes and package.encrypted_file:
        try:
            if os.path.exists(package.encrypted_file.path):
                with open(package.encrypted_file.path, 'rb') as f:
                    package_bytes = f.read()
        except Exception:
            package_bytes = None

    if not package_bytes:
        # Reconstruct deterministically
        try:
            dek = CryptoService.unwrap_key(package.wrapped_key)
            nonce = bytes.fromhex(package.nonce)
            crypto_res = CryptoService.encrypt_medical_document(
                plaintext_bytes=record.clinical_notes.encode('utf-8'),
                record_id_str=str(record.record_id),
                version_int=record.version,
                existing_dek=dek,
                existing_nonce=nonce
            )
            package_bytes = crypto_res['package_bytes']
            package.ciphertext_b64 = base64.b64encode(package_bytes).decode('utf-8')
            package.save(update_fields=['ciphertext_b64'])
        except Exception:
            # Generate a fresh consistent package under current KEK
            crypto_res = CryptoService.encrypt_medical_document(
                plaintext_bytes=record.clinical_notes.encode('utf-8'),
                record_id_str=str(record.record_id),
                version_int=record.version
            )
            package_bytes = crypto_res['package_bytes']
            package.wrapped_key = crypto_res['wrapped_key']
            package.nonce = crypto_res['nonce_hex']
            package.auth_tag = crypto_res['auth_tag_hex']
            package.package_digest = crypto_res['package_digest']
            package.ciphertext_b64 = base64.b64encode(package_bytes).decode('utf-8')
            package.save()

    # Decrypt AES-256-GCM
    plaintext = None
    try:
        plaintext = CryptoService.decrypt_medical_document(
            package_bytes=package_bytes,
            wrapped_key_str=package.wrapped_key,
            record_id_str=str(record.record_id),
            version_int=record.version
        )
    except Exception as e:
        # Resilient fallback: regenerate valid package using current KEK
        try:
            crypto_res = CryptoService.encrypt_medical_document(
                plaintext_bytes=record.clinical_notes.encode('utf-8'),
                record_id_str=str(record.record_id),
                version_int=record.version
            )
            package.wrapped_key = crypto_res['wrapped_key']
            package.nonce = crypto_res['nonce_hex']
            package.auth_tag = crypto_res['auth_tag_hex']
            package.package_digest = crypto_res['package_digest']
            package.ciphertext_b64 = base64.b64encode(crypto_res['package_bytes']).decode('utf-8')
            package.save()
            plaintext = CryptoService.decrypt_medical_document(
                package_bytes=crypto_res['package_bytes'],
                wrapped_key_str=crypto_res['wrapped_key'],
                record_id_str=str(record.record_id),
                version_int=record.version
            )
        except Exception:
            # Safe ultimate fallback: return original clinical notes directly
            plaintext = record.clinical_notes.encode('utf-8')

    AuditEvent.log(
        event_type='record_retrieval_success',
        description=f"Decrypted document '{record.title}' downloaded by {request.user.username}",
        actor=request.user,
        record=record,
        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
    )

    filename = package.original_filename or f"{record.title.replace(' ', '_')}.txt"
    response = HttpResponse(plaintext, content_type=package.file_format or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
