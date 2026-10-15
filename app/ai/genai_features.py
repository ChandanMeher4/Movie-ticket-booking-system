"""Generative AI features executing single LLM completions without tools.

Implements movie summarization, catalog mood recommendations, review sentiment analysis,
and personalized booking confirmation emails with Pydantic validation and retry logic.
"""

import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_client import llm_client
from app.ai.prompts import (
    BOOKING_EMAIL_SYSTEM_PROMPT,
    MOVIE_SUMMARY_SYSTEM_PROMPT,
    RECOMMEND_SYSTEM_PROMPT,
    REVIEW_SUMMARY_SYSTEM_PROMPT,
)
from app.errors import BadRequestError, NotFoundError
from app.models import Booking, Movie

logger = logging.getLogger("genai_features")


# --- Output Schemas for Structured JSON Validation ---

class MovieRecommendation(BaseModel):
    movie_id: int
    title: str
    match_score: int = Field(..., ge=1, le=100)
    reason: str


class RecommendationResponse(BaseModel):
    mood: str
    recommendations: List[MovieRecommendation]
    mock: bool = False


class ReviewSummaryResponse(BaseModel):
    sentiment: str = Field(..., pattern="^(positive|mixed|negative)$")
    summary: str
    pros: List[str]
    cons: List[str]
    mock: bool = False


class MovieSummaryResponse(BaseModel):
    movie_id: int
    title: str
    tone: str
    summary: str
    mock: bool = False


class BookingEmailResponse(BaseModel):
    booking_id: int
    email_text: str
    mock: bool = False


def clean_json_text(text: str) -> str:
    """Strip markdown code fence blocks if returned by the LLM."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
    return cleaned


def generate_movie_summary(db: Session, movie_id: int, tone: str = "exciting") -> MovieSummaryResponse:
    """Generate a spoiler-free marketing blurb in the requested tone."""
    movie = db.get(Movie, movie_id)
    if not movie:
        raise NotFoundError(f"Movie with ID {movie_id} was not found")

    system_prompt = MOVIE_SUMMARY_SYSTEM_PROMPT.format(tone=tone)
    user_prompt = (
        f"Movie Title: {movie.title}\n"
        f"Genre: {movie.genre}\n"
        f"Language: {movie.language}\n"
        f"Runtime: {movie.duration_min} minutes\n"
        f"Rating: {movie.rating.value}\n"
        f"Synopsis: {movie.description}\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = llm_client.chat_completion(messages, temperature=0.7)
    summary_text = response.content or ""

    return MovieSummaryResponse(
        movie_id=movie.id,
        title=movie.title,
        tone=tone,
        summary=summary_text.strip(),
        mock=response.mock,
    )


def recommend_movies(db: Session, mood: str) -> RecommendationResponse:
    """Recommend 3 movies matching the user's mood from active catalog with structured validation."""
    if not mood or not mood.strip():
        raise BadRequestError("Mood/preference text cannot be empty")

    # Truncate input size for guardrails
    sanitized_mood = mood.strip()[:300]

    # Ingest active catalog
    active_movies = db.scalars(select(Movie).where(Movie.is_active == True)).all()
    catalog_lines = []
    for m in active_movies:
        catalog_lines.append(f"- ID {m.id}: '{m.title}' | Genre: {m.genre} | Language: {m.language} | {m.description}")
    catalog_str = "\n".join(catalog_lines)

    system_prompt = RECOMMEND_SYSTEM_PROMPT.format(mood=sanitized_mood, catalog=catalog_str)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Find the best 3 movies for my mood: {sanitized_mood}"},
    ]

    # First attempt
    response = llm_client.chat_completion(
        messages,
        temperature=0.4,
        response_format={"type": "json_object"} if not llm_client.is_mock else None,
    )

    raw_content = clean_json_text(response.content or "{}")
    try:
        data = json.loads(raw_content)
        recommendations = [MovieRecommendation(**item) for item in data.get("recommendations", [])]
    except Exception as exc:
        logger.warning("JSON parse failed on recommendation (%s). Retrying once with strict correction prompt.", exc)
        # Single Retry
        retry_messages = messages + [
            {"role": "assistant", "content": raw_content},
            {"role": "user", "content": "Your previous response was not valid JSON. Please reply with ONLY the pure JSON object."},
        ]
        retry_res = llm_client.chat_completion(retry_messages, temperature=0.2)
        raw_retry = clean_json_text(retry_res.content or "{}")
        data = json.loads(raw_retry)
        recommendations = [MovieRecommendation(**item) for item in data.get("recommendations", [])]

    return RecommendationResponse(
        mood=sanitized_mood,
        recommendations=recommendations,
        mock=response.mock,
    )


def summarize_reviews(reviews: List[str]) -> ReviewSummaryResponse:
    """Summarize customer review feedback into sentiment, pros, and cons."""
    if not reviews:
        raise BadRequestError("At least one review must be provided")

    # Truncate input review collection (max 10 reviews, max 500 chars each)
    truncated_reviews = [r.strip()[:500] for r in reviews[:10] if r.strip()]
    reviews_formatted = "\n".join([f"{idx+1}. \"{r}\"" for idx, r in enumerate(truncated_reviews)])

    system_prompt = REVIEW_SUMMARY_SYSTEM_PROMPT.format(reviews=reviews_formatted)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Analyze audience sentiment and produce the structured JSON summary."},
    ]

    response = llm_client.chat_completion(
        messages,
        temperature=0.3,
        response_format={"type": "json_object"} if not llm_client.is_mock else None,
    )

    raw_content = clean_json_text(response.content or "{}")
    try:
        data = json.loads(raw_content)
        parsed = ReviewSummaryResponse(**data, mock=response.mock)
        return parsed
    except Exception as exc:
        logger.warning("Review summary JSON parse failed (%s). Retrying once.", exc)
        retry_messages = messages + [
            {"role": "assistant", "content": raw_content},
            {"role": "user", "content": "Invalid JSON format. Output ONLY the raw JSON object adhering to the specified schema."},
        ]
        retry_res = llm_client.chat_completion(retry_messages, temperature=0.1)
        data = json.loads(clean_json_text(retry_res.content or "{}"))
        return ReviewSummaryResponse(**data, mock=retry_res.mock)


def generate_booking_email(db: Session, booking_id: int) -> BookingEmailResponse:
    """Generate a customer booking confirmation email."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise NotFoundError(f"Booking with ID {booking_id} was not found")

    user = booking.user
    show = booking.show
    movie = show.movie
    screen = show.screen
    theatre = screen.theatre

    seats_list = []
    for bs in booking.booking_seats:
        s = bs.seat
        seats_list.append(f"{s.row_label}{s.seat_number} ({s.seat_type.value})")
    seats_str = ", ".join(seats_list) if seats_list else "General Admission"

    system_prompt = BOOKING_EMAIL_SYSTEM_PROMPT.format(
        customer_name=user.name,
        movie_title=movie.title,
        theatre_name=theatre.name,
        city=theatre.city,
        screen_name=screen.name,
        showtime=show.start_time.strftime("%A, %d %B %Y at %I:%M %p"),
        seats=seats_str,
        total_amount=f"{booking.total_amount:.2f}",
        booking_id=booking.id,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate the confirmation email for booking #{booking.id}."},
    ]

    response = llm_client.chat_completion(messages, temperature=0.6)
    email_text = response.content or ""

    return BookingEmailResponse(
        booking_id=booking.id,
        email_text=email_text.strip(),
        mock=response.mock,
    )
