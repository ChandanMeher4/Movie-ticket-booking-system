"""Centralized cinema ticket pricing engine.

Applies seat tier multipliers, weekend surcharges, and convenience fees.
All financial calculations use Decimal with ROUND_HALF_UP.
"""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List
from app.models import Seat, SeatType

# --- Pricing Business Constants ---
REGULAR_MULTIPLIER = Decimal("1.0")
PREMIUM_MULTIPLIER = Decimal("1.4")
RECLINER_MULTIPLIER = Decimal("1.8")

# Weekend surcharge applies on Friday (4), Saturday (5), and Sunday (6)
WEEKEND_SURCHARGE_RATE = Decimal("0.10")  # 10%
CONVENIENCE_FEE_RATE = Decimal("0.02")    # 2%


def get_seat_multiplier(seat_type: SeatType) -> Decimal:
    """Return multiplier for the given seat classification tier."""
    if seat_type == SeatType.PREMIUM:
        return PREMIUM_MULTIPLIER
    elif seat_type == SeatType.RECLINER:
        return RECLINER_MULTIPLIER
    return REGULAR_MULTIPLIER


def is_weekend(dt: datetime) -> bool:
    """Check if the datetime falls on a weekend (Friday, Saturday, or Sunday)."""
    # weekday(): Monday=0 ... Friday=4, Saturday=5, Sunday=6
    return dt.weekday() in (4, 5, 6)


def round_currency(value: Decimal) -> Decimal:
    """Round monetary amount to standard two decimal places."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_seat_price(base_price: Decimal, seat_type: SeatType, show_time: datetime) -> Decimal:
    """Calculate the individual ticket price for a single seat in a given show.

    Formula: (base_price * seat_multiplier) * (1 + weekend_surcharge if weekend)
    """
    multiplier = get_seat_multiplier(seat_type)
    tier_price = base_price * multiplier
    if is_weekend(show_time):
        tier_price = tier_price * (Decimal("1.0") + WEEKEND_SURCHARGE_RATE)
    return round_currency(tier_price)


def calculate_booking_totals(base_price: Decimal, seats: List[Seat], show_time: datetime) -> Dict:
    """Compute the full breakdown of prices for a collection of seats.

    Returns:
        Dict containing:
        - per_seat: map of seat_id -> individual seat price (with weekend surcharge)
        - subtotal: sum of seat prices
        - convenience_fee: 2% of subtotal
        - total_amount: subtotal + convenience_fee
    """
    per_seat = {}
    subtotal = Decimal("0.00")

    for seat in seats:
        seat_price = calculate_seat_price(base_price, seat.seat_type, show_time)
        per_seat[seat.id] = seat_price
        subtotal += seat_price

    convenience_fee = round_currency(subtotal * CONVENIENCE_FEE_RATE)
    total_amount = round_currency(subtotal + convenience_fee)

    return {
        "per_seat": per_seat,
        "subtotal": subtotal,
        "convenience_fee": convenience_fee,
        "total_amount": total_amount,
        "is_weekend": is_weekend(show_time),
    }
