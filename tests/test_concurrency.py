"""Concurrency and race condition tests.

Verifies that when two attempts target the identical seat in the same show,
exactly one succeeds (201) and the colliding attempt is safely rejected with 409 Conflict,
backed by the database composite UNIQUE(show_id, seat_id) constraint.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import Booking, BookingSeat, BookingStatus, Movie, Screen, Show, ShowStatus


def test_concurrent_seat_booking_race_condition(client: TestClient, db_session: Session):
    """Simulate two users attempting to reserve the exact same seat.

    Verifies the DB composite UNIQUE(show_id, seat_id) constraint and transactional
    booking service guarantee that the first attempt succeeds and the competing attempt
    receives 409 Conflict.
    """
    now = datetime.utcnow()
    screen = db_session.get(Screen, 1)
    movie = db_session.get(Movie, 1)

    # Create a fresh future show for the race test
    race_show = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=36),
        end_time=now + timedelta(hours=38),
        base_price=Decimal("250.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(race_show)
    db_session.commit()
    race_show_id = race_show.id

    # Pick the first seat on this screen
    screen_seats = client.get(f"/api/screens/{screen.id}/seats").json()
    contested_seat_id = screen_seats[0]["id"]

    payload_user1 = {
        "user_id": 2,
        "show_id": race_show_id,
        "seat_ids": [contested_seat_id],
    }
    payload_user2 = {
        "user_id": 3,
        "show_id": race_show_id,
        "seat_ids": [contested_seat_id],
    }

    # Attempt 1: User 1 claims the contested seat
    res1 = client.post("/api/bookings", json=payload_user1)
    assert res1.status_code == 201, f"Expected 201 Created for first user, got {res1.status_code}"
    data1 = res1.json()
    assert data1["status"] == "pending"

    # Attempt 2: User 2 simultaneously attempts to claim the exact same seat
    res2 = client.post("/api/bookings", json=payload_user2)
    assert res2.status_code == 409, f"Expected 409 Conflict for second user, got {res2.status_code}"
    data2 = res2.json()
    assert data2["error"]["code"] == "RESOURCE_CONFLICT"
    assert "already been booked or held" in data2["error"]["message"].lower()


def test_db_unique_constraint_prevents_duplicate_booking_seats(db_session: Session):
    """Verify that the database layer strictly prohibits duplicate (show_id, seat_id) pairs."""
    now = datetime.utcnow()
    screen = db_session.get(Screen, 1)
    movie = db_session.get(Movie, 1)

    show = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=48),
        end_time=now + timedelta(hours=50),
        base_price=Decimal("200.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(show)
    db_session.commit()

    b1 = Booking(user_id=2, show_id=show.id, status=BookingStatus.PENDING, total_amount=Decimal("200.00"), expires_at=now + timedelta(minutes=5))
    b2 = Booking(user_id=3, show_id=show.id, status=BookingStatus.PENDING, total_amount=Decimal("200.00"), expires_at=now + timedelta(minutes=5))
    db_session.add_all([b1, b2])
    db_session.commit()

    seat = screen.seats[0]

    # First booking seat assignment succeeds
    bs1 = BookingSeat(booking_id=b1.id, show_id=show.id, seat_id=seat.id, price=Decimal("200.00"))
    db_session.add(bs1)
    db_session.commit()

    # Second booking seat assignment for identical (show_id, seat_id) MUST violate unique constraint
    bs2 = BookingSeat(booking_id=b2.id, show_id=show.id, seat_id=seat.id, price=Decimal("200.00"))
    db_session.add(bs2)
    with pytest.raises((IntegrityError, Exception)):
        db_session.commit()
    db_session.rollback()


def test_concurrent_threads_ten_users_same_seat_race_condition(db_session: Session):
    """Simulate 10 concurrent threads simultaneously trying to book the exact same seat.

    Uses real separate worker threads and isolated database sessions to prove
    that the unique constraint and transactional isolation guarantee:
    - Exactly 1 thread succeeds (holding the seat)
    - Exactly 9 threads receive 409 Conflict
    - Exactly 1 row is written in booking_seats
    """
    import concurrent.futures
    from app.errors import ConflictError
    from app.services.booking_service import hold_seats
    from tests.conftest import TestingSessionLocal

    now = datetime.utcnow()
    screen = db_session.get(Screen, 1)
    movie = db_session.get(Movie, 1)

    show = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=60),
        end_time=now + timedelta(hours=62),
        base_price=Decimal("300.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(show)
    db_session.commit()
    target_show_id = show.id

    contested_seat_id = screen.seats[1].id

    results = []

    def attempt_booking(thread_index: int):
        thread_db = TestingSessionLocal()
        user_id = 2 if thread_index % 2 == 0 else 3
        try:
            booking = hold_seats(
                db=thread_db,
                user_id=user_id,
                show_id=target_show_id,
                seat_ids=[contested_seat_id],
            )
            return {"status": 201, "booking_id": booking.id, "error": None}
        except ConflictError as exc:
            return {"status": 409, "booking_id": None, "error": str(exc)}
        except Exception as exc:
            return {"status": 500, "booking_id": None, "error": str(exc)}
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_booking, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r["status"] == 201]
    conflicts = [r for r in results if r["status"] == 409]

    assert len(successes) == 1, f"Expected exactly 1 successful booking, got {len(successes)}: {results}"
    assert len(conflicts) == 9, f"Expected exactly 9 conflicts (409), got {len(conflicts)}: {results}"

    # Verify that the booking_seats table contains precisely one row for this (show_id, seat_id)
    seat_rows = db_session.query(BookingSeat).filter(
        BookingSeat.show_id == target_show_id,
        BookingSeat.seat_id == contested_seat_id,
    ).all()
    assert len(seat_rows) == 1, f"Expected exactly 1 booking_seat row in database, found {len(seat_rows)}"

