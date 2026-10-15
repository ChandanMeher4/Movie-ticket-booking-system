"""Theatres router providing CRUD operations and city-based filtering."""

import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.errors import NotFoundError
from app.models import Theatre
from app.schemas import PaginatedResponse, TheatreCreate, TheatreDetailOut, TheatreOut, TheatreUpdate

router = APIRouter(prefix="/api/theatres", tags=["theatres"])


@router.get("", response_model=PaginatedResponse[TheatreOut])
def list_theatres(
    city: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TheatreOut]:
    """Retrieve theatres with optional city filter and pagination."""
    stmt = select(Theatre)
    if city:
        stmt = stmt.where(func.lower(Theatre.city) == city.strip().lower())

    stmt = stmt.order_by(Theatre.name.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    items = db.scalars(stmt.offset(offset).limit(page_size)).all()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{theatre_id}", response_model=TheatreDetailOut)
def get_theatre(theatre_id: int, db: Session = Depends(get_db)) -> TheatreDetailOut:
    """Retrieve theatre by ID along with its screens."""
    theatre = db.get(Theatre, theatre_id)
    if not theatre:
        raise NotFoundError(f"Theatre with ID {theatre_id} was not found")
    return theatre


@router.post("", response_model=TheatreOut, status_code=status.HTTP_201_CREATED)
def create_theatre(payload: TheatreCreate, db: Session = Depends(get_db)) -> TheatreOut:
    """Register a new cinema theatre."""
    theatre = Theatre(**payload.model_dump())
    db.add(theatre)
    db.commit()
    db.refresh(theatre)
    return theatre


@router.put("/{theatre_id}", response_model=TheatreOut)
def update_theatre(
    theatre_id: int, payload: TheatreUpdate, db: Session = Depends(get_db)
) -> TheatreOut:
    """Update theatre details."""
    theatre = db.get(Theatre, theatre_id)
    if not theatre:
        raise NotFoundError(f"Theatre with ID {theatre_id} was not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(theatre, field, value)

    db.commit()
    db.refresh(theatre)
    return theatre


@router.delete("/{theatre_id}", status_code=status.HTTP_200_OK)
def delete_theatre(theatre_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete a theatre and cascade-delete its screens/shows."""
    theatre = db.get(Theatre, theatre_id)
    if not theatre:
        raise NotFoundError(f"Theatre with ID {theatre_id} was not found")

    db.delete(theatre)
    db.commit()
    return {"message": "Theatre deleted successfully", "id": theatre_id}
