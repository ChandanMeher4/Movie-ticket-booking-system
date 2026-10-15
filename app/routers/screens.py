"""Screens router providing creation with automated seat grid generation."""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.errors import NotFoundError
from app.models import Screen, Seat, SeatType, Theatre
from app.schemas import ScreenCreate, ScreenOut, SeatOut

router = APIRouter(prefix="/api/screens", tags=["screens"])


@router.get("/{screen_id}", response_model=ScreenOut)
def get_screen(screen_id: int, db: Session = Depends(get_db)) -> ScreenOut:
    """Retrieve screen details by ID."""
    screen = db.get(Screen, screen_id)
    if not screen:
        raise NotFoundError(f"Screen with ID {screen_id} was not found")
    return screen


@router.get("/{screen_id}/seats", response_model=List[SeatOut])
def get_screen_seats(screen_id: int, db: Session = Depends(get_db)) -> List[SeatOut]:
    """Retrieve all physical seats configured inside a screen."""
    screen = db.get(Screen, screen_id)
    if not screen:
        raise NotFoundError(f"Screen with ID {screen_id} was not found")

    seats = db.scalars(
        select(Seat).where(Seat.screen_id == screen_id).order_by(Seat.row_label.asc(), Seat.seat_number.asc())
    ).all()
    return seats


@router.post("", response_model=ScreenOut, status_code=status.HTTP_201_CREATED)
def create_screen(payload: ScreenCreate, db: Session = Depends(get_db)) -> ScreenOut:
    """Create a new screen and automatically initialize its physical seat layout."""
    theatre = db.get(Theatre, payload.theatre_id)
    if not theatre:
        raise NotFoundError(f"Theatre with ID {payload.theatre_id} was not found")

    screen = Screen(
        theatre_id=payload.theatre_id,
        name=payload.name,
        total_rows=payload.total_rows,
        seats_per_row=payload.seats_per_row,
    )
    db.add(screen)
    db.flush()

    # Generate seats
    # Assign regular, premium, and recliner based on row position
    seats_to_insert = []
    for r_idx in range(screen.total_rows):
        row_label = chr(65 + r_idx)  # A, B, C, ...
        # If last row and rows > 3: recliner. If second to last: premium. Else regular.
        if screen.total_rows >= 4:
            if r_idx == screen.total_rows - 1:
                seat_type = SeatType.RECLINER
            elif r_idx >= screen.total_rows - 2:
                seat_type = SeatType.PREMIUM
            else:
                seat_type = SeatType.REGULAR
        else:
            seat_type = SeatType.REGULAR

        for seat_num in range(1, screen.seats_per_row + 1):
            seats_to_insert.append(
                Seat(
                    screen_id=screen.id,
                    row_label=row_label,
                    seat_number=seat_num,
                    seat_type=seat_type,
                )
            )

    db.add_all(seats_to_insert)
    db.commit()
    db.refresh(screen)
    return screen
