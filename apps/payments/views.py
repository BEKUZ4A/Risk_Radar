from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.users.models import UserActivityLog
from apps.users.permissions import IsEmployeeOrOwner

from .models import Payment
from .serializers import CheckoutSerializer, PaymentSerializer
from .services import StripePaymentService


def _client_ip(request):
    return request.META.get('REMOTE_ADDR')


class EmployeeCheckoutAPIView(APIView):
    """
    EMPLOYEE Stripe to‘lov:
    OK → ombor kamayadi.
    Fail / DB da tasdiqlanmasa → ombor o‘zgarmaydi, error qaytadi.
    """

    permission_classes = [IsEmployeeOrOwner]

    @extend_schema(request=CheckoutSerializer, responses={200: PaymentSerializer, 400: dict})
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            payment = StripePaymentService.charge_and_fulfill(
                employee=request.user,
                product_id=data['product_id'],
                quantity=data['quantity'],
                payment_method_id=data.get('payment_method_id') or None,
                idempotency_key=data['idempotency_key'],
            )
        except ValueError as exc:
            UserActivityLog.objects.create(
                user=request.user,
                action_name='PAYMENT_REJECTED',
                ip_address=_client_ip(request),
                request_data={'error': str(exc), **data},
            )
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        UserActivityLog.objects.create(
            user=request.user,
            action_name=f'PAYMENT_{payment.status}',
            ip_address=_client_ip(request),
            request_data={
                'payment_id': payment.id,
                'product_id': payment.product_id,
                'quantity': payment.quantity,
                'status': payment.status,
            },
        )

        payload = PaymentSerializer(payment).data
        if payment.status != Payment.Status.SUCCEEDED:
            return Response(
                {
                    'error': payment.error_message or 'To‘lov muvaffaqiyatsiz. Ombor o‘zgartirilmadi.',
                    'payment': payload,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        return Response(
            {
                'message': 'To‘lov muvaffaqiyatli. Ombor yangilandi.',
                'payment': payload,
            },
            status=status.HTTP_200_OK,
        )


class EmployeePaymentListAPIView(APIView):
    permission_classes = [IsEmployeeOrOwner]

    @extend_schema(responses={200: PaymentSerializer(many=True)})
    def get(self, request):
        qs = Payment.objects.filter(employee=request.user).select_related('product')[:50]
        return Response(PaymentSerializer(qs, many=True).data)
