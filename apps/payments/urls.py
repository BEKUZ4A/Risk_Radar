from django.urls import path

from .views import EmployeeCheckoutAPIView, EmployeePaymentListAPIView

urlpatterns = [
    path('checkout/', EmployeeCheckoutAPIView.as_view(), name='employee-checkout'),
    path('my/', EmployeePaymentListAPIView.as_view(), name='employee-payments'),
]
