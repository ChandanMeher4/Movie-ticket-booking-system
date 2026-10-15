"""SQLAlchemy 2.0 ORM models for the Movie Ticket Booking System.

Defines all 10 entities, constraints, foreign keys, and cascading rules.
"""

from datetime import datetime
from decimal import Decimal
import enum
from typing import Any, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class MovieRating(str, enum.Enum):
    U = "U"
    UA = "UA"
    A = "A"


class SeatType(str, enum.Enum):
    REGULAR = "regular"
    PREMIUM = "premium"
    RECLINER = "recliner"


class ShowStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    CARD = "card"
    UPI = "upi"
    WALLET = "wallet"


class PaymentStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class User(Base):
    """Registered application user, customer or administrator."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(191), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.CUSTOMER,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="user", cascade="all, delete-orphan")


class Movie(Base):
    """Movie catalog item containing metadata, synopsis, and rating."""

    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    genre: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[MovieRating] = mapped_column(
        Enum(MovieRating, values_callable=lambda x: [e.value for e in x]),
        default=MovieRating.UA,
        nullable=False,
    )
    release_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    poster_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    shows: Mapped[List["Show"]] = relationship("Show", back_populates="movie", cascade="all, delete-orphan")


class Theatre(Base):
    """Physical cinema theatre located in a specific city."""

    __tablename__ = "theatres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)

    screens: Mapped[List["Screen"]] = relationship("Screen", back_populates="theatre", cascade="all, delete-orphan")


class Screen(Base):
    """Auditorium within a theatre configured with row/column dimensions."""

    __tablename__ = "screens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theatre_id: Mapped[int] = mapped_column(Integer, ForeignKey("theatres.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    seats_per_row: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    theatre: Mapped["Theatre"] = relationship("Theatre", back_populates="screens")
    seats: Mapped[List["Seat"]] = relationship("Seat", back_populates="screen", cascade="all, delete-orphan")
    shows: Mapped[List["Show"]] = relationship("Show", back_populates="screen", cascade="all, delete-orphan")


class Seat(Base):
    """Physical chair inside a screen identified by row label and number."""

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("screen_id", "row_label", "seat_number", name="uq_screen_seat"),
        Index("idx_seats_screen", "screen_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screen_id: Mapped[int] = mapped_column(Integer, ForeignKey("screens.id", ondelete="CASCADE"), nullable=False)
    row_label: Mapped[str] = mapped_column(String(5), nullable=False)
    seat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    seat_type: Mapped[SeatType] = mapped_column(
        Enum(SeatType, values_callable=lambda x: [e.value for e in x]),
        default=SeatType.REGULAR,
        nullable=False,
    )

    screen: Mapped["Screen"] = relationship("Screen", back_populates="seats")
    booking_seats: Mapped[List["BookingSeat"]] = relationship("BookingSeat", back_populates="seat", cascade="all, delete-orphan")


class Show(Base):
    """Scheduled screening of a movie on a screen with baseline ticket pricing."""

    __tablename__ = "shows"
    __table_args__ = (
        Index("idx_shows_screen_time", "screen_id", "start_time"),
        Index("idx_shows_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    screen_id: Mapped[int] = mapped_column(Integer, ForeignKey("screens.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[ShowStatus] = mapped_column(
        Enum(ShowStatus, values_callable=lambda x: [e.value for e in x]),
        default=ShowStatus.SCHEDULED,
        nullable=False,
    )

    movie: Mapped["Movie"] = relationship("Movie", back_populates="shows")
    screen: Mapped["Screen"] = relationship("Screen", back_populates="shows")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="show", cascade="all, delete-orphan")
    booking_seats: Mapped[List["BookingSeat"]] = relationship("BookingSeat", back_populates="show", cascade="all, delete-orphan")


class Booking(Base):
    """Ticket reservation record with 5-minute hold TTL before confirmation."""

    __tablename__ = "bookings"
    __table_args__ = (
        Index("idx_bookings_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    show_id: Mapped[int] = mapped_column(Integer, ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, values_callable=lambda x: [e.value for e in x]),
        default=BookingStatus.PENDING,
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="bookings")
    show: Mapped["Show"] = relationship("Show", back_populates="bookings")
    booking_seats: Mapped[List["BookingSeat"]] = relationship("BookingSeat", back_populates="booking", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")


class BookingSeat(Base):
    """Seat assignment for a specific show.

    Enforces the single most crucial integrity constraint:
    UNIQUE(show_id, seat_id) - guarantees that two bookings cannot claim
    the same seat for the same show under any concurrency condition.
    """

    __tablename__ = "booking_seats"
    __table_args__ = (
        UniqueConstraint("show_id", "seat_id", name="uq_show_seat"),
        Index("idx_bs_booking", "booking_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    show_id: Mapped[int] = mapped_column(Integer, ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    seat_id: Mapped[int] = mapped_column(Integer, ForeignKey("seats.id", ondelete="CASCADE"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="booking_seats")
    show: Mapped["Show"] = relationship("Show", back_populates="booking_seats")
    seat: Mapped["Seat"] = relationship("Seat", back_populates="booking_seats")


class Payment(Base):
    """Payment transaction ledger record."""

    __tablename__ = "payments"
    __table_args__ = (
        Index("idx_payments_booking", "booking_id"),
        Index("idx_payments_txn", "txn_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    txn_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="payments")


class AILog(Base):
    """Audit log tracking all GenAI, single-agent, and multi-agent interactions."""

    __tablename__ = "ai_logs"
    __table_args__ = (
        Index("idx_ai_logs_session", "session_id"),
        Index("idx_ai_logs_agent", "agent_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(60), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
