from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.users.permissions import IsBusinessOwner, IsCustomer, IsEmployee
from apps.users.models import UserActivityLog

from .serializers import (
    CustomerPayloadSerializer,
    DashboardUnifiedJSONSerializer,
    EmployeePayloadSerializer,
    RiskLogSerializer,
)
from .services import RiskEngineService


def _client_ip(request):
    return request.META.get('REMOTE_ADDR')


def _audit(request, action_name: str, payload):
    if request.user and request.user.is_authenticated:
        UserActivityLog.objects.create(
            user=request.user,
            action_name=action_name,
            ip_address=_client_ip(request),
            request_data=payload if isinstance(payload, dict) else {'raw': str(payload)},
        )


class EmployeeDataIngestAPIView(APIView):
    """Xodim JSON ingest + real-time risk scoring. EMPLOYEE only."""

    permission_classes = [IsEmployee]

    @extend_schema(request=EmployeePayloadSerializer, responses={201: RiskLogSerializer})
    def post(self, request):
        serializer = EmployeePayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        # Decimal -> JSON-safe
        payload = {
            **data,
            'price': float(data['price']),
            'old_price': float(data['old_price']) if data.get('old_price') is not None else None,
        }
        risk_log = RiskEngineService.process_employee_json(payload)
        _audit(request, data.get('action', 'EMPLOYEE_INGEST'), payload)
        return Response(RiskLogSerializer(risk_log).data, status=status.HTTP_201_CREATED)


class CustomerDataIngestAPIView(APIView):
    """Mijoz JSON ingest (moliya + churn). CUSTOMER only."""

    permission_classes = [IsCustomer]

    @extend_schema(request=CustomerPayloadSerializer, responses={201: RiskLogSerializer})
    def post(self, request):
        serializer = CustomerPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        payload = {
            **data,
            'total_amount': float(data.get('total_amount') or 0),
            'inflow_amount': float(data.get('inflow_amount') or 0),
            'outflow_amount': float(data.get('outflow_amount') or 0),
        }
        risk_log = RiskEngineService.process_customer_json(payload)
        _audit(request, 'CUSTOMER_INGEST', payload)
        return Response(RiskLogSerializer(risk_log).data, status=status.HTTP_201_CREATED)


class UnifiedDashboardJSONAPIView(APIView):
    """Yagona dashboard JSON. OWNER only."""

    permission_classes = [IsBusinessOwner]

    @extend_schema(responses={200: DashboardUnifiedJSONSerializer})
    def get(self, request):
        unified_json = RiskEngineService.generate_unified_dashboard_json()
        _audit(request, 'DASHBOARD_JSON_VIEW', {})
        return Response(unified_json, status=status.HTTP_200_OK)


class EvaluateBusinessRiskAPIView(APIView):
    """Joriy biznes holatini risk algoritmi bilan baholash. OWNER/root."""

    permission_classes = [IsBusinessOwner]

    def post(self, request):
        result, log = RiskEngineService.evaluate_current_business()
        _audit(request, 'BUSINESS_RISK_EVALUATE', {'score': result.score, 'level': result.level})
        return Response(
            {
                'risk_score': result.score,
                'risk_level': result.level,
                'signals': [
                    {'code': s.code, 'points': s.points, 'message': s.message}
                    for s in result.signals
                ],
                'analysis': result.analysis_text,
                'risk_log_id': log.id,
            },
            status=status.HTTP_200_OK,
        )
