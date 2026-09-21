from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    VerifyEmailOTPView,
    RequestLoginCodeView,
    VerifyLoginCodeView,
    RequestPasswordResetEmailView,
    ConfirmPasswordResetEmailView,
    AuditLogListAPIView,
    EmailTokenObtainPairView,
    GoogleAuthView,
    OwnerCustomerCreateView,
)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/verify-email/', VerifyEmailOTPView.as_view(), name='auth-verify-email'),
    path('auth/email/request-code/', RequestLoginCodeView.as_view(), name='auth-email-request'),
    path('auth/email/verify-code/', VerifyLoginCodeView.as_view(), name='auth-email-verify'),
    path('auth/jwt/create/', EmailTokenObtainPairView.as_view(), name='jwt-create'),
    path('auth/google/', GoogleAuthView.as_view(), name='auth-google'),
    path('auth/jwt/refresh/', TokenRefreshView.as_view(), name='jwt-refresh'),
    path('auth/password-reset/request/', RequestPasswordResetEmailView.as_view(), name='password-reset-request'),
    path('auth/password-reset/confirm/', ConfirmPasswordResetEmailView.as_view(), name='password-reset-confirm'),
    path('audit-logs/', AuditLogListAPIView.as_view(), name='audit-logs'),
    path('customers/', OwnerCustomerCreateView.as_view(), name='owner-create-customer'),
]
