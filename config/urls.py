from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf import settings


def api_root(request):
    return JsonResponse(
        {
            'service': 'Central Risk Engine',
            'docs': request.build_absolute_uri('/api/docs/') if settings.ENABLE_API_DOCS else None,
            'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
            'endpoints': {
                'register': '/api/users/auth/register/',
                'verify_email': '/api/users/auth/verify-email/',
                'email_request_code': '/api/users/auth/email/request-code/',
                'email_verify_code': '/api/users/auth/email/verify-code/',
                'jwt_create': '/api/users/auth/jwt/create/',
                'categories': '/api/catalog/categories/',
                'products': '/api/catalog/products/',
                'employee_checkout': '/api/payments/checkout/',
                'dashboard_json': '/api/risks/dashboard-json/',
            },
        }
    )


urlpatterns = [
    path('', RedirectView.as_view(url='/api/docs/' if settings.ENABLE_API_DOCS else '/api/', permanent=False)),
    path('api/', api_root, name='api-root'),
    path('admin/', admin.site.urls),
    path('api/users/', include('apps.users.urls')),
    path('api/risks/', include('apps.risks.urls')),
    path('api/catalog/', include('apps.catalog.urls')),
    path('api/payments/', include('apps.payments.urls')),
]

if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]
