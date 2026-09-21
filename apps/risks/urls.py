from django.urls import path

from .views import (
    CustomerDataIngestAPIView,
    EmployeeDataIngestAPIView,
    UnifiedDashboardJSONAPIView,
    EvaluateBusinessRiskAPIView,
)

urlpatterns = [
    path('ingest/employee/', EmployeeDataIngestAPIView.as_view(), name='ingest-employee'),
    path('ingest/customer/', CustomerDataIngestAPIView.as_view(), name='ingest-customer'),
    path('dashboard-json/', UnifiedDashboardJSONAPIView.as_view(), name='unified-dashboard-json'),
    path('evaluate/', EvaluateBusinessRiskAPIView.as_view(), name='evaluate-business-risk'),
]
