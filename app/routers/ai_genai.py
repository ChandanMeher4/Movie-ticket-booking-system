"""Generative AI router exposing single-turn AI features without tools."""

from typing import List
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.genai_features import (
    BookingEmailResponse,
    MovieSummaryResponse,
    RecommendationResponse,
    ReviewSummaryResponse,
    generate_booking_email,
    generate_movie_summary,
    recommend_movies,
    summarize_reviews,
)
from app.database import get_db

router = APIRouter(prefix="/api/ai/genai", tags=["genai"])


class MovieSummaryRequest(BaseModel):
    movie_id: int = Field(..., description="ID of the movie to summarize")
    tone: str = Field(default="exciting", description="Copywriting tone: exciting, poetic, family-friendly, dramatic")


class RecommendRequest(BaseModel):
    mood: str = Field(..., min_length=2, max_length=300, description="Viewer mood, vibe, or genre interest")


class ReviewSummarizeRequest(BaseModel):
    reviews: List[str] = Field(..., min_length=1, description="List of raw customer reviews")


class BookingEmailRequest(BaseModel):
    booking_id: int = Field(..., description="ID of the confirmed booking")


@router.post("/movie-summary", response_model=MovieSummaryResponse, status_code=status.HTTP_200_OK)
def create_movie_summary(
    payload: MovieSummaryRequest, db: Session = Depends(get_db)
) -> MovieSummaryResponse:
    """Generate a spoiler-free marketing synopsis for a movie in a chosen tone."""
    return generate_movie_summary(db=db, movie_id=payload.movie_id, tone=payload.tone)


@router.post("/recommend", response_model=RecommendationResponse, status_code=status.HTTP_200_OK)
def create_recommendations(
    payload: RecommendRequest, db: Session = Depends(get_db)
) -> RecommendationResponse:
    """Analyze viewer mood and return 3 ranked movie recommendations from the active catalog."""
    return recommend_movies(db=db, mood=payload.mood)


@router.post("/review-summarize", response_model=ReviewSummaryResponse, status_code=status.HTTP_200_OK)
def create_review_summary(payload: ReviewSummarizeRequest) -> ReviewSummaryResponse:
    """Summarize customer review feedback into overall sentiment, pros, and cons."""
    return summarize_reviews(reviews=payload.reviews)


@router.post("/booking-email", response_model=BookingEmailResponse, status_code=status.HTTP_200_OK)
def create_booking_email(
    payload: BookingEmailRequest, db: Session = Depends(get_db)
) -> BookingEmailResponse:
    """Generate a personalized booking confirmation email text."""
    return generate_booking_email(db=db, booking_id=payload.booking_id)
