from django.core.cache import cache
from django.test import SimpleTestCase, override_settings


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'risk-radar-test',
        }
    }
)
class CacheBehaviorTests(SimpleTestCase):
    def test_otp_values_can_be_stored_and_removed(self):
        cache.set('test:otp', '123456', timeout=60)
        self.assertEqual(cache.get('test:otp'), '123456')

        cache.delete('test:otp')
        self.assertIsNone(cache.get('test:otp'))
