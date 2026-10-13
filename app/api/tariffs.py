from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import DatabaseSession
from app.models.tariff import Tariff
from app.schemas.tariff import TariffResponse

router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("", response_model=list[TariffResponse])
async def list_tariffs(session: DatabaseSession) -> list[TariffResponse]:
    tariffs = await session.scalars(select(Tariff).order_by(Tariff.price, Tariff.id))
    return [TariffResponse.model_validate(tariff) for tariff in tariffs]
