"""Create payment tables and initial tariffs."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tariffs = op.create_table(
        "tariffs",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False, comment="Price in kopecks"),
        sa.CheckConstraint("price >= 0", name=op.f("ck_tariffs_price_nonnegative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tariffs")),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tariff_id", sa.String(32), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("status", sa.String(9), server_default="pending", nullable=False),
        sa.Column(
            "amount", sa.BigInteger(), nullable=False,
            comment="Amount payable in kopecks",
        ),
        sa.Column(
            "discount", sa.BigInteger(), server_default="0", nullable=False,
            comment="Applied discount in kopecks",
        ),
        sa.Column("method", sa.String(11), nullable=False),
        sa.Column("installment_months", sa.Integer(), nullable=True),
        sa.Column(
            "schedule", postgresql.JSONB(none_as_null=True), nullable=True,
            comment="Installment amounts in kopecks",
        ),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_payments_amount_nonnegative")),
        sa.CheckConstraint("discount >= 0", name=op.f("ck_payments_discount_nonnegative")),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'refunded')",
            name=op.f("ck_payments_payment_status"),
        ),
        sa.CheckConstraint(
            "method IN ('card', 'sbp', 'installment')",
            name=op.f("ck_payments_payment_method"),
        ),
        sa.CheckConstraint(
            "(method = 'installment' "
            "AND installment_months IS NOT NULL "
            "AND installment_months IN (3, 6, 12) AND schedule IS NOT NULL) "
            "OR (method IN ('card', 'sbp') "
            "AND installment_months IS NULL AND schedule IS NULL)",
            name=op.f("ck_payments_installment_fields_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["tariff_id"], ["tariffs.id"],
            name=op.f("fk_payments_tariff_id_tariffs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_payments_idempotency_key")),
    )
    op.bulk_insert(
        tariffs,
        [
            {"id": "basic", "title": "Basic", "price": 990000},
            {"id": "standard", "title": "Standard", "price": 1990000},
            {"id": "premium", "title": "Premium", "price": 2990000},
        ],
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("tariffs")
