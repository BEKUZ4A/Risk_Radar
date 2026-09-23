from rest_framework import serializers

from .models import Payment


class CheckoutSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    payment_method_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Stripe PaymentMethod id (masalan pm_card_visa). Bo‘sh bo‘lsa test pm_card_visa.',
    )
    idempotency_key = serializers.CharField(max_length=255, required=True)


class PaymentSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'employee',
            'product',
            'product_name',
            'quantity',
            'unit_price',
            'amount_total',
            'currency',
            'status',
            'stripe_payment_intent_id',
            'stripe_charge_id',
            'error_message',
            'stock_decremented',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
