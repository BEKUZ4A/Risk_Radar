import os

from django.core.cache import cache

EMAIL_COOLDOWN = int(os.getenv('EMAIL_COOLDOWN_SECONDS', 60))
MAX_FAILED_OTP = int(os.getenv('MAX_FAILED_OTP_ATTEMPTS', 3))
INITIAL_BLOCK_MIN = int(os.getenv('INITIAL_BLOCK_MINUTES', 5))
MAX_BLOCK_MIN = int(os.getenv('MAX_BLOCK_MINUTES', 15))


def check_global_block(email: str):
    block_key = f'blocked_user:{email.lower()}'
    if cache.get(block_key):
        return True, (
            f"Ko'p xato urinishlar sababli bloklangansiz. "
            f"Birozdan so'ng (max {MAX_BLOCK_MIN} min) qayta urinib ko'ring."
        )
    return False, None


def can_request_email_code(email: str, ip: str | None = None):
    cooldown_key = f'email_cooldown:{email.lower()}'
    ip_key = f'email_cooldown_ip:{ip}' if ip else None
    if cache.get(cooldown_key):
        return False, 'Email kod so‘rovi uchun 1 daqiqa kuting.'
    if ip_key and cache.get(ip_key):
        return False, 'Email kod so‘rovi uchun 1 daqiqa kuting.'
    return True, None


def set_email_cooldown(email: str):
    cache.set(f'email_cooldown:{email.lower()}', '1', timeout=EMAIL_COOLDOWN)


def set_email_ip_cooldown(ip: str | None):
    if ip:
        cache.set(f'email_cooldown_ip:{ip}', '1', timeout=EMAIL_COOLDOWN)


def handle_failed_otp_attempt(email: str):
    attempts_key = f'otp_failed_attempts:{email.lower()}'
    attempts = cache.get(attempts_key, 0) + 1
    cache.set(attempts_key, attempts, timeout=3600)

    if attempts >= MAX_FAILED_OTP:
        multiplier = 2 ** (attempts - MAX_FAILED_OTP)
        block_time_minutes = min(INITIAL_BLOCK_MIN * multiplier, MAX_BLOCK_MIN)
        cache.set(
            f'blocked_user:{email.lower()}',
            'blocked',
            timeout=block_time_minutes * 60,
        )
        return block_time_minutes
    return 0


def clear_otp_attempts(email: str):
    email = email.lower()
    cache.delete(f'otp_failed_attempts:{email}')
    cache.delete(f'blocked_user:{email}')
