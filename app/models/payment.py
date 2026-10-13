from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(StrEnum):
    CARD = "card"
    SBP = "sbp"
    INSTALLMENT = "installment"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_nonnegative"),
        CheckConstraint("discount >= 0", name="discount_nonnegative"),
        CheckConstraint(
            "(method = 'installment' "
            "AND installment_months IS NOT NULL "
            "AND installment_months IN (3, 6, 12) AND schedule IS NOT NULL) "
            "OR (method IN ('card', 'sbp') "
            "AND installment_months IS NULL AND schedule IS NULL)",
            name="installment_fields_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tariff_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tariffs.id")
    )
    email: Mapped[str] = mapped_column(Text)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
    )
    amount: Mapped[int] = mapped_column(
        BigInteger, comment="Amount payable in kopecks"
    )
    discount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default="0",
        comment="Applied discount in kopecks",
    )
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(
            PaymentMethod,
            name="payment_method",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    installment_months: Mapped[int | None] = mapped_column(Integer)
    schedule: Mapped[list[int] | None] = mapped_column(
        JSONB(none_as_null=True), comment="Installment amounts in kopecks"
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
