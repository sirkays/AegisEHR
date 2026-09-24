"""
Comprehensive End-to-End Test Suite for AegisEHR
Tests all critical workflows:
1. Patient Registration & Algorand Wallet generation
2. Provider Registration & Algorand Identity
3. Admin Provider Verification & Audit trail
4. Record Upload & AES-256-GCM authenticated encryption + Algorand anchor
5. Consent Access Request dispatch
6. Patient Consent Approval on Algorand
7. Clinician Authorized Decryption & File Download
8. Patient Revocation on Algorand & Subsequent Access Denied (403)
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr_portal.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from accounts.models import PatientProfile, ProviderProfile
from records.models import MedicalRecord, EncryptedPackage
from consent.models import AccessRequest, ConsentPermission
from audit.models import AuditEvent
from records.services import CryptoService
from blockchain.services import AlgorandService

User = get_user_model()

def run_tests():
    print("=" * 65)
    print("  RUNNING COMPREHENSIVE END-TO-END TEST SUITE")
    print("=" * 65)
    client = Client()

    # -------------------------------------------------------------
    # TEST 1: Patient Registration & Algorand Wallet Generation
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Patient Account Registration...")
    reg_username = "pat_charlie_test"
    # Clean up if exists
    User.objects.filter(username=reg_username).delete()

    response = client.post('/accounts/register/', {
        'username': reg_username,
        'email': 'charlie@test.org',
        'password': 'password123',
        'confirm_password': 'password123',
        'first_name': 'Charlie',
        'last_name': 'Brown',
        'role': 'patient',
        'blood_group': 'O+',
        'gender': 'Male',
        'emergency_contact': '+1 555-0199',
        'date_of_birth': '1990-05-15',
    }, follow=True)

    assert response.status_code == 200, f"Registration failed with code {response.status_code}"
    patient_user = User.objects.get(username=reg_username)
    assert patient_user.role == User.ROLE_PATIENT, "User role should be patient"
    assert AlgorandService.is_valid_address(patient_user.algorand_address), "Algorand address must be valid base32"
    assert hasattr(patient_user, 'patient_profile'), "Patient profile should be created"
    
    # Verify Audit Event
    reg_audit = AuditEvent.objects.filter(actor=patient_user, event_type='user_registration').first()
    assert reg_audit is not None, "Registration audit event not found"
    assert reg_audit.is_on_chain, "Registration audit should be marked on-chain"
    assert len(reg_audit.algorand_tx_id) == 52, f"Invalid TxID length: {reg_audit.algorand_tx_id}"
    print(f"  -> SUCCESS: Patient registered. Wallet: {patient_user.algorand_address[:12]}... TxID: {reg_audit.algorand_tx_id[:12]}...")

    # -------------------------------------------------------------
    # TEST 2: Provider Registration & Unverified State
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Healthcare Provider Registration...")
    doc_username = "dr_clark_test"
    User.objects.filter(username=doc_username).delete()

    client.logout()
    response = client.post('/accounts/register/', {
        'username': doc_username,
        'email': 'dr.clark@hospital.org',
        'password': 'password123',
        'confirm_password': 'password123',
        'first_name': 'Sarah',
        'last_name': 'Clark',
        'role': 'provider',
        'license_number': 'LIC-CLARK-9988',
        'specialty': 'Neurology',
        'institution': 'Metropolitan Neuro Clinic',
    }, follow=True)

    assert response.status_code == 200
    doc_user = User.objects.get(username=doc_username)
    assert doc_user.role == User.ROLE_PROVIDER
    assert hasattr(doc_user, 'provider_profile')
    assert doc_user.provider_profile.is_verified is False, "New provider must be unverified initially"
    print(f"  -> SUCCESS: Doctor registered. License: {doc_user.provider_profile.license_number} (Unverified)")

    # -------------------------------------------------------------
    # TEST 3: Admin Verifies Provider
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Administrative Provider Verification...")
    admin_user = User.objects.filter(role=User.ROLE_ADMIN).first()
    client.force_login(admin_user)

    verify_url = f"/admin/provider/{doc_user.provider_profile.id}/toggle/"
    toggle_resp = client.post(verify_url, follow=True)
    assert toggle_resp.status_code == 200

    doc_user.provider_profile.refresh_from_db()
    assert doc_user.provider_profile.is_verified is True, "Doctor should now be verified"
    
    verify_audit = AuditEvent.objects.filter(event_type='provider_verification').latest('timestamp')
    assert len(verify_audit.algorand_tx_id) == 52
    print(f"  -> SUCCESS: Provider verified by Admin. Blockchain Audit TxID: {verify_audit.algorand_tx_id[:12]}...")

    # -------------------------------------------------------------
    # TEST 4: Record Upload & AES-256-GCM Encryption + Algorand Anchor
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Clinical Record Upload & AES-256-GCM Encryption...")
    client.force_login(doc_user)
    
    upload_resp = client.post('/records/upload/', {
        'patient_id': patient_user.patient_profile.id,
        'title': 'Brain MRI Diagnostic Evaluation',
        'category': 'imaging',
        'record_date': '2026-09-24',
        'clinical_notes': 'Axial and sagittal T1/T2 weighted sequences demonstrate normal ventricular caliber with no intracranial abnormality.',
        'diagnosis_code': 'R51.9 - Unspecified Headache'
    }, follow=True)

    assert upload_resp.status_code == 200
    new_record = MedicalRecord.objects.filter(patient=patient_user.patient_profile, title='Brain MRI Diagnostic Evaluation').first()
    assert new_record is not None, "Medical record was not created"
    assert hasattr(new_record, 'encrypted_package'), "Encrypted package was not generated"
    assert hasattr(new_record, 'blockchain_state'), "Blockchain anchor state missing"
    
    pkg = new_record.encrypted_package
    assert len(pkg.package_digest) == 64, "Package digest must be SHA-256"
    assert len(pkg.nonce) == 24, "Nonce must be 96-bit (24 hex characters)"
    assert len(pkg.auth_tag) == 32, "Auth tag must be 128-bit (32 hex characters)"
    assert new_record.blockchain_state.status == 'confirmed', "Blockchain state must be confirmed"
    print(f"  -> SUCCESS: Record created. CID: {pkg.ipfs_cid[:16]}... Algorand TxID: {new_record.blockchain_state.algorand_tx_id[:12]}...")

    # -------------------------------------------------------------
    # TEST 5: Clinician Dispatches Consent Access Request
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Consent Access Request...")
    # Verified doc2 (dr_smith) requests access to Charlie's record
    doc_smith = User.objects.get(username='dr_smith')
    client.force_login(doc_smith)

    req_resp = client.post('/consent/request/create/', {
        'record_id': str(new_record.record_id),
        'clinical_purpose': 'Pre-operative neurological assessment and clearance',
        'requested_duration_days': 14
    }, follow=True)

    assert req_resp.status_code == 200
    access_req = AccessRequest.objects.filter(record=new_record, provider=doc_smith.provider_profile).first()
    assert access_req is not None, "Access request was not recorded"
    assert access_req.status == AccessRequest.STATUS_PENDING
    print(f"  -> SUCCESS: Access request created by Dr. Smith for {patient_user.username}'s record.")

    # -------------------------------------------------------------
    # TEST 6: Patient Approves Access Request on Algorand
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Patient Consent Approval & Smart Contract Signing...")
    client.force_login(patient_user)

    approve_resp = client.post(f'/consent/request/{access_req.request_id}/approve/', follow=True)
    assert approve_resp.status_code == 200
    
    access_req.refresh_from_db()
    assert access_req.status == AccessRequest.STATUS_APPROVED
    
    permission = ConsentPermission.objects.filter(request=access_req).first()
    assert permission is not None, "ConsentPermission object not found"
    assert permission.is_active is True
    assert len(permission.algorand_grant_tx_id) == 52, "Must have 52-char Algorand TxID"
    print(f"  -> SUCCESS: Consent granted. Smart Contract TxID: {permission.algorand_grant_tx_id[:12]}... Round: {permission.algorand_grant_round}")

    # -------------------------------------------------------------
    # TEST 7: Clinician Decrypts & Downloads Medical Record
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Authorized Clinical Decryption & Download...")
    client.force_login(doc_smith)

    download_resp = client.get(f'/records/{new_record.record_id}/download/')
    assert download_resp.status_code == 200, f"Download failed with code {download_resp.status_code}"
    decrypted_content = download_resp.content.decode('utf-8')
    assert 'normal ventricular caliber' in decrypted_content, "Decrypted text mismatch"
    print(f"  -> SUCCESS: File decrypted & downloaded successfully. (Content: '{decrypted_content[:45]}...')")

    # -------------------------------------------------------------
    # TEST 8: Patient Revokes Consent & Subsequent Download Denied (403)
    # -------------------------------------------------------------
    print("\n[TEST 8] Testing Patient Revocation on Algorand & Access Revocation...")
    client.force_login(patient_user)

    revoke_resp = client.post(f'/consent/permission/{permission.permission_id}/revoke/', follow=True)
    assert revoke_resp.status_code == 200

    permission.refresh_from_db()
    assert permission.is_revoked is True
    assert len(permission.algorand_revoke_tx_id) == 52

    # Dr. Smith tries to download again -> must be rejected (403)
    client.force_login(doc_smith)
    blocked_download = client.get(f'/records/{new_record.record_id}/download/')
    assert blocked_download.status_code == 403, f"Expected 403 Forbidden, got {blocked_download.status_code}"
    print(f"  -> SUCCESS: Permission revoked on-chain (TxID: {permission.algorand_revoke_tx_id[:12]}...). Subsequent download blocked with HTTP 403 Forbidden.")

    print("\n" + "=" * 65)
    print("  ALL 8 COMPREHENSIVE END-TO-END TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
