from rest_framework import serializers

from .models import RiskLog


class EmployeePayloadSerializer(serializers.Serializer):
    ACTION_CHOICES = ('CREATE', 'UPDATE', 'DELETE', 'PRICE_CHANGE')

    employee_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    category_name = serializers.CharField(max_length=100)
    product_id = serializers.IntegerField(required=False, allow_null=True)
    product_name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    old_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=0
    )
    stock_quantity = serializers.IntegerField(default=0, min_value=0)

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Narx manfiy bo‘lishi mumkin emas.')
        return value


class CustomerPayloadSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(required=False, allow_null=True)
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    items = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    total_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=0, min_value=0
    )
    inflow_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=0, min_value=0
    )
    outflow_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=0, min_value=0
    )
    inactive_users_15days = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )


class RiskLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskLog
        fields = '__all__'


class DashboardUnifiedJSONSerializer(serializers.Serializer):
    summary_date = serializers.CharField()
    overall_risk_score = serializers.IntegerField()
    risk_level = serializers.CharField()
    two_month_financials = serializers.DictField()
    product_stock_analytics = serializers.ListField()
    inactive_users_list = serializers.ListField()
    recent_risk_logs = serializers.ListField()
