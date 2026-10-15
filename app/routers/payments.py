"""Payments router handling checkout payment authorization and booking confirmation."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import PaymentCreate, PaymentOut
from app.services.booking_service import confirm_booking

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("", response_model=PaymentOut, status_code=status.HTTP_200_OK)
def process_payment(payload: PaymentCreate, db: Session = Depends(get_db)) -> PaymentOut:
    """Authorize mock payment gateway transaction and transition booking from pending to confirmed."""
    _, payment = confirm_booking(
        db=db,
        booking_id=payload.booking_id,
        payment_method=payload.method,
    )
    return payment
