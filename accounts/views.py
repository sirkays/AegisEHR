from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import User, PatientProfile, ProviderProfile
from blockchain.services import AlgorandService
from audit.models import AuditEvent

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            AuditEvent.log(
                event_type='system_operational',
                description=f"User session authenticated for {user.username} ({user.role})",
                actor=user,
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Invalid account credentials. Please verify your username and password.")

    return render(request, 'accounts/login.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        role = request.POST.get('role', 'patient')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        algorand_address = request.POST.get('algorand_address', '').strip()

        # Generate a wallet if the user didn't supply one
        if not algorand_address or not AlgorandService.is_valid_address(algorand_address):
            wallet = AlgorandService.generate_wallet()
            algorand_address = wallet['address']

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already registered. Please choose another username.")
            return render(request, 'accounts/register.html')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone_number=phone_number,
            algorand_address=algorand_address
        )

        if role == User.ROLE_PATIENT:
            blood_group = request.POST.get('blood_group', 'O+')
            gender = request.POST.get('gender', 'other')
            emergency_contact = request.POST.get('emergency_contact', '')
            dob = request.POST.get('date_of_birth') or None
            PatientProfile.objects.create(
                user=user,
                blood_group=blood_group,
                gender=gender,
                emergency_contact=emergency_contact,
                date_of_birth=dob
            )
        elif role == User.ROLE_PROVIDER:
            license_number = request.POST.get('license_number', f"LIC-{username.upper()}-2026")
            specialty = request.POST.get('specialty', 'General Practice')
            institution = request.POST.get('institution', 'St. Jude Clinical Center')
            ProviderProfile.objects.create(
                user=user,
                license_number=license_number,
                specialty=specialty,
                institution=institution,
                is_verified=False  # Requires Admin verification
            )

        AuditEvent.log(
            event_type='user_registration',
            description=f"New {role} registered: {user.username} with Algorand address {algorand_address[:12]}...",
            actor=user,
            is_on_chain=True,
            tx_id=AlgorandService._generate_txid(),
            round_num=AlgorandService.get_current_round(),
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )

        login(request, user)
        messages.success(request, f"Account registered successfully! Algorand identity {algorand_address[:8]}... linked.")
        return redirect('dashboard_redirect')

    return render(request, 'accounts/register.html')

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out securely.")
    return redirect('login')

@login_required
def dashboard_redirect(request):
    if request.user.is_admin_user():
        return redirect('admin_verification')
    elif request.user.is_provider_user():
        return redirect('provider_dashboard')
    else:
        return redirect('patient_dashboard')

@login_required
def admin_verification_view(request):
    if not request.user.is_admin_user():
        messages.error(request, "Restricted administrative zone. Provider or patient role not permitted.")
        return redirect('dashboard_redirect')

    providers = ProviderProfile.objects.select_related('user').all().order_by('-created_at')
    blockchain_status = AlgorandService.get_system_status()
    total_users = User.objects.count()
    verified_providers_count = ProviderProfile.objects.filter(is_verified=True).count()
    pending_providers_count = ProviderProfile.objects.filter(is_verified=False).count()

    context = {
        'providers': providers,
        'blockchain_status': blockchain_status,
        'total_users': total_users,
        'verified_providers_count': verified_providers_count,
        'pending_providers_count': pending_providers_count,
    }
    return render(request, 'accounts/admin_provider_verification.html', context)

@login_required
def toggle_provider_verification(request, provider_id):
    if not request.user.is_admin_user():
        messages.error(request, "Unauthorized operation.")
        return redirect('dashboard_redirect')

    provider = get_object_or_404(ProviderProfile, id=provider_id)
    if provider.is_verified:
        provider.revoke_verification()
        AuditEvent.log(
            event_type='provider_revocation',
            description=f"Administrative suspension of provider {provider.user.get_full_name()} (License: {provider.license_number})",
            actor=request.user,
            is_on_chain=True,
            tx_id=AlgorandService._generate_txid(),
            round_num=AlgorandService.get_current_round(),
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )
        messages.warning(request, f"Verification for Dr. {provider.user.get_full_name() or provider.user.username} revoked.")
    else:
        provider.verify(request.user)
        AuditEvent.log(
            event_type='provider_verification',
            description=f"Administrative credential approval for provider {provider.user.get_full_name()} (License: {provider.license_number})",
            actor=request.user,
            is_on_chain=True,
            tx_id=AlgorandService._generate_txid(),
            round_num=AlgorandService.get_current_round(),
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
        )
        messages.success(request, f"Dr. {provider.user.get_full_name() or provider.user.username} verified and granted clinical authorization.")

    return redirect('admin_verification')
