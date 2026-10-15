"""Unit tests for the centralized cinema ticket pricing engine."""

from datetime import datetime
from decimal import Decimal
from app.models import Seat, SeatType
from app.services.pricing import (
    calculate_booking_totals,
    calculate_seat_price,
    get_seat_multiplier,
    is_weekend,
    round_currency,
    PREMIUM_MULTIPLIER,
    RECLINER_MULTIPLIER,
    REGULAR_MULTIPLIER,
)


def test_seat_multipliers():
    """Verify multipliers for seat tiers: regular=1.0, premium=1.4, recliner=1.8."""
    assert get_seat_multiplier(SeatType.REGULAR) == REGULAR_MULTIPLIER
    assert get_seat_multiplier(SeatType.PREMIUM) == PREMIUM_MULTIPLIER
    assert get_seat_multiplier(SeatType.RECLINER) == RECLINER_MULTIPLIER


def test_weekend_detection():
    """Verify weekend detection accurately identifies Friday, Saturday, Sunday."""
    # 2026-10-16 is Friday (weekday 4)
    friday = datetime(2026, 10, 16, 18, 0)
    # 2026-10-17 is Saturday (weekday 5)
    saturday = datetime(2026, 10, 17, 18, 0)
    # 2026-10-18 is Sunday (weekday 6)
    sunday = datetime(2026, 10, 18, 18, 0)
    # 2026-10-19 is Monday (weekday 0)
    monday = datetime(2026, 10, 19, 18, 0)
    # 2026-10-21 is Wednesday (weekday 2)
    wednesday = datetime(2026, 10, 21, 18, 0)

    assert is_weekend(friday) is True
    assert is_weekend(saturday) is True
    assert is_weekend(sunday) is True
    assert is_weekend(monday) is False
    assert is_weekend(wednesday) is False


def test_calculate_seat_price_weekday():
    """Verify seat pricing on a weekday without weekend surcharge."""
    weekday = datetime(2026, 10, 19, 14, 0)  # Monday
    base = Decimal("300.00")

    # Regular: 300 * 1.0 = 300.00
    assert calculate_seat_price(base, SeatType.REGULAR, weekday) == Decimal("300.00")
    # Premium: 300 * 1.4 = 420.00
    assert calculate_seat_price(base, SeatType.PREMIUM, weekday) == Decimal("420.00")
    # Recliner: 300 * 1.8 = 540.00
    assert calculate_seat_price(base, SeatType.RECLINER, weekday) == Decimal("540.00")


def test_calculate_seat_price_weekend():
    """Verify seat pricing on weekend includes 10% surcharge."""
    weekend = datetime(2026, 10, 17, 18, 0)  # Saturday
    base = Decimal("300.00")

    # Regular: 300 * 1.0 * 1.10 = 330.00
    assert calculate_seat_price(base, SeatType.REGULAR, weekend) == Decimal("330.00")
    # Premium: 300 * 1.4 * 1.10 = 462.00
    assert calculate_seat_price(base, SeatType.PREMIUM, weekend) == Decimal("462.00")
    # Recliner: 300 * 1.8 * 1.10 = 594.00
    assert calculate_seat_price(base, SeatType.RECLINER, weekend) == Decimal("594.00")


def test_calculate_booking_totals_with_convenience_fee():
    """Verify subtotal, 2% convenience fee, and final rounded total."""
    weekday = datetime(2026, 10, 20, 15, 0)  # Tuesday
    base = Decimal("200.00")

    s1 = Seat(id=1, screen_id=1, row_label="A", seat_number=1, seat_type=SeatType.REGULAR)
    s2 = Seat(id=2, screen_id=1, row_label="C", seat_number=1, seat_type=SeatType.PREMIUM)

    # s1 price = 200 * 1.0 = 200.00
    # s2 price = 200 * 1.4 = 280.00
    # subtotal = 480.00
    # convenience fee = 480 * 0.02 = 9.60
    # total = 489.60
    totals = calculate_booking_totals(base, [s1, s2], weekday)

    assert totals["subtotal"] == Decimal("480.00")
    assert totals["convenience_fee"] == Decimal("9.60")
    assert totals["total_amount"] == Decimal("489.60")
    assert totals["per_seat"][1] == Decimal("200.00")
    assert totals["per_seat"][2] == Decimal("280.00")
