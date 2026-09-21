from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'employee',
        'product',
        'quantity',
        'amount_total',
        'status',
        'stock_decremented',
        'created_at',
    )
    list_filter = ('status', 'stock_decremented')
    search_fields = ('stripe_payment_intent_id', 'employee__email')
