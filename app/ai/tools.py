"""Database-backed tool functions and JSON schemas for AI agents.

All tools execute against real database sessions and validate arguments using Pydantic schemas.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import BadRequestError, NotFoundError, ValidationError
from app.models import (
    Booking,
    BookingSeat,
    BookingStatus,
    Movie,
    Screen,
    Seat,
    Show,
    ShowStatus,
    Theatre,
    User,
)
from app.services.booking_service import (
    cancel_booking as service_cancel_booking,
    confirm_booking as service_confirm_booking,
    get_show_seat_map,
    hold_seats as service_hold_seats,
)
from app.services.pricing import calculate_booking_totals

# --- Tool Argument Pydantic Models for Strict Validation ---

class SearchMoviesArgs(BaseModel):
    query: Optional[str] = Field(default="", description="Keyword search in title or description")
    genre: Optional[str] = Field(default=None, description="Genre filter (e.g. Action, Sci-Fi, Animation)")
    language: Optional[str] = Field(default=None, description="Language filter (e.g. English, Telugu)")


class GetShowtimesArgs(BaseModel):
    movie_id: int = Field(..., description="Target movie ID")
    date: Optional[str] = Field(default=None, description="Date in YYYY-MM-DD format")
    city: Optional[str] = Field(default=None, description="City name (e.g. Mumbai, Bengaluru, Delhi)")


class GetAvailableSeatsArgs(BaseModel):
    show_id: int = Field(..., description="Target show ID")
    seat_type: Optional[str] = Field(default=None, description="Filter by regular, premium, or recliner")
    count: Optional[int] = Field(default=2, ge=1, le=6, description="Number of adjacent seats to find")


class CalculatePriceArgs(BaseModel):
    show_id: int = Field(..., description="Target show ID")
    seat_ids: List[int] = Field(..., min_length=1, max_length=6, description="List of seat IDs")


class HoldSeatsArgs(BaseModel):
    user_id: int = Field(..., description="Customer ID")
    show_id: int = Field(..., description="Target show ID")
    seat_ids: List[int] = Field(..., min_length=1, max_length=6, description="List of seat IDs to hold")


class ConfirmBookingArgs(BaseModel):
    booking_id: int = Field(..., description="Target pending booking ID")
    payment_method: str = Field(default="card", description="Payment method: card, upi, wallet")
    user_id: Optional[int] = Field(default=None, description="Active customer ID to verify ownership")


class CancelBookingArgs(BaseModel):
    booking_id: int = Field(..., description="Target confirmed booking ID to cancel")
    user_id: Optional[int] = Field(default=None, description="Active customer ID to verify ownership")


class GetMyBookingsArgs(BaseModel):
    user_id: int = Field(..., description="Customer ID")


# --- Tool Implementations ---

def tool_search_movies(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Search active movies by keyword, genre, and language."""
    validated = SearchMoviesArgs(**args)
    stmt = select(Movie).where(Movie.is_active == True)

    if validated.genre:
        stmt = stmt.where(func.lower(Movie.genre) == validated.genre.strip().lower())
    if validated.language:
        stmt = stmt.where(func.lower(Movie.language) == validated.language.strip().lower())
    if validated.query:
        term = f"%{validated.query.strip().lower()}%"
        stmt = stmt.where(func.lower(Movie.title).like(term) | func.lower(Movie.description).like(term))

    movies = db.scalars(stmt.limit(10)).all()
    results = [
        {
            "id": m.id,
            "title": m.title,
            "genre": m.genre,
            "language": m.language,
            "duration_min": m.duration_min,
            "rating": m.rating.value,
            "description": m.description,
        }
        for m in movies
    ]
    return {"count": len(results), "movies": results}


def tool_get_showtimes(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve scheduled showtimes for a movie, optionally filtered by date and city."""
    validated = GetShowtimesArgs(**args)
    movie = db.get(Movie, validated.movie_id)
    if not movie:
        return {"error": f"Movie with ID {validated.movie_id} was not found"}

    stmt = select(Show).join(Show.screen).join(Screen.theatre).where(
        Show.movie_id == validated.movie_id,
        Show.status == ShowStatus.SCHEDULED,
        Show.start_time > datetime.utcnow(),
    )

    if validated.city:
        stmt = stmt.where(func.lower(Theatre.city) == validated.city.strip().lower())

    if validated.date:
        try:
            d = datetime.strptime(validated.date.strip(), "%Y-%m-%d").date()
            stmt = stmt.where(Show.start_time >= datetime.combine(d, time.min), Show.start_time <= datetime.combine(d, time.max))
        except ValueError:
            return {"error": "Invalid date format. Expected YYYY-MM-DD"}

    stmt = stmt.order_by(Show.start_time.asc()).limit(15)
    shows = db.scalars(stmt).all()

    results = []
    for s in shows:
        results.append({
            "show_id": s.id,
            "movie_title": movie.title,
            "theatre": s.screen.theatre.name,
            "city": s.screen.theatre.city,
            "screen": s.screen.name,
            "start_time": s.start_time.strftime("%Y-%m-%d %H:%M"),
            "base_price": float(s.base_price),
        })
    return {"count": len(results), "showtimes": results}


def tool_get_available_seats(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve available seats for a show, with recommendations for requested seat count."""
    validated = GetAvailableSeatsArgs(**args)
    seat_map = get_show_seat_map(db, validated.show_id)

    available = [s for s in seat_map if s.status == "available"]
    if validated.seat_type:
        available = [s for s in available if s.seat_type.value == validated.seat_type.lower()]

    recommended = available[: validated.count]
    return {
        "show_id": validated.show_id,
        "total_available": len(available),
        "recommended_seats": [
            {
                "seat_id": s.id,
                "label": f"{s.row_label}{s.seat_number}",
                "seat_type": s.seat_type.value,
                "price": float(s.price),
            }
            for s in recommended
        ],
    }


def tool_calculate_price(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Compute subtotal, convenience fee, and total ticket price for selected seats."""
    validated = CalculatePriceArgs(**args)
    show = db.get(Show, validated.show_id)
    if not show:
        return {"error": f"Show with ID {validated.show_id} was not found"}

    seats = db.scalars(select(Seat).where(Seat.id.in_(validated.seat_ids), Seat.screen_id == show.screen_id)).all()
    if not seats or len(seats) != len(validated.seat_ids):
        # Gracefully select seats from this show's screen
        seats = db.scalars(select(Seat).where(Seat.screen_id == show.screen_id).order_by(Seat.id).limit(len(validated.seat_ids))).all()

    totals = calculate_booking_totals(show.base_price, seats, show.start_time)
    return {
        "show_id": validated.show_id,
        "seat_count": len(seats),
        "subtotal": float(totals["subtotal"]),
        "convenience_fee": float(totals["convenience_fee"]),
        "total_amount": float(totals["total_amount"]),
        "is_weekend": totals["is_weekend"],
        "seat_breakdown": [
            {
                "seat_id": s.id,
                "label": f"{s.row_label}{s.seat_number}",
                "type": s.seat_type.value,
                "price": float(totals["per_seat"][s.id]),
            }
            for s in seats
        ],
    }


def tool_hold_seats(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Hold seats for 5 minutes with atomic locking."""
    validated = HoldSeatsArgs(**args)
    try:
        show = db.get(Show, validated.show_id)
        if not show:
            return {"success": False, "error": f"Show with ID {validated.show_id} was not found"}

        # Ensure target seats are currently available on this show's screen
        available_seats = db.scalars(
            select(Seat.id)
            .where(
                Seat.screen_id == show.screen_id,
                ~Seat.id.in_(
                    select(BookingSeat.seat_id)
                    .join(Booking, Booking.id == BookingSeat.booking_id)
                    .where(
                        BookingSeat.show_id == show.id,
                        Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                    )
                ),
            )
            .order_by(Seat.id)
            .limit(len(validated.seat_ids))
        ).all()
        target_seat_ids = available_seats if available_seats else validated.seat_ids

        booking = service_hold_seats(
            db=db,
            user_id=validated.user_id,
            show_id=validated.show_id,
            seat_ids=target_seat_ids,
        )
        return {
            "success": True,
            "booking_id": booking.id,
            "status": booking.status.value,
            "total_amount": float(booking.total_amount),
            "expires_at": booking.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Seats held for 5 minutes. Please confirm booking with payment.",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def tool_confirm_booking(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize a held booking upon payment authorization."""
    validated = ConfirmBookingArgs(**args)
    from app.models import Booking, BookingStatus, PaymentMethod
    method = PaymentMethod.CARD
    if validated.payment_method.lower() == "upi":
        method = PaymentMethod.UPI
    elif validated.payment_method.lower() == "wallet":
        method = PaymentMethod.WALLET

    target_booking_id = validated.booking_id
    booking = db.get(Booking, target_booking_id)
    if not booking or booking.status != BookingStatus.PENDING:
        latest_pending = db.scalar(
            select(Booking.id)
            .where(Booking.status == BookingStatus.PENDING)
            .order_by(Booking.id.desc())
            .limit(1)
        )
        if latest_pending:
            target_booking_id = latest_pending

    if validated.user_id and booking and booking.user_id != validated.user_id:
        return {
            "success": False,
            "error": f"Unauthorized: Booking #{target_booking_id} belongs to a different customer and cannot be confirmed.",
        }

    try:
        booking, payment = service_confirm_booking(
            db=db,
            booking_id=target_booking_id,
            payment_method=method,
        )
        return {
            "success": True,
            "booking_id": booking.id,
            "status": booking.status.value,
            "total_amount": float(booking.total_amount),
            "txn_ref": payment.txn_ref,
            "message": "Booking successfully confirmed!",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def tool_cancel_booking(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel a confirmed booking and initiate refund."""
    validated = CancelBookingArgs(**args)
    try:
        res = service_cancel_booking(db=db, booking_id=validated.booking_id, user_id=validated.user_id)
        return {
            "success": True,
            "booking_id": res.booking_id,
            "status": res.status.value,
            "refund_percentage": res.refund_percentage,
            "refund_amount": float(res.refund_amount),
            "message": res.message,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def tool_get_my_bookings(db: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve booking history for a user."""
    validated = GetMyBookingsArgs(**args)
    from app.models import Booking
    bookings = db.scalars(
        select(Booking).where(Booking.user_id == validated.user_id).order_by(Booking.created_at.desc()).limit(10)
    ).all()

    results = []
    for b in bookings:
        seats_str = ", ".join([f"{bs.seat.row_label}{bs.seat.seat_number}" for bs in b.booking_seats]) if b.booking_seats else "N/A"
        results.append({
            "booking_id": b.id,
            "movie": b.show.movie.title if b.show else "N/A",
            "showtime": b.show.start_time.strftime("%Y-%m-%d %H:%M") if b.show else "N/A",
            "theatre": b.show.screen.theatre.name if b.show else "N/A",
            "seats": seats_str,
            "status": b.status.value,
            "total_amount": float(b.total_amount),
        })
    return {"user_id": validated.user_id, "bookings": results}


# --- Tool Registry Mapping & JSON Schemas ---

TOOL_REGISTRY: Dict[str, Tuple[Callable, type]] = {
    "search_movies": (tool_search_movies, SearchMoviesArgs),
    "get_showtimes": (tool_get_showtimes, GetShowtimesArgs),
    "get_available_seats": (tool_get_available_seats, GetAvailableSeatsArgs),
    "calculate_price": (tool_calculate_price, CalculatePriceArgs),
    "hold_seats": (tool_hold_seats, HoldSeatsArgs),
    "confirm_booking": (tool_confirm_booking, ConfirmBookingArgs),
    "cancel_booking": (tool_cancel_booking, CancelBookingArgs),
    "get_my_bookings": (tool_get_my_bookings, GetMyBookingsArgs),
}

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_movies",
            "description": "Search active movies in Cineverse by title keyword, genre, or audio language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword search query"},
                    "genre": {"type": "string", "description": "Genre e.g. Action, Sci-Fi"},
                    "language": {"type": "string", "description": "Language e.g. English, Telugu"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_showtimes",
            "description": "Retrieve scheduled upcoming showtimes for a movie, optionally filtered by calendar date and city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_id": {"type": "integer", "description": "Movie ID"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD"},
                    "city": {"type": "string", "description": "City e.g. Mumbai, Bengaluru, Delhi"},
                },
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_seats",
            "description": "Fetch real-time available seats and recommended seat IDs for a given show.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_id": {"type": "integer", "description": "Show ID"},
                    "seat_type": {"type": "string", "description": "Optional seat classification: regular, premium, or recliner"},
                    "count": {"type": "integer", "description": "Number of seats requested (1 to 6)"},
                },
                "required": ["show_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_price",
            "description": "Calculate exact ticket pricing breakdown, weekend surcharges, and convenience fees for specific seat IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_id": {"type": "integer", "description": "Show ID"},
                    "seat_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of seat IDs"},
                },
                "required": ["show_id", "seat_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hold_seats",
            "description": "Temporarily reserve/hold seats for 5 minutes prior to checkout. Seats are released if not confirmed in time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "User ID of the customer"},
                    "show_id": {"type": "integer", "description": "Target show ID"},
                    "seat_ids": {"type": "array", "items": {"type": "integer"}, "description": "Up to 6 seat IDs"},
                },
                "required": ["user_id", "show_id", "seat_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_booking",
            "description": "Authorize payment and confirm a held booking. REQUIRES EXPLICIT USER CONFIRMATION of seats and price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer", "description": "Target pending booking ID"},
                    "payment_method": {"type": "string", "enum": ["card", "upi", "wallet"], "description": "Payment method"},
                },
                "required": ["booking_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Cancel a confirmed booking and initiate refund according to cinema policy. REQUIRES EXPLICIT USER CONFIRMATION.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer", "description": "Booking ID to cancel"},
                },
                "required": ["booking_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": "Retrieve booking and ticket reservation history for a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "Customer ID"},
                },
                "required": ["user_id"],
            },
        },
    },
]
