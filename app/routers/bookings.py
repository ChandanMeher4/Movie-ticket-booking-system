"""Bookings router providing seat holds, retrieval, cancellations, and user history."""

from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user_id
from app.database import get_db
from app.errors import ForbiddenError, NotFoundError
from app.models import Booking, User, UserRole
from app.schemas import (
    BookingCancelResponse,
    BookingCreate,
    BookingDetailOut,
    BookingOut,
    ShowDetailOut,
)
from app.services.booking_service import (
    cancel_booking,
    hold_seats,
    release_expired_holds,
)

router = APIRouter(tags=["bookings"])


@router.post("/api/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking_hold(payload: BookingCreate, db: Session = Depends(get_db)) -> BookingOut:
    """Hold up to 6 seats for 5 minutes with atomic locking to prevent double bookings."""
    booking = hold_seats(
        db=db,
        user_id=payload.user_id,
        show_id=payload.show_id,
        seat_ids=payload.seat_ids,
    )
    return booking


@router.get("/api/bookings/{booking_id}", response_model=BookingDetailOut)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    active_user_id: Optional[int] = Depends(get_current_user_id),
) -> BookingDetailOut:
    """Retrieve detailed booking record including seats and showtime."""
    release_expired_holds(db)
    booking = db.get(Booking, booking_id)
    if not booking:
        raise NotFoundError(f"Booking with ID {booking_id} was not found")

    if active_user_id is not None:
        caller = db.get(User, active_user_id)
        is_admin = caller and caller.role == UserRole.ADMIN
        if not is_admin and booking.user_id != active_user_id:
            raise ForbiddenError("You do not have permission to view this booking")

    show = booking.show
    show_detail = None
    if show:
        show_detail = ShowDetailOut(
            id=show.id,
            movie_id=show.movie_id,
            screen_id=show.screen_id,
            start_time=show.start_time,
            end_time=show.end_time,
            base_price=show.base_price,
            status=show.status,
            movie=show.movie,
            screen=show.screen,
            theatre=show.screen.theatre if show.screen else None,
        )

    return BookingDetailOut(
        id=booking.id,
        user_id=booking.user_id,
        show_id=booking.show_id,
        status=booking.status,
        total_amount=booking.total_amount,
        created_at=booking.created_at,
        expires_at=booking.expires_at,
        booking_seats=booking.booking_seats,
        show=show_detail,
        user=booking.user,
    )


@router.post("/api/bookings/{booking_id}/cancel", response_model=BookingCancelResponse)
def cancel_booking_endpoint(
    booking_id: int,
    db: Session = Depends(get_db),
    active_user_id: Optional[int] = Depends(get_current_user_id),
) -> BookingCancelResponse:
    """Cancel a confirmed booking and calculate tiered refund (100% >24h, 50% 2-24h)."""
    return cancel_booking(db=db, booking_id=booking_id, user_id=active_user_id)


@router.get("/api/users/{user_id}/bookings", response_model=List[BookingDetailOut])
def get_user_bookings(
    user_id: int,
    db: Session = Depends(get_db),
    active_user_id: Optional[int] = Depends(get_current_user_id),
) -> List[BookingDetailOut]:
    """Retrieve booking history for a specific customer."""
    release_expired_holds(db)
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError(f"User with ID {user_id} was not found")

    if active_user_id is not None:
        caller = db.get(User, active_user_id)
        is_admin = caller and caller.role == UserRole.ADMIN
        if not is_admin and user_id != active_user_id:
            raise ForbiddenError("You do not have permission to view another customer's booking history")

    bookings = db.scalars(
        select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
    ).all()

    results = []
    for b in bookings:
        show = b.show
        show_detail = None
        if show:
            show_detail = ShowDetailOut(
                id=show.id,
                movie_id=show.movie_id,
                screen_id=show.screen_id,
                start_time=show.start_time,
                end_time=show.end_time,
                base_price=show.base_price,
                status=show.status,
                movie=show.movie,
                screen=show.screen,
                theatre=show.screen.theatre if show.screen else None,
            )
        results.append(
            BookingDetailOut(
                id=b.id,
                user_id=b.user_id,
                show_id=b.show_id,
                status=b.status,
                total_amount=b.total_amount,
                created_at=b.created_at,
                expires_at=b.expires_at,
                booking_seats=b.booking_seats,
                show=show_detail,
                user=b.user,
            )
        )

    return results
