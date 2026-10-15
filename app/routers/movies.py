"""Movies router providing full CRUD, pagination, filtering, and sorting."""

import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth import require_admin
from app.database import get_db
from app.errors import NotFoundError
from app.models import Movie, Screen, Show, Theatre, User
from app.schemas import MovieCreate, MovieOut, MovieUpdate, PaginatedResponse

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get("", response_model=PaginatedResponse[MovieOut])
def list_movies(
    genre: Optional[str] = None,
    language: Optional[str] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("release_date_desc"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[MovieOut]:
    """Retrieve paginated movies with optional genre, language, city, search query, and sorting."""
    stmt = select(Movie)

    if is_active is not None:
        stmt = stmt.where(Movie.is_active == is_active)

    if genre:
        stmt = stmt.where(func.lower(Movie.genre) == genre.strip().lower())

    if language:
        stmt = stmt.where(func.lower(Movie.language) == language.strip().lower())

    if search:
        search_filter = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(Movie.title).like(search_filter)
            | func.lower(Movie.description).like(search_filter)
        )

    if city:
        # Filter movies currently scheduled in screens within theatres in this city
        stmt = stmt.join(Show, Show.movie_id == Movie.id)\
                   .join(Screen, Screen.id == Show.screen_id)\
                   .join(Theatre, Theatre.id == Screen.theatre_id)\
                   .where(func.lower(Theatre.city) == city.strip().lower())\
                   .distinct()

    # Sorting
    sort_map = {
        "release_date_desc": Movie.release_date.desc(),
        "release_date_asc": Movie.release_date.asc(),
        "title_asc": Movie.title.asc(),
        "title_desc": Movie.title.desc(),
        "duration_desc": Movie.duration_min.desc(),
        "duration_asc": Movie.duration_min.asc(),
    }
    stmt = stmt.order_by(sort_map.get(sort_by, Movie.release_date.desc()))

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Paginate
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


@router.get("/{movie_id}", response_model=MovieOut)
def get_movie(movie_id: int, db: Session = Depends(get_db)) -> MovieOut:
    """Retrieve details of a single movie by its primary key ID."""
    movie = db.get(Movie, movie_id)
    if not movie:
        raise NotFoundError(f"Movie with ID {movie_id} was not found")
    return movie


@router.post("", response_model=MovieOut, status_code=status.HTTP_201_CREATED)
def create_movie(
    payload: MovieCreate,
    db: Session = Depends(get_db),
    admin: Optional[User] = Depends(require_admin),
) -> MovieOut:
    """Create a new movie record."""
    movie = Movie(**payload.model_dump())
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


@router.put("/{movie_id}", response_model=MovieOut)
def update_movie(
    movie_id: int,
    payload: MovieUpdate,
    db: Session = Depends(get_db),
    admin: Optional[User] = Depends(require_admin),
) -> MovieOut:
    """Update an existing movie record."""
    movie = db.get(Movie, movie_id)
    if not movie:
        raise NotFoundError(f"Movie with ID {movie_id} was not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(movie, field, value)

    db.commit()
    db.refresh(movie)
    return movie


@router.delete("/{movie_id}", status_code=status.HTTP_200_OK)
def delete_movie(
    movie_id: int,
    db: Session = Depends(get_db),
    admin: Optional[User] = Depends(require_admin),
) -> dict:
    """Soft-delete a movie by deactivating it."""
    movie = db.get(Movie, movie_id)
    if not movie:
        raise NotFoundError(f"Movie with ID {movie_id} was not found")

    movie.is_active = False
    db.commit()
    return {"message": "Movie deactivated successfully", "id": movie_id}
