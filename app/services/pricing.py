def calculate_amount(price: int, promo_code: str | None) -> tuple[int, int]:
    """Return amount payable and discount in kopecks; round discount down."""
    discount = price * 10 // 100 if promo_code is not None else 0
    return price - discount, discount


def build_schedule(amount: int, months: int) -> list[int]:
    installment, remainder = divmod(amount, months)
    return [installment + (index < remainder) for index in range(months)]
