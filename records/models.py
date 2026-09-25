import uuid
from django.db import models
from accounts.models import PatientProfile, ProviderProfile

class MedicalRecord(models.Model):
    CATEGORY_CHOICES = (
        ('clinical_summary', 'Clinical Summary & Examination'),
        ('laboratory', 'Laboratory & Pathology Report'),
        ('radiology', 'Radiology & Medical Imaging'),
        ('prescription', 'Prescription & Pharmacy Order'),
        ('discharge', 'Inpatient Discharge Summary'),
        ('vaccination', 'Immunisation & Vaccination Record'),
    )

    record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='medical_records')
    creator = models.ForeignKey(ProviderProfile, on_delete=models.PROTECT, related_name='authored_records')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='clinical_summary')
    record_date = models.DateField()
    version = models.PositiveIntegerField(default=1)
    previous_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subsequent_versions')
    clinical_notes = models.TextField(help_text="Structured clinical notes (encrypted before IPFS commit)")
    diagnosis_code = models.CharField(max_length=50, blank=True, null=True, help_text="Opaque ICD/Category code")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-record_date', '-created_at']

    def __str__(self):
        return f"{self.title} (v{self.version}) - {self.patient.patient_code}"

    @property
    def is_confirmed_on_chain(self):
        return hasattr(self, 'blockchain_state') and self.blockchain_state.status == 'confirmed'


class EncryptedPackage(models.Model):
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE, related_name='encrypted_package')
    ipfs_cid = models.CharField(max_length=100, help_text="InterPlanetary File System Content Identifier")
    package_digest = models.CharField(max_length=64, help_text="SHA-256 digest computed over complete stored package")
    nonce = models.CharField(max_length=64, help_text="Hex-encoded 96-bit AES-GCM nonce")
    auth_tag = models.CharField(max_length=64, help_text="Hex-encoded 128-bit AES-GCM authentication tag")
    wrapped_key = models.TextField(help_text="Data encryption key wrapped under Key-Encryption-Key")
    file_format = models.CharField(max_length=50, default='application/pdf')
    original_filename = models.CharField(max_length=255, default='clinical_record.txt')
    file_size_bytes = models.PositiveIntegerField(default=0)
    encrypted_file = models.FileField(upload_to='encrypted_packages/', blank=True, null=True)
    ciphertext_b64 = models.TextField(blank=True, null=True, help_text="Base64-encoded package bytes for resilient cloud storage")
    stored_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Package for {self.record_id} [CID: {self.ipfs_cid[:12]}...]"


class RecordBlockchainState(models.Model):
    STATUS_PREPARED = 'prepared'
    STATUS_SUBMITTED = 'submitted'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = (
        (STATUS_PREPARED, 'Prepared'),
        (STATUS_SUBMITTED, 'Submitted to Mempool'),
        (STATUS_CONFIRMED, 'Confirmed on Algorand Ledger'),
        (STATUS_REJECTED, 'Rejected / Error'),
    )

    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE, related_name='blockchain_state')
    algorand_tx_id = models.CharField(max_length=64, blank=True, null=True, help_text="Algorand Transaction ID")
    confirmation_round = models.PositiveBigIntegerField(null=True, blank=True, help_text="Block round")
    app_id = models.PositiveBigIntegerField(null=True, blank=True, help_text="Algorand App ID")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PREPARED)
    raw_payload_hash = models.CharField(max_length=64, blank=True, null=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.record.title} [{self.get_status_display()}] - Round: {self.confirmation_round}"
