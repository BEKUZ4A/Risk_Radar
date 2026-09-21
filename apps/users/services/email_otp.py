import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class EmailOTPService:
    """Email orqali 6 xonali kod yuborish."""

    @staticmethod
    def send_code(email: str, code: str, purpose: str = 'verification') -> bool:
        subject = 'Risk Radar — tasdiqlash kodi'
        if purpose == 'login':
            subject = 'Risk Radar — kirish kodi'
        elif purpose == 'password_reset':
            subject = 'Risk Radar — parolni tiklash kodi'

        body = (
            f'Sizning kodingiz: {code}\n\n'
            f'Kod 5 daqiqa amal qiladi.\n'
            f'Agar bu so‘rovni siz yubormagan bo‘lsangiz, e’tiborsiz qoldiring.'
        )

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info('OTP email yuborildi: %s (%s)', email, purpose)
            return True
        except Exception as exc:
            logger.exception('Email yuborilmadi: %s', exc)
            # Dev: console backend odatda ishlaydi; xato bo‘lsa ham logda kod
            logger.warning('DEV FALLBACK OTP [%s]: %s', email, code)
            return False
