import random
import re
from uuid import uuid4

from django.core.cache import cache
from django.conf import settings
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from drf_spectacular.utils import extend_schema

from apps.users.models import User, UserActivityLog
from apps.users.permissions import IsBusinessOwner
from apps.users.serializers import (
    RegisterSerializer,
    EmailCodeRequestSerializer,
    EmailCodeVerifySerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
    UserActivityLogSerializer,
    GoogleAuthSerializer,
    OwnerCustomerCreateSerializer,
)
from apps.users.tasks import send_otp_email
from apps.users.utils import (
    check_global_block,
    can_request_email_code,
    set_email_cooldown,
    handle_failed_otp_attempt,
    clear_otp_attempts,
)


def _client_ip(request):
    return request.META.get('REMOTE_ADDR')


def _issue_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    }


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login email + password (USERNAME_FIELD = email)."""

    username_field = User.EMAIL_FIELD


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class GoogleAuthView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(request=GoogleAuthSerializer, responses={200: dict, 400: dict, 503: dict})
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not settings.GOOGLE_CLIENT_ID:
            return Response(
                {'error': 'Google login is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            claims = id_token.verify_oauth2_token(
                serializer.validated_data['credential'],
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except (ValueError, GoogleAuthError):
            return Response(
                {'error': 'Google credential is invalid or expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = str(claims.get('email', '')).lower().strip()
        subject = str(claims.get('sub', '')).strip()
        if not email or not subject or not claims.get('email_verified', False):
            return Response(
                {'error': 'Google account email is not verified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(google_subject=subject).first()
        if user is None:
            user = User.objects.filter(email=email).first()
        if user is None:
            base_username = re.sub(r'[^a-zA-Z0-9_.-]', '', email.split('@')[0])[:100] or 'google-user'
            user = User.objects.create_user(
                username=f'{base_username}-{uuid4().hex[:8]}',
                email=email,
                first_name=str(claims.get('given_name', '')),
                last_name=str(claims.get('family_name', '')),
                password=uuid4().hex,
                role=User.Role.EMPLOYEE,
                is_email_verified=True,
                google_subject=subject,
            )
        else:
            user.google_subject = subject
            user.is_email_verified = True
            user.save(update_fields=['google_subject', 'is_email_verified'])

        UserActivityLog.objects.create(
            user=user,
            action_name='GOOGLE_LOGIN',
            ip_address=_client_ip(request),
            request_data={},
        )
        return Response(_issue_tokens(user), status=status.HTTP_200_OK)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(request=RegisterSerializer, responses={201: dict, 400: dict, 429: dict})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        is_blocked, msg = check_global_block(email)
        if is_blocked:
            return Response({'error': msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        can_send, cooldown_msg = can_request_email_code(email)
        if not can_send:
            return Response({'error': cooldown_msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        user = serializer.save()
        code = str(random.randint(100000, 999999))
        cache.set(f'email_otp:verify:{email}', code, timeout=300)
        set_email_cooldown(email)
        send_otp_email.delay(email, code, 'verification')

        UserActivityLog.objects.create(
            user=user,
            action_name='REGISTER',
            ip_address=_client_ip(request),
            request_data={'email': email},
        )

        return Response(
            {
                'message': 'Foydalanuvchi yaratildi. Tasdiqlash kodi emailga yuborildi.',
                'email': email,
            },
            status=status.HTTP_201_CREATED,
        )


class OwnerCustomerCreateView(APIView):
    permission_classes = [IsBusinessOwner]

    @extend_schema(request=OwnerCustomerCreateSerializer, responses={201: UserSerializer, 400: dict})
    def post(self, request):
        serializer = OwnerCustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.role = User.Role.CUSTOMER
        user.save(update_fields=['role'])
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailOTPView(APIView):
    """Ro‘yxatdan o‘tgach email kodini tasdiqlash."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(request=EmailCodeVerifySerializer, responses={200: dict, 400: dict, 429: dict})
    def post(self, request):
        serializer = EmailCodeVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        is_blocked, msg = check_global_block(email)
        if is_blocked:
            return Response({'error': msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        real = cache.get(f'email_otp:verify:{email}')
        if real != code:
            blocked = handle_failed_otp_attempt(email)
            if blocked:
                return Response(
                    {'error': f'Xato urinishlar oshdi. {blocked} daqiqaga bloklandingiz.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response({'error': 'Kod noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)

        clear_otp_attempts(email)
        cache.delete(f'email_otp:verify:{email}')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Foydalanuvchi topilmadi.'}, status=404)

        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])

        UserActivityLog.objects.create(
            user=user,
            action_name='EMAIL_VERIFIED',
            ip_address=_client_ip(request),
            request_data={},
        )
        return Response(
            {'message': 'Email tasdiqlandi.', **_issue_tokens(user)},
            status=status.HTTP_200_OK,
        )


class RequestLoginCodeView(APIView):
    """Emailga kirish kodi yuborish."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(request=EmailCodeRequestSerializer, responses={200: dict, 400: dict, 404: dict, 429: dict})
    def post(self, request):
        serializer = EmailCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data['email']
        is_blocked, msg = check_global_block(email)
        if is_blocked:
            return Response({'error': msg}, status=429)

        can_send, cooldown_msg = can_request_email_code(email)
        if not can_send:
            return Response({'error': cooldown_msg}, status=429)

        if not User.objects.filter(email=email).exists():
            return Response({'error': 'Bu email bilan foydalanuvchi topilmadi.'}, status=404)

        code = str(random.randint(100000, 999999))
        cache.set(f'email_otp:login:{email}', code, timeout=300)
        set_email_cooldown(email)
        send_otp_email.delay(email, code, 'login')
        return Response({'message': 'Kirish kodi emailga yuborildi.', 'email': email})


class VerifyLoginCodeView(APIView):
    """Email kod orqali kirish → JWT."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(request=EmailCodeVerifySerializer, responses={200: dict, 400: dict, 429: dict})
    def post(self, request):
        serializer = EmailCodeVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        is_blocked, msg = check_global_block(email)
        if is_blocked:
            return Response({'error': msg}, status=429)

        real = cache.get(f'email_otp:login:{email}')
        if real != code:
            blocked = handle_failed_otp_attempt(email)
            if blocked:
                return Response(
                    {'error': f'Xato urinishlar oshdi. {blocked} daqiqaga bloklandingiz.'},
                    status=429,
                )
            return Response({'error': 'Kod noto‘g‘ri.'}, status=400)

        clear_otp_attempts(email)
        cache.delete(f'email_otp:login:{email}')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Foydalanuvchi topilmadi.'}, status=404)

        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])

        UserActivityLog.objects.create(
            user=user,
            action_name='LOGIN_EMAIL_OTP',
            ip_address=_client_ip(request),
            request_data={},
        )
        return Response({'message': 'Muvaffaqiyatli kirdingiz.', **_issue_tokens(user)})


class RequestPasswordResetEmailView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(request=EmailCodeRequestSerializer, responses={200: dict, 400: dict, 404: dict, 429: dict})
    def post(self, request):
        serializer = EmailCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data['email']
        is_blocked, msg = check_global_block(email)
        if is_blocked:
            return Response({'error': msg}, status=429)

        can_send, cooldown_msg = can_request_email_code(email)
        if not can_send:
            return Response({'error': cooldown_msg}, status=429)

        if not User.objects.filter(email=email).exists():
            return Response({'error': 'Bu email bilan foydalanuvchi topilmadi.'}, status=404)

        code = str(random.randint(100000, 999999))
        cache.set(f'email_otp:reset:{email}', code, timeout=300)
        set_email_cooldown(email)
        send_otp_email.delay(email, code, 'password_reset')
        return Response({'message': 'Parolni tiklash kodi emailga yuborildi.'})


class ConfirmPasswordResetEmailView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: dict, 400: dict, 429: dict})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password']

        is_blocked, msg = check_global_block(email)
        if is_blocked:
            return Response({'error': msg}, status=429)

        real = cache.get(f'email_otp:reset:{email}')
        if real != code:
            blocked = handle_failed_otp_attempt(email)
            if blocked:
                return Response(
                    {'error': f'Ko‘p xato urinishlar. {blocked} daqiqaga bloklandingiz.'},
                    status=429,
                )
            return Response({'error': 'Kod noto‘g‘ri.'}, status=400)

        clear_otp_attempts(email)
        cache.delete(f'email_otp:reset:{email}')
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        UserActivityLog.objects.create(
            user=user,
            action_name='PASSWORD_RESET',
            ip_address=_client_ip(request),
            request_data={},
        )
        return Response({'message': 'Parol muvaffaqiyatli yangilandi.'})


class AuditLogListAPIView(APIView):
    permission_classes = [IsBusinessOwner]

    @extend_schema(responses={200: UserActivityLogSerializer(many=True)})
    def get(self, request):
        qs = UserActivityLog.objects.select_related('user').order_by('-timestamp')[:100]
        return Response(UserActivityLogSerializer(qs, many=True).data)
