import random

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User, UserActivityLog
from apps.users.permissions import IsBusinessOwner
from apps.users.serializers import (
    RegisterSerializer,
    EmailCodeRequestSerializer,
    EmailCodeVerifySerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
    UserActivityLogSerializer,
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


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

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


class VerifyEmailOTPView(APIView):
    """Ro‘yxatdan o‘tgach email kodini tasdiqlash."""

    authentication_classes = []
    permission_classes = []

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

    def get(self, request):
        qs = UserActivityLog.objects.select_related('user').order_by('-timestamp')[:100]
        return Response(UserActivityLogSerializer(qs, many=True).data)
