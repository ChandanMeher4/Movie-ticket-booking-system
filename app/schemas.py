"""Pydantic v2 data transfer objects (schemas) and request/response models.

Implements strict validation, constraints, and DTO isolation from internal models.
"""

from datetime import datetime
from decimal import Decimal
import re
from typing import Generic, List, Optional, TypeVar
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models import (
    BookingStatus,
    MovieRating,
    PaymentMethod,
    PaymentStatus,
    SeatType,
    ShowStatus,
    UserRole,
)

T = TypeVar("T")


# --- Pagination Generic ---
class PaginatedResponse(BaseModel, Generic[T]):
    """Standard pagination wrapper."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


# --- User Schemas ---
class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Full name of the user")
    email: EmailStr = Field(..., description="Unique email address")
    phone: str = Field(..., description="Contact phone number with optional country code")
    role: UserRole = Field(default=UserRole.CUSTOMER, description="Role: customer or admin")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        pattern = r"^\+?[0-9\s\-]{8,20}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Phone number must contain 8 to 20 digits and optional '+', '-', spaces")
        return v.strip()


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = None
    role: Optional[UserRole] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        pattern = r"^\+?[0-9\s\-]{8,20}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Phone number must contain 8 to 20 digits and optional '+', '-', spaces")
        return v.strip()


class UserOut(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Movie Schemas ---
class MovieBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Movie title")
    description: str = Field(..., min_length=5, description="Synopsis or plot overview")
    genre: str = Field(..., min_length=2, max_length=60, description="Genre e.g. Action, Sci-Fi")
    language: str = Field(..., min_length=2, max_length=60, description="Audio language")
    duration_min: int = Field(..., gt=0, le=600, description="Runtime in minutes")
    rating: MovieRating = Field(default=MovieRating.UA, description="Content rating: U, UA, A")
    release_date: datetime = Field(..., description="Release date")
    poster_url: str = Field(default="", max_length=500, description="Image URL of official poster")
    is_active: bool = Field(default=True, description="Active status in current catalog")


class MovieCreate(MovieBase):
    pass


class MovieUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=5)
    genre: Optional[str] = Field(None, min_length=2, max_length=60)
    language: Optional[str] = Field(None, min_length=2, max_length=60)
    duration_min: Optional[int] = Field(None, gt=0, le=600)
    rating: Optional[MovieRating] = None
    release_date: Optional[datetime] = None
    poster_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class MovieOut(MovieBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# --- Theatre Schemas ---
class TheatreBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Theatre/multiplex name")
    city: str = Field(..., min_length=2, max_length=80, description="Operating city")
    address: str = Field(..., min_length=5, description="Full street address")


class TheatreCreate(TheatreBase):
    pass


class TheatreUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    city: Optional[str] = Field(None, min_length=2, max_length=80)
    address: Optional[str] = Field(None, min_length=5)


class TheatreOut(TheatreBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# --- Screen Schemas ---
class ScreenBase(BaseModel):
    theatre_id: int = Field(..., description="Foreign key of parent theatre")
    name: str = Field(..., min_length=1, max_length=80, description="Screen or auditorium name")
    total_rows: int = Field(default=8, ge=1, le=26, description="Total rows (max 26 for A-Z)")
    seats_per_row: int = Field(default=10, ge=1, le=50, description="Seats per row")


class ScreenCreate(ScreenBase):
    pass


class ScreenUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    total_rows: Optional[int] = Field(None, ge=1, le=26)
    seats_per_row: Optional[int] = Field(None, ge=1, le=50)


class ScreenOut(ScreenBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class TheatreDetailOut(TheatreOut):
    screens: List[ScreenOut] = []

    model_config = ConfigDict(from_attributes=True)


# --- Seat Schemas ---
class SeatOut(BaseModel):
    id: int
    screen_id: int
    row_label: str
    seat_number: int
    seat_type: SeatType

    model_config = ConfigDict(from_attributes=True)


# --- Show Schemas ---
class ShowBase(BaseModel):
    movie_id: int = Field(..., description="ID of movie being screened")
    screen_id: int = Field(..., description="ID of auditorium hosting the show")
    start_time: datetime = Field(..., description="Show commencement time")
    end_time: datetime = Field(..., description="Show conclusion time")
    base_price: Decimal = Field(..., gt=Decimal("0.00"), description="Base ticket price in INR")
    status: ShowStatus = Field(default=ShowStatus.SCHEDULED)

    @model_validator(mode="after")
    def validate_times(self) -> "ShowBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        return self


class ShowCreate(ShowBase):
    pass


class ShowUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    base_price: Optional[Decimal] = Field(None, gt=Decimal("0.00"))
    status: Optional[ShowStatus] = None

    @model_validator(mode="after")
    def validate_times(self) -> "ShowUpdate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        return self


class ShowOut(ShowBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ShowDetailOut(ShowOut):
    movie: Optional[MovieOut] = None
    screen: Optional[ScreenOut] = None
    theatre: Optional[TheatreOut] = None

    model_config = ConfigDict(from_attributes=True)


# --- Seat Map Item ---
class SeatMapItem(BaseModel):
    id: int
    row_label: str
    seat_number: int
    seat_type: SeatType
    price: Decimal
    status: str  # "available", "held", "booked"

    model_config = ConfigDict(from_attributes=True)


# --- Booking Schemas ---
class BookingCreate(BaseModel):
    user_id: int = Field(..., description="Customer placing the booking")
    show_id: int = Field(..., description="Target show ID")
    seat_ids: List[int] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="List of seat IDs to hold (maximum 6 per transaction)",
    )


class BookingSeatOut(BaseModel):
    id: int
    seat_id: int
    price: Decimal
    seat: Optional[SeatOut] = None

    model_config = ConfigDict(from_attributes=True)


class BookingOut(BaseModel):
    id: int
    user_id: int
    show_id: int
    status: BookingStatus
    total_amount: Decimal
    created_at: datetime
    expires_at: datetime
    booking_seats: List[BookingSeatOut] = []

    model_config = ConfigDict(from_attributes=True)


class BookingDetailOut(BookingOut):
    show: Optional[ShowDetailOut] = None
    user: Optional[UserOut] = None

    model_config = ConfigDict(from_attributes=True)


class BookingCancelResponse(BaseModel):
    booking_id: int
    status: BookingStatus
    original_amount: Decimal
    refund_percentage: int
    refund_amount: Decimal
    message: str


# --- Payment Schemas ---
class PaymentCreate(BaseModel):
    booking_id: int = Field(..., description="Target pending booking")
    method: PaymentMethod = Field(
        ...,
        description="Payment method: card, upi, wallet",
        validation_alias=AliasChoices("method", "payment_method"),
    )


class PaymentOut(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    method: PaymentMethod
    status: PaymentStatus
    txn_ref: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
