from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.api.dependencies import DatabaseSession
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services import payments

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": PaymentResponse}, 404: {"description": "Tariff not found"}},
)
async def create_payment(
    data: PaymentCreate,
    response: Response,
    session: DatabaseSession,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=255)
    ] = None,
) -> PaymentResponse:
    try:
        payment, created = await payments.create_payment(session, data, idempotency_key)
    except payments.TariffNotFound:
        raise HTTPException(status_code=404, detail="Tariff not found") from None
    if not created:
        response.status_code = status.HTTP_200_OK
    return PaymentResponse.model_validate(payment)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: UUID, session: DatabaseSession) -> PaymentResponse:
    try:
        payment = await payments.get_payment(session, payment_id)
    except payments.PaymentNotFound:
        raise HTTPException(status_code=404, detail="Payment not found") from None
    return PaymentResponse.model_validate(payment)
