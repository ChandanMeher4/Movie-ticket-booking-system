"""Tests for Pydantic v2 schemas and domain business rule validations."""

from datetime import datetime, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Movie, Screen, Show, ShowStatus


def test_max_six_seats_limit(client: TestClient):
    """Verify selecting more than 6 seats fails with validation error (422)."""
    payload = {
        "user_id": 2,
        "show_id": 1,
        "seat_ids": [1, 2, 3, 4, 5, 6, 7],  # 7 seats
    }
    response = client.post("/api/bookings", json=payload)
    assert response.status_code == 422
    err = response.json()
    assert err["error"]["code"] == "VALIDATION_ERROR"


def test_empty_seats_list(client: TestClient):
    """Verify empty seat selection fails with validation error (422)."""
    payload = {
        "user_id": 2,
        "show_id": 1,
        "seat_ids": [],
    }
    response = client.post("/api/bookings", json=payload)
    assert response.status_code == 422
    err = response.json()
    assert err["error"]["code"] == "VALIDATION_ERROR"


def test_seat_from_different_screen(client: TestClient):
    """Verify selecting a seat that belongs to another screen is rejected."""
    # Find a future show on Screen 1
    shows = client.get("/api/shows?page_size=20").json()["items"]
    future_show = next(s for s in shows if datetime.fromisoformat(s["start_time"]) > datetime.utcnow() + timedelta(days=1))
    show_id = future_show["id"]
    screen_id = future_show["screen_id"]

    # Pick another screen
    other_screen_id = 2 if screen_id == 1 else 1
    other_screen_seats = client.get(f"/api/screens/{other_screen_id}/seats").json()
    other_screen_seat_id = other_screen_seats[0]["id"]

    payload = {
        "user_id": 2,
        "show_id": show_id,
        "seat_ids": [other_screen_seat_id],
    }
    response = client.post("/api/bookings", json=payload)
    assert response.status_code == 422
    err = response.json()
    assert "does not belong to the screen" in err["error"]["message"].lower()


def test_cannot_book_past_show(client: TestClient, db_session: Session):
    """Verify attempting to book a show in the past is rejected with 400 Bad Request."""
    now = datetime.utcnow()
    screen = db_session.get(Screen, 1)
    movie = db_session.get(Movie, 1)

    past_show = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=1),
        base_price=Decimal("200.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(past_show)
    db_session.commit()
    past_show_id = past_show.id

    seat_id = client.get(f"/api/screens/{screen.id}/seats").json()[0]["id"]

    response = client.post(
        "/api/bookings",
        json={"user_id": 2, "show_id": past_show_id, "seat_ids": [seat_id]},
    )
    assert response.status_code == 400
    assert "started or concluded" in response.json()["error"]["message"]


def test_cannot_book_cancelled_show(client: TestClient, db_session: Session):
    """Verify attempting to book a cancelled show is rejected with 400 Bad Request."""
    now = datetime.utcnow()
    screen = db_session.get(Screen, 1)
    movie = db_session.get(Movie, 1)

    cancelled_show = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=20),
        end_time=now + timedelta(hours=22),
        base_price=Decimal("200.00"),
        status=ShowStatus.CANCELLED,
    )
    db_session.add(cancelled_show)
    db_session.commit()
    cancelled_show_id = cancelled_show.id

    seat_id = client.get(f"/api/screens/{screen.id}/seats").json()[0]["id"]

    response = client.post(
        "/api/bookings",
        json={"user_id": 2, "show_id": cancelled_show_id, "seat_ids": [seat_id]},
    )
    assert response.status_code == 400
    assert "cancelled" in response.json()["error"]["message"].lower()


def test_phone_validation_regex(client: TestClient):
    """Verify invalid phone format is rejected with 422."""
    payload = {
        "name": "Invalid Phone User",
        "email": "invalid.phone@example.com",
        "phone": "abc-not-a-phone",
        "role": "customer",
    }
    response = client.post("/api/users", json=payload)
    assert response.status_code == 422
    err = response.json()
    assert err["error"]["code"] == "VALIDATION_ERROR"


def test_show_base_price_must_be_positive(client: TestClient):
    """Verify base_price <= 0 is rejected with 422."""
    now = datetime.utcnow()
    payload = {
        "movie_id": 1,
        "screen_id": 1,
        "start_time": (now + timedelta(hours=5)).isoformat(),
        "end_time": (now + timedelta(hours=7)).isoformat(),
        "base_price": "0.00",  # must be gt 0
        "status": "scheduled",
    }
    response = client.post("/api/shows", json=payload, headers={"X-User-Id": "1"})
    assert response.status_code == 422
