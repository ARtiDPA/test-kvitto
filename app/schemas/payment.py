from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.payment import PaymentMethod, PaymentStatus


class PaymentCreate(BaseModel):
    tariff_id: str = Field(min_length=1, max_length=32)
    email: EmailStr
    method: PaymentMethod
    installment_months: Literal[3, 6, 12] | None = None
    promo_code: str | None = None

    @field_validator("promo_code")
    @classmethod
    def validate_promo_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.upper() != "KVITTO10":
            raise ValueError("Unknown promo code")
        return value.upper()

    @model_validator(mode="after")
    def validate_installment(self) -> Self:
        if self.method == PaymentMethod.INSTALLMENT:
            if self.installment_months is None:
                raise ValueError("installment_months is required for installment payments")
        elif self.installment_months is not None:
            raise ValueError("installment_months is only allowed for installment payments")
        return self


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: PaymentStatus
    tariff_id: str
    amount: int
    discount: int
    method: PaymentMethod
    installment_months: int | None
    schedule: list[int] | None
    email: EmailStr
    created_at: datetime
