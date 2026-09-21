import os
import requests
import logging

logger = logging.getLogger(__name__)


class InfobipSMSService:
    """Infobip portal API orqali SMS yuborish servisi"""

    @staticmethod
    def send_sms(phone_number: str, message_text: str) -> bool:
        base_url = os.getenv('INFOBIP_BASE_URL')
        api_key = os.getenv('INFOBIP_API_KEY')
        sender = os.getenv('INFOBIP_SENDER', 'InfoSMS')

        if not base_url or not api_key:
            logger.error("Infobip API kalitlari .env faylida ko'rsatilmagan!")
            return False

        endpoint = f"{base_url.rstrip('/')}/sms/2/text/advanced"
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "messages": [
                {
                    "from": sender,
                    "destinations": [{"to": phone_number}],
                    "text": message_text
                }
            ]
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                return True
            logger.error(f"Infobip SMS xatosi: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            logger.error(f"Infobip SMS so'rovi amalga oshmadi: {str(e)}")
            return False