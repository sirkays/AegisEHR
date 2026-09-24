import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    ROLE_PATIENT = 'patient'
    ROLE_PROVIDER = 'provider'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = (
        (ROLE_PATIENT, 'Patient'),
        (ROLE_PROVIDER, 'Healthcare Provider'),
        (ROLE_ADMIN, 'System Administrator'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PATIENT)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    algorand_address = models.CharField(max_length=58, blank=True, null=True, help_text="58-character Algorand wallet public address")

    def is_patient_user(self):
        return self.role == self.ROLE_PATIENT

    def is_provider_user(self):
        return self.role == self.ROLE_PROVIDER

    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser


def generate_patient_code():
    return f"PAT-{uuid.uuid4().hex[:8].upper()}"

def generate_provider_code():
    return f"PRV-{uuid.uuid4().hex[:8].upper()}"


class PatientProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )

    BLOOD_GROUP_CHOICES = (
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    patient_code = models.CharField(max_length=32, unique=True, default=generate_patient_code)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='other')
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, default='O+')
    emergency_contact = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.patient_code})"


class ProviderProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='provider_profile')
    provider_code = models.CharField(max_length=32, unique=True, default=generate_provider_code)
    license_number = models.CharField(max_length=50, unique=True, help_text="Medical Council Licensing Number")
    specialty = models.CharField(max_length=100, default='General Practice')
    institution = models.CharField(max_length=150, help_text="Hospital or Clinic Name")
    is_verified = models.BooleanField(default=False, help_text="Administrative authorization to access and create EHRs")
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_providers')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username} - {self.specialty} ({'Verified' if self.is_verified else 'Pending'})"

    def verify(self, admin_user):
        self.is_verified = True
        self.verified_at = timezone.now()
        self.verified_by = admin_user
        self.save()

    def revoke_verification(self):
        self.is_verified = False
        self.verified_at = None
        self.verified_by = None
        self.save()
