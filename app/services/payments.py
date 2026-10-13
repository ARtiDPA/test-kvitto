from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.tariff import Tariff
from app.schemas.payment import PaymentCreate
from app.services.pricing import build_schedule, calculate_amount


class PaymentNotFound(Exception):
    pass


class TariffNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


ALLOWED_TRANSITIONS = {
    PaymentStatus.PENDING: {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED},
    PaymentStatus.SUCCEEDED: {PaymentStatus.REFUNDED},
    PaymentStatus.FAILED: set(),
    PaymentStatus.REFUNDED: set(),
}


async def get_payment(session: AsyncSession, payment_id: UUID) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise PaymentNotFound
    return payment


async def create_payment(
    session: AsyncSession,
    data: PaymentCreate,
    idempotency_key: str | None,
) -> tuple[Payment, bool]:
    """Return the payment and whether this request created it."""
    async with session.begin():
        existing_query = select(Payment).where(
            Payment.idempotency_key == idempotency_key
        )
        if idempotency_key is not None:
            existing = await session.scalar(existing_query)
            if existing is not None:
                return existing, False

        tariff = await session.get(Tariff, data.tariff_id)
        if tariff is None:
            raise TariffNotFound

        amount, discount = calculate_amount(tariff.price, data.promo_code)
        schedule = (
            build_schedule(amount, data.installment_months)
            if data.method == PaymentMethod.INSTALLMENT
            and data.installment_months is not None
            else None
        )
        statement = insert(Payment).values(
            tariff_id=tariff.id,
            email=str(data.email),
            status=PaymentStatus.PENDING,
            amount=amount,
            discount=discount,
            method=data.method,
            installment_months=data.installment_months,
            schedule=schedule,
            idempotency_key=idempotency_key,
        )
        if idempotency_key is not None:
            statement = statement.on_conflict_do_nothing(
                index_elements=[Payment.idempotency_key]
            )
        result = await session.execute(statement.returning(Payment))
        payment = result.scalar_one_or_none()
        if payment is not None:
            return payment, True

        # ON CONFLICT waits for the competing insert to commit. A new SELECT
        # sees that row under PostgreSQL's default READ COMMITTED isolation.
        existing = (await session.execute(existing_query)).scalar_one()
        return existing, False


async def change_status(
    session: AsyncSession,
    payment_id: UUID,
    new_status: PaymentStatus,
) -> None:
    async with session.begin():
        payment = await session.scalar(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        if payment is None:
            raise PaymentNotFound
        if new_status not in ALLOWED_TRANSITIONS[payment.status]:
            raise InvalidTransition
        payment.status = new_status
