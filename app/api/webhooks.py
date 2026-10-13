from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import DatabaseSession
from app.schemas.webhook import BankWebhook, BankWebhookResponse, InvalidTransitionResponse
from app.services import payments

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/bank",
    response_model=BankWebhookResponse,
    responses={409: {"model": InvalidTransitionResponse}},
)
async def bank_webhook(
    data: BankWebhook, session: DatabaseSession
) -> BankWebhookResponse | JSONResponse:
    try:
        await payments.change_status(session, data.payment_id, data.status)
    except payments.PaymentNotFound:
        raise HTTPException(status_code=404, detail="Payment not found") from None
    except payments.InvalidTransition:
        return JSONResponse(
            status_code=409, content=InvalidTransitionResponse().model_dump()
        )
    return BankWebhookResponse()
