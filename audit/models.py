import uuid
from django.db import models
from django.utils import timezone
from accounts.models import User
from records.models import MedicalRecord

class AuditEvent(models.Model):
    EVENT_TYPE_CHOICES = (
        ('user_registration', 'User Account Registration'),
        ('provider_verification', 'Provider Credential Verified'),
        ('provider_revocation', 'Provider Credential Suspended'),
        ('record_upload', 'Encrypted Record Upload & IPFS Commit'),
        ('record_blockchain_anchor', 'Record Metadata Anchored on Algorand'),
        ('access_requested', 'Clinical Access Requested'),
        ('consent_granted', 'Patient Scoped Consent Granted'),
        ('consent_revoked', 'Patient Consent Revoked On-Chain'),
        ('record_retrieval_success', 'Authorized Clinical Decryption & View'),
        ('record_retrieval_denied', 'Access Denied / Unauthorised Attempt'),
        ('integrity_check_failure', 'Integrity Alert: Digest or Tag Mismatch'),
        ('system_operational', 'System Service / Maintenance Event'),
    )

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=40, choices=EVENT_TYPE_CHOICES)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_events')
    actor_role = models.CharField(max_length=20, default='system')
    actor_address = models.CharField(max_length=58, blank=True, null=True, help_text="Algorand public address")
    record = models.ForeignKey(MedicalRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    description = models.TextField()
    is_on_chain = models.BooleanField(default=False, help_text="True if anchored on Algorand blockchain ledger")
    algorand_tx_id = models.CharField(max_length=64, blank=True, null=True, help_text="Transaction reference on Algorand")
    confirmation_round = models.PositiveBigIntegerField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        evidence = "ON-CHAIN" if self.is_on_chain else "OFF-CHAIN"
        return f"[{evidence}] {self.get_event_type_display()} by {self.actor or 'System'} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log(cls, event_type, description, actor=None, record=None, is_on_chain=False, tx_id=None, round_num=None, ip_address='127.0.0.1'):
        role = actor.role if actor and hasattr(actor, 'role') else 'system'
        address = actor.algorand_address if actor and hasattr(actor, 'algorand_address') else None
        return cls.objects.create(
            event_type=event_type,
            actor=actor,
            actor_role=role,
            actor_address=address,
            record=record,
            description=description,
            is_on_chain=is_on_chain,
            algorand_tx_id=tx_id,
            confirmation_round=round_num,
            ip_address=ip_address
        )
