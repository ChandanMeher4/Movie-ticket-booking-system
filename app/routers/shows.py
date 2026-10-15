"""Shows router providing schedule management and search by movie, date, and city."""

from datetime import datetime, time
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth import require_admin
from app.database import get_db
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Movie, Screen, Show, ShowStatus, Theatre, User
from app.schemas import PaginatedResponse, ShowCreate, ShowDetailOut, ShowOut, ShowUpdate

router = APIRouter(prefix="/api/shows", tags=["shows"])


@router.get("", response_model=PaginatedResponse[ShowDetailOut])
def list_shows(
    movie_id: Optional[int] = None,
    date: Optional[str] = None,  # YYYY-MM-DD
    city: Optional[str] = None,
    status_filter: Optional[ShowStatus] = ShowStatus.SCHEDULED,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ShowDetailOut]:
    """Retrieve shows filtered by movie, calendar date, city, and status."""
    stmt = select(Show).join(Show.screen).join(Screen.theatre).join(Show.movie)

    if movie_id:
        stmt = stmt.where(Show.movie_id == movie_id)

    if status_filter:
        stmt = stmt.where(Show.status == status_filter)

    if city:
        stmt = stmt.where(func.lower(Theatre.city) == city.strip().lower())

    if date:
        try:
            parsed_date = datetime.strptime(date.strip(), "%Y-%m-%d").date()
            start_of_day = datetime.combine(parsed_date, time.min)
            end_of_day = datetime.combine(parsed_date, time.max)
            stmt = stmt.where(Show.start_time >= start_of_day, Show.start_time <= end_of_day)
        except ValueError:
            raise ValidationError("Invalid date format. Expected YYYY-MM-DD")

    stmt = stmt.order_by(Show.start_time.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    items = db.scalars(stmt.offset(offset).limit(page_size)).all()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Populate nested relations for detail output
    detailed_items = []
    for s in items:
        detail = ShowDetailOut(
            id=s.id,
            movie_id=s.movie_id,
            screen_id=s.screen_id,
            start_time=s.start_time,
            end_time=s.end_time,
            base_price=s.base_price,
            status=s.status,
            movie=s.movie,
            screen=s.screen,
            theatre=s.screen.theatre if s.screen else None,
        )
        detailed_items.append(detail)

    return PaginatedResponse(
        items=detailed_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{show_id}", response_model=ShowDetailOut)
def get_show(show_id: int, db: Session = Depends(get_db)) -> ShowDetailOut:
    """Retrieve detailed show information including movie, screen, and theatre."""
    show = db.get(Show, show_id)
    if not show:
        raise NotFoundError(f"Show with ID {show_id} was not found")

    return ShowDetailOut(
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


@router.post("", response_model=ShowOut, status_code=status.HTTP_201_CREATED)
def create_show(
    payload: ShowCreate,
    db: Session = Depends(get_db),
    admin: Optional[User] = Depends(require_admin),
) -> ShowOut:
    """Schedule a new show, validating that no overlapping shows run on the same screen."""
    movie = db.get(Movie, payload.movie_id)
    if not movie or not movie.is_active:
        raise NotFoundError(f"Active movie with ID {payload.movie_id} was not found")

    screen = db.get(Screen, payload.screen_id)
    if not screen:
        raise NotFoundError(f"Screen with ID {payload.screen_id} was not found")

    # Business Rule: Check screen overlap
    overlap = db.scalar(
        select(Show.id).where(
            Show.screen_id == payload.screen_id,
            Show.status != ShowStatus.CANCELLED,
            Show.start_time < payload.end_time,
            Show.end_time > payload.start_time,
        ).limit(1)
    )
    if overlap:
        raise ConflictError("Screen is already booked for another show during this time window")

    show = Show(**payload.model_dump())
    db.add(show)
    db.commit()
    db.refresh(show)
    return show


@router.put("/{show_id}", response_model=ShowOut)
def update_show(
    show_id: int,
    payload: ShowUpdate,
    db: Session = Depends(get_db),
    admin: Optional[User] = Depends(require_admin),
) -> ShowOut:
    """Update show timing, price, or cancellation status."""
    show = db.get(Show, show_id)
    if not show:
        raise NotFoundError(f"Show with ID {show_id} was not found")

    update_data = payload.model_dump(exclude_unset=True)
    new_start = update_data.get("start_time", show.start_time)
    new_end = update_data.get("end_time", show.end_time)

    if new_end <= new_start:
        raise ValidationError("end_time must be strictly greater than start_time")

    # If times changed, check overlap
    if "start_time" in update_data or "end_time" in update_data:
        overlap = db.scalar(
            select(Show.id).where(
                Show.id != show_id,
                Show.screen_id == show.screen_id,
                Show.status != ShowStatus.CANCELLED,
                Show.start_time < new_end,
                Show.end_time > new_start,
            ).limit(1)
        )
        if overlap:
            raise ConflictError("Screen is already booked for another show during the requested time window")

    for field, value in update_data.items():
        setattr(show, field, value)

    db.commit()
    db.refresh(show)
    return show


@router.delete("/{show_id}", status_code=status.HTTP_200_OK)
def cancel_show(
    show_id: int,
    db: Session = Depends(get_db),
    admin: Optional[User] = Depends(require_admin),
) -> dict:
    """Mark a show as cancelled."""
    show = db.get(Show, show_id)
    if not show:
        raise NotFoundError(f"Show with ID {show_id} was not found")

    show.status = ShowStatus.CANCELLED
    db.commit()
    return {"message": "Show cancelled successfully", "id": show_id}
