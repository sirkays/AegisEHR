import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, PatientProfile, ProviderProfile
from records.models import MedicalRecord, EncryptedPackage, RecordBlockchainState
from consent.models import AccessRequest, ConsentPermission
from audit.models import AuditEvent
from records.services import CryptoService
from blockchain.services import AlgorandService

class Command(BaseCommand):
    help = 'Seeds the EHR database with comprehensive demo patients, providers, encrypted records, consent states, and audit trails'

    def handle(self, *args, **options):
        self.stdout.write("Initializing AegisEHR data seeding...")

        # 1. Create Administrator
        admin_user, _ = User.objects.get_or_create(
            username='admin_auditor',
            defaults={
                'email': 'admin@aegisehr.org',
                'first_name': 'Marcus',
                'last_name': 'Vance',
                'role': User.ROLE_ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'algorand_address': AlgorandService.generate_wallet()['address']
            }
        )
        admin_user.set_password('demo12345')
        admin_user.save()
        self.stdout.write(f"Created Admin: {admin_user.username}")

        # 2. Create Providers
        # Verified Provider: Dr. Evelyn Smith
        doc1_wallet = AlgorandService.generate_wallet()
        doc1_user, _ = User.objects.get_or_create(
            username='dr_smith',
            defaults={
                'email': 'dr.smith@metrohospital.org',
                'first_name': 'Evelyn',
                'last_name': 'Smith',
                'role': User.ROLE_PROVIDER,
                'algorand_address': doc1_wallet['address']
            }
        )
        doc1_user.set_password('demo12345')
        doc1_user.save()

        doc1_profile, _ = ProviderProfile.objects.get_or_create(
            user=doc1_user,
            defaults={
                'license_number': 'MED-CARDIO-9812',
                'specialty': 'Cardiology & Internal Medicine',
                'institution': 'Metropolitan University Hospital',
                'is_verified': True,
                'verified_at': timezone.now(),
                'verified_by': admin_user
            }
        )

        # Unverified Provider: Dr. Liam Jones (For testing Figure 4.12 verification workflow)
        doc2_wallet = AlgorandService.generate_wallet()
        doc2_user, _ = User.objects.get_or_create(
            username='dr_jones',
            defaults={
                'email': 'dr.jones@cityortho.clinic',
                'first_name': 'Liam',
                'last_name': 'Jones',
                'role': User.ROLE_PROVIDER,
                'algorand_address': doc2_wallet['address']
            }
        )
        doc2_user.set_password('demo12345')
        doc2_user.save()

        doc2_profile, _ = ProviderProfile.objects.get_or_create(
            user=doc2_user,
            defaults={
                'license_number': 'MED-ORTHO-4102',
                'specialty': 'Orthopedic Surgery',
                'institution': 'City Orthopedic Specialty Clinic',
                'is_verified': False
            }
        )
        self.stdout.write("Created Providers: Dr. Evelyn Smith (Verified) & Dr. Liam Jones (Pending)")

        # 3. Create Patients
        # Alice Patient
        pat1_wallet = AlgorandService.generate_wallet()
        pat1_user, _ = User.objects.get_or_create(
            username='alice_patient',
            defaults={
                'email': 'alice.williams@gmail.com',
                'first_name': 'Alice',
                'last_name': 'Williams',
                'role': User.ROLE_PATIENT,
                'algorand_address': pat1_wallet['address']
            }
        )
        pat1_user.set_password('demo12345')
        pat1_user.save()

        pat1_profile, _ = PatientProfile.objects.get_or_create(
            user=pat1_user,
            defaults={
                'patient_code': 'PAT-2026-8901',
                'gender': 'female',
                'blood_group': 'O+',
                'date_of_birth': datetime.date(1991, 4, 12),
                'emergency_contact': '+1 (555) 302-8819 (Spouse)'
            }
        )

        # Bob Patient
        pat2_wallet = AlgorandService.generate_wallet()
        pat2_user, _ = User.objects.get_or_create(
            username='bob_patient',
            defaults={
                'email': 'bob.miller@outlook.com',
                'first_name': 'Bob',
                'last_name': 'Miller',
                'role': User.ROLE_PATIENT,
                'algorand_address': pat2_wallet['address']
            }
        )
        pat2_user.set_password('demo12345')
        pat2_user.save()

        pat2_profile, _ = PatientProfile.objects.get_or_create(
            user=pat2_user,
            defaults={
                'patient_code': 'PAT-2026-4472',
                'gender': 'male',
                'blood_group': 'A+',
                'date_of_birth': datetime.date(1985, 9, 28),
                'emergency_contact': '+1 (555) 918-4421 (Brother)'
            }
        )
        self.stdout.write("Created Patients: Alice Williams & Bob Miller")

        # 4. Create Medical Records & Packages
        sample_records_data = [
            {
                'patient': pat1_profile,
                'creator': doc1_profile,
                'title': 'Comprehensive Metabolic Panel & Lipid Profile',
                'category': 'laboratory',
                'record_date': datetime.date(2026, 8, 14),
                'version': 1,
                'diagnosis_code': 'E78.5 (Hyperlipidemia)',
                'notes': (
                    "CLINICAL LABORATORY FINDINGS:\n"
                    "• Fasting Blood Glucose: 98 mg/dL (Normal Range: 70-99 mg/dL)\n"
                    "• Total Cholesterol: 215 mg/dL (Elevated)\n"
                    "• HDL Cholesterol: 58 mg/dL (Desirable)\n"
                    "• LDL Cholesterol: 134 mg/dL (Borderline High)\n"
                    "• Triglycerides: 145 mg/dL (Normal < 150 mg/dL)\n"
                    "• Serum Creatinine: 0.9 mg/dL (eGFR > 90 mL/min/1.73m²)\n\n"
                    "ASSESSMENT & PLAN:\n"
                    "Mild hyperlipidemia. Lifestyle modification, Mediterranean dietary protocol, and repeat lipid panel in 6 months."
                )
            },
            {
                'patient': pat1_profile,
                'creator': doc1_profile,
                'title': 'Resting 12-Lead Electrocardiogram (ECG)',
                'category': 'clinical_summary',
                'record_date': datetime.date(2026, 9, 2),
                'version': 1,
                'diagnosis_code': 'R00.1 (Sinus Bradycardia)',
                'notes': (
                    "CARDIOLOGY EXAMINATION REPORT:\n"
                    "• Heart Rate: 54 bpm (Sinus rhythm with physiological bradycardia)\n"
                    "• PR Interval: 156 ms\n"
                    "• QRS Duration: 84 ms\n"
                    "• QT / QTc: 394 / 412 ms\n"
                    "• ST-T wave morphology: Normal throughout precordial and limb leads.\n\n"
                    "CONCLUSION: Normal athletic variant sinus bradycardia. No ischemic alterations."
                )
            },
            {
                'patient': pat2_profile,
                'creator': doc1_profile,
                'title': 'Lumbar Spine MRI Radiological Examination',
                'category': 'radiology',
                'record_date': datetime.date(2026, 9, 10),
                'version': 1,
                'diagnosis_code': 'M51.26 (Intervertebral disc displacement, lumbar)',
                'notes': (
                    "RADIOLOGY & IMAGING REPORT (MRI 3.0T):\n"
                    "• Sequence: Multiplanar T1 and T2 weighted imaging of lumbar spine.\n"
                    "• Alignment: Preserved lumbar lordosis.\n"
                    "• L4-L5: Moderate broad-based posterior disc protrusion indenting the thecal sac. Mild bilateral neural foraminal narrowing without frank root impingement.\n"
                    "• L5-S1: Mild disc desiccation with intact posterior longitudinal ligament.\n\n"
                    "RECOMMENDATION: Conservative physical therapy protocol."
                )
            }
        ]

        created_records = []
        for rdata in sample_records_data:
            rec, _ = MedicalRecord.objects.get_or_create(
                patient=rdata['patient'],
                title=rdata['title'],
                defaults={
                    'creator': rdata['creator'],
                    'category': rdata['category'],
                    'record_date': rdata['record_date'],
                    'version': rdata['version'],
                    'diagnosis_code': rdata['diagnosis_code'],
                    'clinical_notes': rdata['notes']
                }
            )

            # Encrypt and package
            if not hasattr(rec, 'encrypted_package'):
                crypto_result = CryptoService.encrypt_medical_document(
                    plaintext_bytes=rdata['notes'].encode('utf-8'),
                    record_id_str=str(rec.record_id),
                    version_int=rec.version
                )
                pkg = EncryptedPackage.objects.create(
                    record=rec,
                    ipfs_cid=crypto_result['ipfs_cid'],
                    package_digest=crypto_result['package_digest'],
                    nonce=crypto_result['nonce_hex'],
                    auth_tag=crypto_result['auth_tag_hex'],
                    wrapped_key=crypto_result['wrapped_key'],
                    file_format='text/plain',
                    file_size_bytes=crypto_result['size_bytes']
                )

                # Commit to simulated Algorand ledger
                chain_receipt = AlgorandService.register_record_on_chain(
                    record_id_str=str(rec.record_id),
                    cid=crypto_result['ipfs_cid'],
                    package_digest=crypto_result['package_digest'],
                    owner_address=rdata['patient'].user.algorand_address,
                    creator_address=rdata['creator'].user.algorand_address
                )

                RecordBlockchainState.objects.create(
                    record=rec,
                    algorand_tx_id=chain_receipt['tx_id'],
                    confirmation_round=chain_receipt['confirmation_round'],
                    app_id=chain_receipt['app_id'],
                    status=RecordBlockchainState.STATUS_CONFIRMED,
                    raw_payload_hash=crypto_result['package_digest'],
                    confirmed_at=timezone.now()
                )

                # Log to audit trail
                AuditEvent.log(
                    event_type='record_upload',
                    description=f"Record '{rec.title}' encrypted and stored on IPFS (CID: {pkg.ipfs_cid[:16]}...)",
                    actor=rdata['creator'].user,
                    record=rec
                )
                AuditEvent.log(
                    event_type='record_blockchain_anchor',
                    description=f"EHR anchor confirmed on Algorand Ledger (Round #{chain_receipt['confirmation_round']})",
                    actor=rdata['creator'].user,
                    record=rec,
                    is_on_chain=True,
                    tx_id=chain_receipt['tx_id'],
                    round_num=chain_receipt['confirmation_round']
                )

            created_records.append(rec)

        self.stdout.write(f"Created {len(created_records)} encrypted EHR packages anchored to Algorand")

        # 5. Create Scoped Consent Permissions & Access Requests
        # Active Permission: Alice grants Dr. Smith access to Metabolic Panel
        rec1 = created_records[0]
        grant_tx = AlgorandService.grant_consent_on_chain(
            record_id_str=str(rec1.record_id),
            patient_address=pat1_user.algorand_address,
            provider_address=doc1_user.algorand_address,
            expiry_timestamp=timezone.now() + datetime.timedelta(days=14)
        )

        perm1, _ = ConsentPermission.objects.get_or_create(
            patient=pat1_profile,
            provider=doc1_profile,
            record=rec1,
            defaults={
                'expires_at': timezone.now() + datetime.timedelta(days=14),
                'algorand_grant_tx_id': grant_tx['tx_id'],
                'algorand_grant_round': grant_tx['confirmation_round'],
                'is_revoked': False
            }
        )

        AuditEvent.log(
            event_type='consent_granted',
            description=f"Patient Alice Williams granted 14-day scoped consent to Dr. Evelyn Smith for '{rec1.title}'",
            actor=pat1_user,
            record=rec1,
            is_on_chain=True,
            tx_id=grant_tx['tx_id'],
            round_num=grant_tx['confirmation_round']
        )

        # Revoked Permission (Demonstrating Figure 4.9 & Figure 4.10 security revocation):
        # Alice revoked an earlier consent grant to Dr. Jones
        rec2 = created_records[1]
        revoke_tx = AlgorandService.revoke_consent_on_chain(
            record_id_str=str(rec2.record_id),
            patient_address=pat1_user.algorand_address,
            provider_address=doc2_user.algorand_address
        )
        perm2, _ = ConsentPermission.objects.get_or_create(
            patient=pat1_profile,
            provider=doc2_profile,
            record=rec2,
            defaults={
                'expires_at': timezone.now() + datetime.timedelta(days=7),
                'algorand_grant_tx_id': AlgorandService._generate_txid(),
                'algorand_grant_round': grant_tx['confirmation_round'] - 100,
                'is_revoked': True,
                'revoked_at': timezone.now() - datetime.timedelta(days=1),
                'algorand_revoke_tx_id': revoke_tx['tx_id'],
                'algorand_revoke_round': revoke_tx['confirmation_round']
            }
        )

        AuditEvent.log(
            event_type='consent_revoked',
            description=f"Patient Alice Williams permanently REVOKED access for Dr. Liam Jones regarding record '{rec2.title}'",
            actor=pat1_user,
            record=rec2,
            is_on_chain=True,
            tx_id=revoke_tx['tx_id'],
            round_num=revoke_tx['confirmation_round']
        )

        # Pending Request: Dr. Smith requests access to Bob's MRI record
        rec3 = created_records[2]
        req1, _ = AccessRequest.objects.get_or_create(
            patient=pat2_profile,
            provider=doc1_profile,
            record=rec3,
            defaults={
                'clinical_purpose': 'Pre-operative neurological and musculoskeletal evaluation for chronic back pain symptoms',
                'requested_duration_days': 7,
                'status': AccessRequest.STATUS_PENDING
            }
        )

        AuditEvent.log(
            event_type='access_requested',
            description=f"Dr. Evelyn Smith requested clinical access to '{rec3.title}' for Patient Bob Miller",
            actor=doc1_user,
            record=rec3
        )

        self.stdout.write(self.style.SUCCESS("AegisEHR database successfully seeded with all demo roles, encrypted packages, consent states, and on-chain audit logs!"))
