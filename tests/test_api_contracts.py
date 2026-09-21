from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.risks.models import RiskLog
from apps.users.models import User


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'risk-radar-api-tests',
        }
    }
)
class FrontendJsonApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username='customer-api',
            email='customer-api@example.com',
            password='A-strong-password-123',
            role=User.Role.CUSTOMER,
        )

    def test_customer_json_is_stored_with_customer_source(self):
        self.client.force_authenticate(self.customer)
        payload = {
            'order_id': 42,
            'customer_id': 7,
            'total_amount': '125.50',
            'inflow_amount': '200.00',
            'outflow_amount': '74.50',
            'items': [{'sku': 'SKU-1', 'quantity': 2}],
        }

        response = self.client.post(
            '/api/risks/ingest/customer/',
            payload,
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        risk_log = RiskLog.objects.get(pk=response.data['id'])
        self.assertEqual(risk_log.source_app, RiskLog.SourceApp.CUSTOMER_APP)
        self.assertEqual(risk_log.payload_json['order_id'], 42)
        self.assertEqual(risk_log.payload_json['items'][0]['sku'], 'SKU-1')

    def test_google_login_requires_configuration(self):
        response = self.client.post(
            '/api/users/auth/google/',
            {'credential': 'not-a-real-google-token'},
            format='json',
        )
        self.assertEqual(response.status_code, 503)
