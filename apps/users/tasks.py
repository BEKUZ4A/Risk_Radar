from celery import shared_task

from apps.users.services.email_otp import EmailOTPService


@shared_task
def send_otp_email(email: str, code: str, purpose: str = 'verification') -> bool:
    """Send an OTP email in a Celery worker."""
    return EmailOTPService.send_code(email, code, purpose=purpose)
