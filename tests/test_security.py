from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.catalog.models import Category, Product
from apps.risks.models import FinancialBalance
from apps.users.models import User
from apps.users.serializers import RegisterSerializer
from rest_framework.test import APIClient


class RegistrationSecurityTests(TestCase):
    def test_root_username_is_reserved(self):
        response = APIClient().post(
            '/api/users/auth/register/',
            {
                'username': 'root',
                'email': 'root-registration@example.com',
                'password': 'A-strong-password-123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_unverified_user_cannot_get_jwt_or_owner_access(self):
        user = User.objects.create_user(
            username='root-like',
            email='unverified@example.com',
            password='A-strong-password-123',
            role=User.Role.OWNER,
            is_email_verified=False,
        )
        client = APIClient()
        response = client.post(
            '/api/users/auth/jwt/create/',
            {'email': user.email, 'password': 'A-strong-password-123'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn(client.get('/api/risks/dashboard-json/').status_code, (401, 403))

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
            is_email_verified=True,
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

    def test_employee_can_browse_catalog(self):
        employee = User.objects.create_user(
            username='employee',
            email='employee@example.com',
            password='A-strong-password-123',
            role=User.Role.EMPLOYEE,
            is_email_verified=True,
        )
        category = Category.objects.create(name='Employee category', created_by=self.customer)
        Product.objects.create(
            category=category,
            name='Employee product',
            price='10.00',
            stock_quantity=5,
            created_by=self.customer,
        )
        self.client.force_authenticate(employee)

        response = self.client.get('/api/catalog/products/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['name'], 'Employee product')

    def test_customer_cannot_edit_another_customers_product(self):
        other = User.objects.create_user(
            username='other-customer',
            email='other@example.com',
            password='A-strong-password-123',
            role=User.Role.CUSTOMER,
            is_email_verified=True,
        )
        category = Category.objects.create(name='Owned category', created_by=other)
        product = Product.objects.create(
            category=category,
            name='Owned product',
            price='10.00',
            created_by=other,
        )
        response = self.client.put(
            f'/api/catalog/products/{product.pk}/',
            {'name': 'Tampered'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_can_ingest_financial_data_repeatedly(self):
        payload = {
            'total_amount': '100.00',
            'inflow_amount': '100.00',
            'outflow_amount': '25.50',
            'inactive_users_15days': [],
        }
        first = self.client.post('/api/risks/ingest/customer/', payload, format='json')
        second = self.client.post('/api/risks/ingest/customer/', payload, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        balance = FinancialBalance.objects.get()
        self.assertEqual(balance.total_inflow, Decimal('200.00'))
        self.assertEqual(balance.total_outflow, Decimal('51.00'))

    def test_owner_can_use_employee_checkout_endpoint(self):
        from apps.payments.views import EmployeeCheckoutAPIView

        owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='A-strong-password-123',
            role=User.Role.OWNER,
            is_email_verified=True,
        )
        request = type('Request', (), {'user': owner})()
        self.assertTrue(
            EmployeeCheckoutAPIView.permission_classes[0]().has_permission(
                request,
                EmployeeCheckoutAPIView(),
            )
        )

    def test_customer_can_create_product_with_frontend_fields(self):
        category = Category.objects.create(name='Products category', created_by=self.customer)
        response = self.client.post(
            '/api/catalog/products/',
            {
                'category': category.pk,
                'name': 'Risk Radar product',
                'description': 'Product description',
                'image': 'https://example.com/product.png',
                'price': '125.50',
                'count': 7,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        product = Product.objects.get(pk=response.data['id'])
        self.assertEqual(product.name, 'Risk Radar product')
        self.assertEqual(product.description, 'Product description')
        self.assertEqual(product.image, 'https://example.com/product.png')
        self.assertEqual(product.price, Decimal('125.50'))
        self.assertEqual(product.stock_quantity, 7)
        self.assertEqual(response.data['count'], 7)
