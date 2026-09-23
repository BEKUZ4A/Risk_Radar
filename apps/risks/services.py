from datetime import timedelta

from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Product

from .algorithm import (
    RiskResult,
    classify_level,
    evaluate_business_snapshot,
    evaluate_customer_event,
    evaluate_employee_event,
    evaluate_payment_stock_event,
)
from .models import FinancialBalance, InactiveUserLog, ProductRiskMetric, RiskLog


class RiskEngineService:
    """
    Markaziy Risk Dvigateli:
    - algorithm.py qoidalariga asosan skorlaydi (0–100)
    - 2 oylik P&L agregatini yangilaydi
    - Dashboard / Local AI uchun yagona JSON beradi
    """

    @staticmethod
    def _json_safe(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {key: RiskEngineService._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [RiskEngineService._json_safe(item) for item in value]
        return value

    @staticmethod
    def _persist_log(
        *,
        source_app: str,
        payload: dict,
        result: RiskResult,
    ) -> RiskLog:
        return RiskLog.objects.create(
            source_app=source_app,
            payload_json=RiskEngineService._json_safe(payload),
            risk_score=result.score,
            risk_level=result.level,
            analysis_details=result.analysis_text,
        )

    @staticmethod
    def process_employee_json(data: dict) -> RiskLog:
        price = float(data.get('price', 0))
        old_price_raw = data.get('old_price')
        old_price = float(old_price_raw) if old_price_raw is not None else None
        stock = int(data.get('stock_quantity', 0) or 0)

        result = evaluate_employee_event(
            price=price,
            old_price=old_price if old_price is not None else price,
            stock_quantity=stock,
        )

        ProductRiskMetric.objects.update_or_create(
            product_id=data.get('product_id') or 0,
            defaults={
                'product_name': data.get('product_name', ''),
                'category_name': data.get('category_name', ''),
                'current_price': price,
                'stock_quantity': stock,
                'raw_metric_json': data,
            },
        )

        return RiskEngineService._persist_log(
            source_app=RiskLog.SourceApp.EMPLOYEE_APP,
            payload=data,
            result=result,
        )

    @staticmethod
    def process_customer_json(data: dict) -> RiskLog:
        inflow = Decimal(data.get('inflow_amount', 0) or 0)
        outflow = Decimal(data.get('outflow_amount', 0) or 0)
        inactive_users = data.get('inactive_users_15days') or []

        for u in inactive_users:
            uid = u.get('user_id')
            if uid is None:
                continue
            InactiveUserLog.objects.update_or_create(
                user_id=uid,
                defaults={
                    'username': u.get('username', 'Unknown'),
                    'inactive_days': u.get('inactive_days', 15),
                    'details_json': u,
                },
            )

        current_month = timezone.now().strftime('%Y-%m')
        with transaction.atomic():
            fin_obj, _ = FinancialBalance.objects.select_for_update().get_or_create(
                month_year=current_month
            )
            fin_obj.total_inflow = F('total_inflow') + inflow
            fin_obj.total_outflow = F('total_outflow') + outflow
            fin_obj.save(update_fields=['total_inflow', 'total_outflow', 'updated_at'])
            fin_obj.refresh_from_db()
            fin_obj.net_profit = fin_obj.total_inflow - fin_obj.total_outflow
            fin_obj.save(update_fields=['net_profit', 'updated_at'])

        result = evaluate_customer_event(
            inflow_amount=inflow,
            outflow_amount=outflow,
            inactive_users_count=len(inactive_users),
        )

        return RiskEngineService._persist_log(
            source_app=RiskLog.SourceApp.CUSTOMER_APP,
            payload=data,
            result=result,
        )

    @staticmethod
    def process_payment_event(
        *,
        product,
        quantity: int,
        amount_total: float,
        payment_id: int,
        stock_after: int,
    ) -> RiskLog:
        """Stripe checkout muvaffaqiyatidan keyin avtomatik risk."""
        result = evaluate_payment_stock_event(
            product_name=product.name,
            stock_after=stock_after,
            quantity_sold=quantity,
            amount_total=float(amount_total),
        )
        payload = {
            'payment_id': payment_id,
            'product_id': product.id,
            'product_name': product.name,
            'category_name': product.category.name,
            'quantity': quantity,
            'amount_total': float(amount_total),
            'stock_after': stock_after,
            'price': float(product.price),
        }
        ProductRiskMetric.objects.update_or_create(
            product_id=product.id,
            defaults={
                'product_name': product.name,
                'category_name': product.category.name,
                'current_price': product.price,
                'stock_quantity': stock_after,
                'raw_metric_json': payload,
            },
        )
        return RiskEngineService._persist_log(
            source_app=RiskLog.SourceApp.EMPLOYEE_APP,
            payload=payload,
            result=result,
        )

    @staticmethod
    def process_catalog_product_change(
        *,
        product,
        old_price=None,
        action: str = 'UPDATE',
    ) -> RiskLog:
        """Katalog mahsulot yaratish/yangilashda risk."""
        result = evaluate_employee_event(
            price=float(product.price),
            old_price=float(old_price) if old_price is not None else float(product.price),
            stock_quantity=int(product.stock_quantity),
        )
        payload = {
            'action': action,
            'product_id': product.id,
            'product_name': product.name,
            'category_name': product.category.name,
            'price': float(product.price),
            'old_price': float(old_price) if old_price is not None else None,
            'stock_quantity': product.stock_quantity,
        }
        ProductRiskMetric.objects.update_or_create(
            product_id=product.id,
            defaults={
                'product_name': product.name,
                'category_name': product.category.name,
                'current_price': product.price,
                'stock_quantity': product.stock_quantity,
                'raw_metric_json': payload,
            },
        )
        return RiskEngineService._persist_log(
            source_app=RiskLog.SourceApp.EMPLOYEE_APP,
            payload=payload,
            result=result,
        )

    @staticmethod
    def evaluate_current_business() -> tuple[RiskResult, RiskLog]:
        """Joriy DB holatidan to‘liq biznes risk skori."""
        low_stock = list(
            Product.objects.filter(is_active=True, stock_quantity__lte=5).values(
                'id', 'name', 'stock_quantity'
            )
        )
        month = timezone.now().strftime('%Y-%m')
        fin = FinancialBalance.objects.filter(month_year=month).first()
        since = timezone.now() - timedelta(hours=24)
        failed_payments = 0
        try:
            from apps.payments.models import Payment

            failed_payments = Payment.objects.filter(
                status=Payment.Status.FAILED,
                created_at__gte=since,
            ).count()
        except Exception:
            failed_payments = 0

        snapshot = {
            'low_stock_products': [
                {'name': p['name'], 'stock': p['stock_quantity']} for p in low_stock
            ],
            'month_inflow': float(fin.total_inflow) if fin else 0,
            'month_outflow': float(fin.total_outflow) if fin else 0,
            'inactive_users_count': InactiveUserLog.objects.count(),
            'failed_payments_24h': failed_payments,
        }
        result = evaluate_business_snapshot(snapshot)
        log = RiskEngineService._persist_log(
            source_app=RiskLog.SourceApp.EMPLOYEE_APP,
            payload={'type': 'BUSINESS_SNAPSHOT', **snapshot},
            result=result,
        )
        return result, log

    @staticmethod
    def generate_unified_dashboard_json() -> dict:
        months = FinancialBalance.objects.order_by('-month_year')[:2]
        fin_data = {
            m.month_year: {
                'inflow': float(m.total_inflow),
                'outflow': float(m.total_outflow),
                'net_profit': float(m.net_profit),
            }
            for m in months
        }

        products = list(
            ProductRiskMetric.objects.values(
                'product_id',
                'product_name',
                'category_name',
                'current_price',
                'stock_quantity',
            )
        )
        for p in products:
            p['current_price'] = float(p['current_price'])

        inactive = list(
            InactiveUserLog.objects.values('user_id', 'username', 'inactive_days')
        )

        logs = list(
            RiskLog.objects.order_by('-created_at')[:10].values(
                'source_app',
                'risk_score',
                'risk_level',
                'analysis_details',
                'created_at',
            )
        )
        for log in logs:
            log['created_at'] = log['created_at'].isoformat()

        avg_score = int(sum(l['risk_score'] for l in logs) / len(logs)) if logs else 0

        # Live catalog low-stock preview
        live_low = list(
            Product.objects.filter(is_active=True, stock_quantity__lte=5).values(
                'id', 'name', 'stock_quantity', 'price'
            )
        )

        return {
            'summary_date': timezone.now().isoformat(),
            'overall_risk_score': avg_score,
            'risk_level': classify_level(avg_score),
            'algorithm_rules': {
                'PRICE_ANOMALY': '+40 if price drop > 30%',
                'INVENTORY_DEPLETION': '+25 if stock <= 5',
                'CASHFLOW_IMBALANCE': '+35 if outflow > inflow',
                'CUSTOMER_CHURN': '+20 if inactive users > 10',
                'LARGE_SALE': '+15 if quantity sold >= 10',
                'levels': {'GREEN': '<30', 'YELLOW': '30-69', 'RED': '>=70'},
            },
            'two_month_financials': fin_data,
            'product_stock_analytics': products,
            'live_low_stock_products': live_low,
            'inactive_users_list': inactive,
            'recent_risk_logs': logs,
        }
