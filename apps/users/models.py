from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """JWT + email OTP autentifikatsiya va RBAC."""

    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Business Owner'
        EMPLOYEE = 'EMPLOYEE', 'Employee'
        CUSTOMER = 'CUSTOMER', 'Customer'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    email = models.EmailField(unique=True)
    google_subject = models.CharField(max_length=255, unique=True, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.email} ({self.role})"


class UserActivityLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities',
        null=True,
        blank=True,
    )
    action_name = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_data = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        who = self.user.email if self.user_id else 'anonymous'
        return f"{who} - {self.action_name} [{self.timestamp}]"
