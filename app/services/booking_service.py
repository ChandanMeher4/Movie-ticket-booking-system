"""Core booking domain service.

Enforces seat locking, 5-minute hold TTL, payment confirmations, and tiered cancellation refunds.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
import uuid
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import FlushError
from sqlalchemy.orm import Session

from app.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import (
    Booking,
    BookingSeat,
    BookingStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Seat,
    Show,
    ShowStatus,
    User,
    UserRole,
)
from app.schemas import BookingCancelResponse, SeatMapItem
from app.services.pricing import calculate_booking_totals, calculate_seat_price

# --- Business Rules Constants ---
MAX_SEATS_PER_BOOKING = 6
HOLD_DURATION_MINUTES = 5
CANCEL_CUTOFF_HOURS = 2
REFUND_TIER_FULL_HOURS = 24
REFUND_TIER_FULL_PERCENT = 100
REFUND_TIER_PARTIAL_PERCENT = 50


import logging
import time

logger = logging.getLogger(__name__)


def _is_seat_unique_violation(e: IntegrityError) -> bool:
    """Check if the IntegrityError is caused by duplicate seat booking on uq_show_seat."""
    msg = str(e).lower()
    return "uq_show_seat" in msg or "booking_seats" in msg or "unique constraint" in msg or "duplicate entry" in msg


def _is_transient_lock_error(e: OperationalError) -> bool:
    """Check if the OperationalError is a transient MySQL deadlock (1213) or lock wait timeout (1205), or SQLite lock."""
    orig = getattr(e, "orig", None)
    if orig and hasattr(orig, "args") and len(orig.args) > 0:
        code = orig.args[0]
        if code in (1205, 1213):  # MySQL ER_LOCK_WAIT_TIMEOUT, ER_LOCK_DEADLOCK
            return True
    msg = str(e).lower()
    return any(term in msg for term in ["deadlock", "lock wait timeout", "database is locked", "database table is locked"])


def release_expired_holds(db: Session, show_id: Optional[int] = None) -> int:
    """Find and cancel pending bookings past their 5-minute TTL, releasing seats."""
    try:
        now = datetime.utcnow()
        stmt = select(Booking).where(
            Booking.status == BookingStatus.PENDING,
            Booking.expires_at < now,
        )
        if show_id:
            stmt = stmt.where(Booking.show_id == show_id)

        expired_bookings = db.scalars(stmt).all()
        count = len(expired_bookings)

        for booking in expired_bookings:
            booking.status = BookingStatus.CANCELLED
            # Remove booking_seats to release the UNIQUE(show_id, seat_id) constraint
            db.execute(delete(BookingSeat).where(BookingSeat.booking_id == booking.id))

        if count > 0:
            db.commit()

        return count
    except OperationalError as e:
        db.rollback()
        if _is_transient_lock_error(e):
            return 0
        logger.error("OperationalError during release_expired_holds: %s", e, exc_info=True)
        raise


def get_show_seat_map(db: Session, show_id: int) -> List[SeatMapItem]:
    """Retrieve the real-time seat layout for a show with live pricing and availability status."""
    show = db.get(Show, show_id)
    if not show:
        raise NotFoundError(f"Show with ID {show_id} was not found")

    # Release any holds that have expired
    release_expired_holds(db, show_id)

    # Fetch all physical seats for the screen
    seats = db.scalars(
        select(Seat).where(Seat.screen_id == show.screen_id).order_by(Seat.row_label.asc(), Seat.seat_number.asc())
    ).all()

    # Query active booking seats for this show
    active_bs = db.scalars(
        select(BookingSeat)
        .join(Booking, Booking.id == BookingSeat.booking_id)
        .where(
            BookingSeat.show_id == show_id,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
        )
    ).all()

    seat_status_map = {}
    now = datetime.utcnow()
    for bs in active_bs:
        if bs.booking.status == BookingStatus.CONFIRMED:
            seat_status_map[bs.seat_id] = "booked"
        elif bs.booking.status == BookingStatus.PENDING:
            if bs.booking.expires_at > now:
                seat_status_map[bs.seat_id] = "held"
            else:
                seat_status_map[bs.seat_id] = "available"

    result = []
    for s in seats:
        seat_price = calculate_seat_price(show.base_price, s.seat_type, show.start_time)
        result.append(
            SeatMapItem(
                id=s.id,
                row_label=s.row_label,
                seat_number=s.seat_number,
                seat_type=s.seat_type,
                price=seat_price,
                status=seat_status_map.get(s.id, "available"),
            )
        )
    return result


def hold_seats(db: Session, user_id: int, show_id: int, seat_ids: List[int]) -> Booking:
    """Reserve seats with a 5-minute temporary hold.

    Validates:
    - User exists
    - Show is scheduled and in the future
    - 1 to 6 seats requested
    - All seats belong to the screen
    - Atomic seat locking preventing double booking via UNIQUE(show_id, seat_id)
    """
    if not seat_ids:
        raise ValidationError("At least 1 seat must be selected")

    if len(seat_ids) > MAX_SEATS_PER_BOOKING:
        raise ValidationError(f"Cannot book more than {MAX_SEATS_PER_BOOKING} seats per transaction")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            user = db.get(User, user_id)
            if not user:
                raise NotFoundError(f"User with ID {user_id} was not found")

            show = db.get(Show, show_id)
            if not show:
                raise NotFoundError(f"Show with ID {show_id} was not found")

            if show.status != ShowStatus.SCHEDULED:
                raise BadRequestError(f"Cannot book tickets: show is {show.status.value}")

            now = datetime.utcnow()
            if show.start_time <= now:
                raise BadRequestError("Cannot book tickets for a show that has already started or concluded")

            # Fetch requested seats and verify they belong to this screen
            seats = db.scalars(select(Seat).where(Seat.id.in_(seat_ids))).all()
            if len(seats) != len(seat_ids):
                raise NotFoundError("One or more selected seat IDs do not exist")

            for s in seats:
                if s.screen_id != show.screen_id:
                    raise ValidationError(
                        f"Seat {s.row_label}{s.seat_number} does not belong to the screen hosting this show"
                    )

            # Calculate price breakdown
            totals = calculate_booking_totals(show.base_price, seats, show.start_time)

            # Release expired holds for this show first
            release_expired_holds(db, show_id)
            # Check if any of the requested seats are already held or confirmed
            conflict_seat = db.scalar(
                select(BookingSeat.seat_id)
                .join(Booking, Booking.id == BookingSeat.booking_id)
                .where(
                    BookingSeat.show_id == show_id,
                    BookingSeat.seat_id.in_(seat_ids),
                    Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                )
                .limit(1)
            )
            if conflict_seat:
                raise ConflictError(
                    "One or more selected seats have already been booked or held by another customer. Please choose other seats."
                )

            # Create pending booking with 5-minute expiration
            expires_at = now + timedelta(minutes=HOLD_DURATION_MINUTES)
            booking = Booking(
                user_id=user_id,
                show_id=show_id,
                status=BookingStatus.PENDING,
                total_amount=totals["total_amount"],
                created_at=now,
                expires_at=expires_at,
            )
            db.add(booking)
            db.flush()  # obtain booking.id

            # Insert booking seats
            booking_seats = []
            for s in seats:
                booking_seats.append(
                    BookingSeat(
                        booking_id=booking.id,
                        show_id=show_id,
                        seat_id=s.id,
                        price=totals["per_seat"][s.id],
                    )
                )
            db.add_all(booking_seats)
            db.commit()
            return booking

        except (ConflictError, NotFoundError, BadRequestError, ValidationError):
            db.rollback()
            raise
        except IntegrityError as e:
            db.rollback()
            if _is_seat_unique_violation(e):
                raise ConflictError(
                    "One or more selected seats have already been booked or held by another customer. Please choose other seats."
                )
            logger.error("Database integrity error in hold_seats: %s", e, exc_info=True)
            raise
        except FlushError as e:
            db.rollback()
            raise ConflictError(
                "One or more selected seats have already been booked or held by another customer. Please choose other seats."
            )
        except OperationalError as e:
            db.rollback()
            if _is_transient_lock_error(e) and attempt < max_retries - 1:
                time.sleep(0.05 * (2 ** attempt))
                continue
            logger.error("Database operational error in hold_seats (attempt %d/%d): %s", attempt + 1, max_retries, e, exc_info=True)
            raise

    raise ConflictError(
        "One or more selected seats have already been booked or held by another customer. Please choose other seats."
    )


def confirm_booking(
    db: Session, booking_id: int, payment_method: PaymentMethod
) -> Tuple[Booking, Payment]:
    """Confirm a held booking upon mock payment authorization.

    Ensures the 5-minute hold has not expired before finalizing.
    """
    # Release any globally expired holds
    release_expired_holds(db)

    booking = db.get(Booking, booking_id)
    if not booking:
        raise NotFoundError(f"Booking with ID {booking_id} was not found")

    if booking.status == BookingStatus.CONFIRMED:
        # Already confirmed, find existing payment
        existing_payment = db.scalar(
            select(Payment).where(
                Payment.booking_id == booking_id,
                Payment.status == PaymentStatus.SUCCESS,
            ).limit(1)
        )
        return booking, existing_payment

    if booking.status == BookingStatus.CANCELLED:
        raise BadRequestError("This booking has been cancelled and cannot be confirmed")

    now = datetime.utcnow()
    if booking.expires_at < now:
        booking.status = BookingStatus.CANCELLED
        db.execute(delete(BookingSeat).where(BookingSeat.booking_id == booking.id))
        db.commit()
        raise BadRequestError(
            f"Your seat hold expired after {HOLD_DURATION_MINUTES} minutes. Please select your seats again."
        )

    # Process successful payment
    txn_ref = f"TXN-{uuid.uuid4().hex[:12].upper()}"
    payment = Payment(
        booking_id=booking.id,
        amount=booking.total_amount,
        method=payment_method,
        status=PaymentStatus.SUCCESS,
        txn_ref=txn_ref,
        created_at=now,
    )
    booking.status = BookingStatus.CONFIRMED

    db.add(payment)
    db.commit()
    db.refresh(booking)
    db.refresh(payment)

    return booking, payment


def cancel_booking(
    db: Session, booking_id: int, user_id: Optional[int] = None
) -> BookingCancelResponse:
    """Cancel a confirmed booking and calculate refund based on showtime tiers.

    Tiers:
    - < 2 hours before showtime: cancellation not allowed
    - >= 24 hours before showtime: 100% refund
    - 2 to 24 hours before showtime: 50% refund
    """
    booking = db.get(Booking, booking_id)
    if not booking:
        raise NotFoundError(f"Booking with ID {booking_id} was not found")

    if user_id:
        user = db.get(User, user_id)
        is_admin = user and user.role == UserRole.ADMIN
        if not is_admin and booking.user_id != user_id:
            raise ForbiddenError("You do not have permission to cancel this booking")

    if booking.status != BookingStatus.CONFIRMED:
        raise BadRequestError(f"Cannot cancel booking with status '{booking.status.value}'")

    show = booking.show
    now = datetime.utcnow()
    time_until_show = show.start_time - now

    # Rule: Cancellation not allowed within 2 hours of showtime
    if time_until_show < timedelta(hours=CANCEL_CUTOFF_HOURS):
        raise BadRequestError(
            f"Cancellations are only permitted at least {CANCEL_CUTOFF_HOURS} hours prior to showtime."
        )

    # Determine refund percentage
    if time_until_show >= timedelta(hours=REFUND_TIER_FULL_HOURS):
        refund_pct = REFUND_TIER_FULL_PERCENT
    else:
        refund_pct = REFUND_TIER_PARTIAL_PERCENT

    refund_factor = Decimal(str(refund_pct)) / Decimal("100")
    refund_amount = (booking.total_amount * refund_factor).quantize(Decimal("0.01"))

    # Update booking status
    booking.status = BookingStatus.CANCELLED

    # Release booking seats so they become available for other customers
    db.execute(delete(BookingSeat).where(BookingSeat.booking_id == booking.id))

    # Record refunded payment entry
    refund_payment = Payment(
        booking_id=booking.id,
        amount=refund_amount,
        method=PaymentMethod.CARD,
        status=PaymentStatus.REFUNDED,
        txn_ref=f"RFND-{uuid.uuid4().hex[:12].upper()}",
        created_at=now,
    )
    db.add(refund_payment)
    db.commit()

    return BookingCancelResponse(
        booking_id=booking.id,
        status=BookingStatus.CANCELLED,
        original_amount=booking.total_amount,
        refund_percentage=refund_pct,
        refund_amount=refund_amount,
        message=f"Booking cancelled successfully. A {refund_pct}% refund of ₹{refund_amount} has been initiated.",
    )
