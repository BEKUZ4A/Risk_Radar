from django.db import models


class RiskLog(models.Model):
    """Har bir ingest hodisasi uchun risk balli va tahlil yozuvi."""

    class SourceApp(models.TextChoices):
        EMPLOYEE_APP = 'EMPLOYEE_APP', 'Employee App'
        CUSTOMER_APP = 'CUSTOMER_APP', 'Customer App'

    class RiskLevel(models.TextChoices):
        GREEN = 'GREEN', 'Low Risk'
        YELLOW = 'YELLOW', 'Medium Risk'
        RED = 'RED', 'Critical Risk'

    source_app = models.CharField(max_length=32, choices=SourceApp.choices, db_index=True)
    payload_json = models.JSONField()
    risk_score = models.PositiveSmallIntegerField(db_index=True)
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, db_index=True)
    analysis_details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'risk_level']),
            models.Index(fields=['source_app', '-created_at']),
        ]

    def __str__(self):
        return f"{self.source_app} {self.risk_level} ({self.risk_score})"


class FinancialBalance(models.Model):
    """Oylik kirim/chiqim va sof foyda agregati."""

    month_year = models.CharField(max_length=7, unique=True, help_text='YYYY-MM')
    total_inflow = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_outflow = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month_year']

    def __str__(self):
        return f"{self.month_year}: net={self.net_profit}"


class ProductRiskMetric(models.Model):
    """Mahsulot bo'yicha joriy narx va zaxira holati."""

    product_id = models.PositiveIntegerField(unique=True, db_index=True)
    product_name = models.CharField(max_length=255)
    category_name = models.CharField(max_length=100, blank=True)
    current_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)
    raw_metric_json = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product_name']

    def __str__(self):
        return f"{self.product_name} (#{self.product_id})"


class InactiveUserLog(models.Model):
    """15+ kun faol bo'lmagan mijozlar ombori."""

    user_id = models.PositiveIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=150)
    inactive_days = models.PositiveIntegerField(default=15)
    details_json = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-inactive_days']

    def __str__(self):
        return f"{self.username} ({self.inactive_days}d)"
