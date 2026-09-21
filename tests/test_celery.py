from unittest.mock import patch

from django.test import SimpleTestCase

from config.celery import app
from apps.users.tasks import send_otp_email


class CeleryConfigurationTests(SimpleTestCase):
    def test_celery_uses_redis_broker_and_backend(self):
        self.assertTrue(app.conf.broker_url.startswith('redis://'))
        self.assertTrue(app.conf.result_backend.startswith('redis://'))
        self.assertIn('apps.users.tasks.send_otp_email', app.tasks)

    @patch('apps.users.tasks.EmailOTPService.send_code', return_value=True)
    def test_otp_task_sends_email(self, send_code):
        result = send_otp_email.run('user@example.com', '123456', 'login')

        self.assertTrue(result)
        send_code.assert_called_once_with(
            'user@example.com',
            '123456',
            purpose='login',
        )
