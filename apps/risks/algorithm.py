"""
Central Risk Engine — deterministic scoring algorithm (0–100).

Rules (from architecture spec):
  +40  Price anomaly: price drop > 30% vs old_price
  +25  Inventory depletion: stock_quantity <= 5
  +35  Cash-flow imbalance: outflow_amount > inflow_amount
  +20  Customer churn: inactive users (>15 days) count > 10

Classification:
  GREEN  score < 30
  YELLOW score 30–69
  RED    score >= 70
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RiskSignal:
    code: str
    points: int
    message: str


@dataclass
class RiskResult:
    score: int
    level: str
    signals: list[RiskSignal] = field(default_factory=list)

    @property
    def analysis_text(self) -> str:
        if not self.signals:
            return 'Normal operatsiya — risk signal topilmadi'
        return '; '.join(s.message for s in self.signals)


def classify_level(score: int) -> str:
    score = max(0, min(100, int(score)))
    if score >= 70:
        return 'RED'
    if score >= 30:
        return 'YELLOW'
    return 'GREEN'


def score_price_anomaly(price: float, old_price: float | None) -> RiskSignal | None:
    if old_price is None:
        return None
    old = float(old_price)
    new = float(price)
    if old > 0 and new < old * 0.7:
        drop_pct = round((1 - new / old) * 100, 1)
        return RiskSignal(
            code='PRICE_ANOMALY',
            points=40,
            message=f'Keskin narx tushishi ({drop_pct}%): {old} -> {new}',
        )
    return None


def score_inventory_depletion(stock_quantity: int) -> RiskSignal | None:
    stock = int(stock_quantity)
    if stock <= 5:
        return RiskSignal(
            code='INVENTORY_DEPLETION',
            points=25,
            message=f'Zaxira kritik darajada: {stock} ta qoldi',
        )
    return None


def score_cashflow_imbalance(inflow: float, outflow: float) -> RiskSignal | None:
    inflow = float(inflow or 0)
    outflow = float(outflow or 0)
    if outflow > inflow:
        return RiskSignal(
            code='CASHFLOW_IMBALANCE',
            points=35,
            message=f'Xarajat tushumdan yuqori: Out={outflow}, In={inflow}',
        )
    return None


def score_customer_churn(inactive_count: int) -> RiskSignal | None:
    count = int(inactive_count or 0)
    if count > 10:
        return RiskSignal(
            code='CUSTOMER_CHURN',
            points=20,
            message=f'Passiv mijozlar (15+ kun) ko‘p: {count} ta',
        )
    return None


def evaluate_employee_event(
    *,
    price: float,
    old_price: float | None,
    stock_quantity: int,
) -> RiskResult:
    signals: list[RiskSignal] = []
    for sig in (
        score_price_anomaly(price, old_price),
        score_inventory_depletion(stock_quantity),
    ):
        if sig:
            signals.append(sig)
    score = min(100, sum(s.points for s in signals))
    return RiskResult(score=score, level=classify_level(score), signals=signals)


def evaluate_customer_event(
    *,
    inflow_amount: float,
    outflow_amount: float,
    inactive_users_count: int,
) -> RiskResult:
    signals: list[RiskSignal] = []
    for sig in (
        score_cashflow_imbalance(inflow_amount, outflow_amount),
        score_customer_churn(inactive_users_count),
    ):
        if sig:
            signals.append(sig)
    score = min(100, sum(s.points for s in signals))
    return RiskResult(score=score, level=classify_level(score), signals=signals)


def evaluate_payment_stock_event(
    *,
    product_name: str,
    stock_after: int,
    quantity_sold: int,
    amount_total: float,
) -> RiskResult:
    """Stripe to‘lovdan keyin ombor holati bo‘yicha risk."""
    signals: list[RiskSignal] = []
    inv = score_inventory_depletion(stock_after)
    if inv:
        signals.append(inv)
    if quantity_sold >= 10:
        signals.append(
            RiskSignal(
                code='LARGE_SALE',
                points=15,
                message=f'Katta savdo: {product_name} x{quantity_sold} (summa={amount_total})',
            )
        )
    score = min(100, sum(s.points for s in signals))
    return RiskResult(score=score, level=classify_level(score), signals=signals)


def evaluate_business_snapshot(snapshot: dict[str, Any]) -> RiskResult:
    """
    Butun biznes holati bo‘yicha agregat risk:
    - past stock mahsulotlar
    - oylik cashflow
    - inactive users
    """
    signals: list[RiskSignal] = []

    low_stock = snapshot.get('low_stock_products') or []
    if low_stock:
        names = ', '.join(p.get('name', '?') for p in low_stock[:5])
        signals.append(
            RiskSignal(
                code='MULTI_LOW_STOCK',
                points=min(40, 10 + 5 * len(low_stock)),
                message=f'Kam zaxirali mahsulotlar ({len(low_stock)}): {names}',
            )
        )

    inflow = float(snapshot.get('month_inflow') or 0)
    outflow = float(snapshot.get('month_outflow') or 0)
    cash = score_cashflow_imbalance(inflow, outflow)
    if cash:
        signals.append(cash)

    inactive = int(snapshot.get('inactive_users_count') or 0)
    churn = score_customer_churn(inactive)
    if churn:
        signals.append(churn)

    failed_payments = int(snapshot.get('failed_payments_24h') or 0)
    if failed_payments >= 3:
        signals.append(
            RiskSignal(
                code='PAYMENT_FAILURES',
                points=20,
                message=f'So‘nggi 24 soatda muvaffaqiyatsiz to‘lovlar: {failed_payments}',
            )
        )

    score = min(100, sum(s.points for s in signals))
    return RiskResult(score=score, level=classify_level(score), signals=signals)
