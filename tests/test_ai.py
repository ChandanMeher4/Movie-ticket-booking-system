"""Tests for Generative AI endpoints in deterministic mock fallback mode."""

from fastapi.testclient import TestClient


def test_genai_movie_summary(client: TestClient):
    """Verify movie summary returns marketing synopsis in chosen tone with mock: true."""
    payload = {
        "movie_id": 1,
        "tone": "exciting",
    }
    response = client.post("/api/ai/genai/movie-summary", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["movie_id"] == 1
    assert data["title"] == "Inception"
    assert data["tone"] == "exciting"
    assert len(data["summary"]) > 20
    assert data["mock"] is True


def test_genai_movie_summary_not_found(client: TestClient):
    """Verify movie summary for non-existent movie returns 404."""
    response = client.post("/api/ai/genai/movie-summary", json={"movie_id": 99999, "tone": "poetic"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_genai_recommendations_structured_output(client: TestClient):
    """Verify movie recommendations returns exactly 3 ranked movies with mock: true."""
    payload = {
        "mood": "I want an epic cosmic sci-fi journey with deep emotion",
    }
    response = client.post("/api/ai/genai/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["mock"] is True
    assert "recommendations" in data
    recs = data["recommendations"]
    assert len(recs) == 3
    for rec in recs:
        assert "movie_id" in rec
        assert "title" in rec
        assert 1 <= rec["match_score"] <= 100
        assert len(rec["reason"]) > 5


def test_genai_review_summarize_positive(client: TestClient):
    """Verify review summarizer produces structured pros/cons/sentiment analysis."""
    payload = {
        "reviews": [
            "An absolute masterpiece of cinema! The visuals were stunning and the cast was phenomenal.",
            "Loved every single minute of it. Brilliant direction and superb sound design.",
            "A bit long in the middle, but the climax completely blew me away. Great experience!",
        ]
    }
    response = client.post("/api/ai/genai/review-summarize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["mock"] is True
    assert data["sentiment"] in ("positive", "mixed", "negative")
    assert isinstance(data["pros"], list)
    assert len(data["pros"]) >= 1
    assert isinstance(data["cons"], list)
    assert len(data["summary"]) > 10


def test_genai_review_summarize_empty_error(client: TestClient):
    """Verify empty review list returns 422 validation error."""
    response = client.post("/api/ai/genai/review-summarize", json={"reviews": []})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_genai_booking_email(client: TestClient):
    """Verify booking confirmation email generation for a confirmed booking."""
    # First create and confirm a booking
    shows_res = client.get("/api/shows?page_size=5").json()["items"]
    show_id = shows_res[2]["id"]
    screen_id = shows_res[2]["screen_id"]

    seat_id = client.get(f"/api/screens/{screen_id}/seats").json()[12]["id"]

    hold_res = client.post(
        "/api/bookings",
        json={"user_id": 2, "show_id": show_id, "seat_ids": [seat_id]},
    )
    booking_id = hold_res.json()["id"]
    client.post("/api/payments", json={"booking_id": booking_id, "method": "card"})

    # Request email generation
    email_res = client.post("/api/ai/genai/booking-email", json={"booking_id": booking_id})
    assert email_res.status_code == 200
    data = email_res.json()
    assert data["booking_id"] == booking_id
    assert "Subject:" in data["email_text"]
    assert "Cineverse" in data["email_text"]
    assert data["mock"] is True
