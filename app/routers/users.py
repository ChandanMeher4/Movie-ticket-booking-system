"""Users router for customer and administrator profile management."""

import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.errors import ConflictError, NotFoundError
from app.models import User, UserRole
from app.schemas import PaginatedResponse, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=PaginatedResponse[UserOut])
def list_users(
    role: Optional[UserRole] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UserOut]:
    """List users with optional role filtering and pagination."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.id.asc())

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


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserOut:
    """Retrieve user profile by ID."""
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError(f"User with ID {user_id} was not found")
    return user


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    """Register a new customer or admin."""
    existing = db.scalar(select(User.id).where(User.email == payload.email).limit(1))
    if existing:
        raise ConflictError(f"A user with email {payload.email} already exists")

    user = User(**payload.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: UserUpdate, db: Session = Depends(get_db)
) -> UserOut:
    """Update user contact details or role."""
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError(f"User with ID {user_id} was not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user
