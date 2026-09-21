from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.catalog.models import Category
from apps.users.models import User
from apps.users.serializers import RegisterSerializer
from rest_framework.test import APIClient


class RegistrationSecurityTests(TestCase):
    def test_public_registration_cannot_select_privileged_role(self):
        serializer = RegisterSerializer(
            data={
                'username': 'attacker',
                'email': 'attacker@example.com',
                'password': 'A-strong-password-123',
                'role': 'OWNER',
            }
        )

        self.assertNotIn('role', serializer.fields)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertEqual(user.role, User.Role.EMPLOYEE)

    def test_promote_user_grants_full_administrator_access(self):
        user = User.objects.create_user(
            username='behruzbekb98',
            email='behruzbekb98@gmail.com',
            password='A-strong-password-123',
            role=User.Role.EMPLOYEE,
        )

        call_command('promote_user', 'BEHRUZBEKB98@GMAIL.COM')

        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.OWNER)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'risk-radar-catalog-tests',
        }
    }
)
class CustomerCatalogAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='A-strong-password-123',
            role=User.Role.CUSTOMER,
        )
        self.client.force_authenticate(self.customer)

    def test_customer_can_create_and_update_category(self):
        response = self.client.post(
            '/api/catalog/categories/',
            {'name': 'Customer category', 'description': 'Created by customer'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        category = Category.objects.get(pk=response.data['id'])

        response = self.client.put(
            f'/api/catalog/categories/{category.pk}/',
            {'description': 'Updated by customer'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        category.refresh_from_db()
        self.assertEqual(category.description, 'Updated by customer')
