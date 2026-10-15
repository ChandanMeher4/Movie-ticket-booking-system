"""Seats router providing seat map layout and availability for scheduled shows."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import SeatMapItem
from app.services.booking_service import get_show_seat_map

router = APIRouter(prefix="/api/shows", tags=["seats"])


@router.get("/{show_id}/seats", response_model=List[SeatMapItem])
def get_seats_for_show(show_id: int, db: Session = Depends(get_db)) -> List[SeatMapItem]:
    """Retrieve seat layout for a show with current availability (available, held, booked) and tier pricing."""
    return get_show_seat_map(db, show_id)
