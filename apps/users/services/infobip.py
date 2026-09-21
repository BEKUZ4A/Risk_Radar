import logging
import os

import requests

logger = logging.getLogger(__name__)


class InfobipSMSService:
    """Infobip portal API orqali SMS yuborish servisi."""

    @staticmethod
    def send_sms(phone_number: str, message_text: str) -> bool:
        base_url = os.getenv('INFOBIP_BASE_URL')
        api_key = os.getenv('INFOBIP_API_KEY')
        sender = os.getenv('INFOBIP_SENDER', 'InfoSMS')

        if not base_url or not api_key or 'your_' in (api_key or ''):
            logger.warning('Infobip sozlanmagan — SMS skip (dev mode). OTP logda ko‘rinadi.')
            logger.info('DEV OTP SMS [%s]: %s', phone_number, message_text)
            return True

        endpoint = f"{base_url.rstrip('/')}/sms/2/text/advanced"
        headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {
            'messages': [
                {
                    'from': sender,
                    'destinations': [{'to': phone_number}],
                    'text': message_text,
                }
            ]
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            if response.status_code in (200, 201):
                return True
            logger.error('Infobip SMS xatosi: %s - %s', response.status_code, response.text)
            return False
        except Exception as exc:
            logger.error('Infobip SMS so‘rovi amalga oshmadi: %s', exc)
            return False
