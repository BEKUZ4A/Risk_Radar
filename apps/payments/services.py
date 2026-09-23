import logging
from decimal import Decimal
from uuid import uuid4

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import F

from apps.catalog.models import Product
from apps.risks.models import FinancialBalance
from apps.risks.services import RiskEngineService
from django.utils import timezone

from .models import Payment

logger = logging.getLogger(__name__)


class StripePaymentService:
    """
    EMPLOYEE Stripe to‘lovi:
    - Muvaffaqiyatli + DB da SUCCEEDED bo‘lsa → ombor kamayadi
    - Aks holda → ombor o‘zgarmaydi, employee ga xato
    """

    @staticmethod
    def _configure():
        secret = settings.STRIPE_SECRET_KEY
        if not secret:
            raise RuntimeError('STRIPE_SECRET_KEY sozlanmagan.')
        stripe.api_key = secret

    @classmethod
    def charge_and_fulfill(
        cls,
        *,
        employee,
        product_id: int,
        quantity: int,
        payment_method_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Payment:
        cls._configure()
        idempotency_key = idempotency_key or uuid4().hex

        if quantity < 1:
            raise ValueError('Miqdor 1 dan kam bo‘lishi mumkin emas.')

        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

        product = Product.objects.filter(pk=product_id, is_active=True).first()
        if not product:
            raise ValueError('Mahsulot topilmadi yoki faol emas.')

        if product.stock_quantity < quantity:
            raise ValueError(
                f'Ombor yetarli emas. Mavjud: {product.stock_quantity}, so‘ralgan: {quantity}.'
            )

        unit_price = Decimal(product.price)
        amount_total = (unit_price * quantity).quantize(Decimal('0.01'))
        amount_cents = int(amount_total * 100)
        if amount_cents < 50:
            raise ValueError('Stripe uchun minimal summa juda kichik.')

        payment = Payment.objects.create(
            employee=employee,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            amount_total=amount_total,
            currency='usd',
            status=Payment.Status.PENDING,
            idempotency_key=idempotency_key,
        )

        try:
            intent_params = {
                'amount': amount_cents,
                'currency': 'usd',
                'confirm': True,
                'automatic_payment_methods': {'enabled': True, 'allow_redirects': 'never'},
                'metadata': {
                    'payment_id': str(payment.id),
                    'product_id': str(product.id),
                    'quantity': str(quantity),
                    'employee_id': str(employee.id),
                },
            }
            if payment_method_id:
                intent_params['payment_method'] = payment_method_id
            else:
                # Test: Stripe test payment method (pm_card_visa) — frontend odatda yuboradi
                intent_params['payment_method'] = 'pm_card_visa'

            intent = stripe.PaymentIntent.create(
                **intent_params,
                idempotency_key=idempotency_key,
            )
            payment.stripe_payment_intent_id = intent.id
            payment.raw_stripe_response = {'id': intent.id, 'status': intent.status}
            payment.save(update_fields=['stripe_payment_intent_id', 'raw_stripe_response', 'updated_at'])

            # Stripe dan qayta o‘qib statusni tekshirish (DB da pul ko‘rinishi)
            refreshed = stripe.PaymentIntent.retrieve(intent.id)
            payment.raw_stripe_response = {'id': refreshed.id, 'status': refreshed.status}

            if refreshed.status != 'succeeded':
                payment.status = Payment.Status.FAILED
                payment.error_message = (
                    f"To‘lov tasdiqlanmadi. Stripe status: {refreshed.status}. "
                    'Ombor o‘zgartirilmadi.'
                )
                payment.save()
                return payment

            # Charge id (agar bor bo‘lsa)
            latest = refreshed.to_dict()
            charges = latest.get('charges') or {}
            charge_data = charges.get('data') or []
            if charge_data:
                payment.stripe_charge_id = charge_data[0].get('id', '')
            else:
                payment.stripe_charge_id = latest.get('latest_charge') or ''

            # Faqat SUCCEEDED + DB yozuvi OK bo‘lganda omborni kamaytirish
            with transaction.atomic():
                locked = Product.objects.select_for_update().get(pk=product.id)
                if locked.stock_quantity < quantity:
                    payment.status = Payment.Status.FAILED
                    payment.error_message = (
                        'To‘lov Stripe da OK, lekin ombor yetarli emas — stock kamaytirilmadi.'
                    )
                    payment.save()
                    # To‘lov allaqachon olingan — realda refund kerak; xabar beramiz
                    try:
                        stripe.Refund.create(payment_intent=intent.id)
                        payment.error_message += ' Avtomatik refund qilindi.'
                        payment.save(update_fields=['error_message', 'updated_at'])
                    except Exception as refund_exc:
                        logger.exception('Refund xatosi: %s', refund_exc)
                    return payment

                locked.stock_quantity = F('stock_quantity') - quantity
                locked.save(update_fields=['stock_quantity', 'updated_at'])
                locked.refresh_from_db()

                payment.status = Payment.Status.SUCCEEDED
                payment.stock_decremented = True
                payment.error_message = ''
                payment.save()

                month = timezone.now().strftime('%Y-%m')
                fin, _ = FinancialBalance.objects.get_or_create(month_year=month)
                fin.total_inflow = F('total_inflow') + amount_total
                fin.save(update_fields=['total_inflow', 'updated_at'])
                fin.refresh_from_db()
                fin.net_profit = fin.total_inflow - fin.total_outflow
                fin.save(update_fields=['net_profit', 'updated_at'])

                # Avtomatik risk algoritmi (stock + savdo)
                RiskEngineService.process_payment_event(
                    product=locked,
                    quantity=quantity,
                    amount_total=float(amount_total),
                    payment_id=payment.id,
                    stock_after=locked.stock_quantity,
                )

            return payment

        except stripe.error.StripeError as exc:
            payment.status = Payment.Status.FAILED
            payment.error_message = 'To‘lov provayderi xatosi. Qayta urinib ko‘ring.'
            payment.save()
            logger.warning('Stripe payment failed: %s', exc)
            return payment
        except Exception as exc:
            payment.status = Payment.Status.FAILED
            payment.error_message = 'To‘lovni qayta ishlashda tizim xatosi yuz berdi.'
            payment.save()
            logger.exception('Payment unexpected error')
            return payment
