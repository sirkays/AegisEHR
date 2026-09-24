import uuid
from django.db import models
from django.utils import timezone
from accounts.models import PatientProfile, ProviderProfile
from records.models import MedicalRecord

class AccessRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending Patient Review'),
        (STATUS_APPROVED, 'Approved & Granted'),
        (STATUS_REJECTED, 'Rejected by Patient'),
        (STATUS_EXPIRED, 'Request Expired'),
    )

    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='received_requests')
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='initiated_requests')
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='access_requests')
    clinical_purpose = models.TextField(help_text="Detailed justification for clinical access request")
    requested_duration_days = models.PositiveIntegerField(default=7, help_text="Requested access duration in days")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decision_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request by {self.provider} for {self.record.title} [{self.get_status_display()}]"


class ConsentPermission(models.Model):
    permission_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(AccessRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='permission')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='granted_permissions')
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='received_permissions')
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='permissions')
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(help_text="Exact expiry timestamp when permission terminates")
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    # Blockchain Audit Trails
    algorand_grant_tx_id = models.CharField(max_length=64, blank=True, null=True, help_text="Algorand transaction ID for consent grant")
    algorand_grant_round = models.PositiveBigIntegerField(null=True, blank=True)
    algorand_revoke_tx_id = models.CharField(max_length=64, blank=True, null=True, help_text="Algorand transaction ID for revocation")
    algorand_revoke_round = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-granted_at']

    def __str__(self):
        status = "Revoked" if self.is_revoked else ("Active" if self.is_currently_valid else "Expired")
        return f"Permission: {self.provider.user.username} -> {self.record.title} [{status}]"

    @property
    def is_currently_valid(self):
        if self.is_revoked:
            return False
        return timezone.now() < self.expires_at

    @property
    def is_active(self):
        return self.is_currently_valid

    def revoke(self, tx_id=None, round_num=None):
        self.is_revoked = True
        self.revoked_at = timezone.now()
        if tx_id:
            self.algorand_revoke_tx_id = tx_id
        if round_num:
            self.algorand_revoke_round = round_num
        self.save()
