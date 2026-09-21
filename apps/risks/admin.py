from django.contrib import admin

from .models import FinancialBalance, InactiveUserLog, ProductRiskMetric, RiskLog


@admin.register(RiskLog)
class RiskLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_app', 'risk_score', 'risk_level', 'created_at')
    list_filter = ('source_app', 'risk_level')
    search_fields = ('analysis_details',)


@admin.register(FinancialBalance)
class FinancialBalanceAdmin(admin.ModelAdmin):
    list_display = ('month_year', 'total_inflow', 'total_outflow', 'net_profit', 'updated_at')


@admin.register(ProductRiskMetric)
class ProductRiskMetricAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name', 'category_name', 'current_price', 'stock_quantity')
    search_fields = ('product_name', 'category_name')


@admin.register(InactiveUserLog)
class InactiveUserLogAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'username', 'inactive_days', 'updated_at')
