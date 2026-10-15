"""Tests for seat map, holds, payments, expiry, cancellations, and refunds."""

from datetime import datetime, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Booking, BookingStatus, Movie, Screen, Seat, Show, ShowStatus, User


def test_get_show_seat_map(client: TestClient):
    """Verify seat map returns all physical seats with availability status and pricing."""
    # Show 1
    response = client.get("/api/shows/1/seats")
    assert response.status_code == 200
    seats = response.json()
    assert len(seats) == 40
    for seat in seats:
        assert "id" in seat
        assert "row_label" in seat
        assert "seat_number" in seat
        assert "seat_type" in seat
        assert "price" in seat
        assert seat["status"] in ("available", "held", "booked")


def test_hold_and_confirm_booking_flow(client: TestClient):
    """Verify end-to-end reservation: seat hold -> payment confirmation -> booked status."""
    # Find a future show
    shows_res = client.get("/api/shows?page_size=10")
    shows = shows_res.json()["items"]
    # Pick a show with future start_time
    now = datetime.utcnow()
    target_show = None
    for s in shows:
        st = datetime.fromisoformat(s["start_time"])
        if st > now + timedelta(hours=30):
            target_show = s
            break
    assert target_show is not None

    show_id = target_show["id"]
    screen_id = target_show["screen_id"]

    # Get available seats for this screen
    seats_res = client.get(f"/api/screens/{screen_id}/seats")
    screen_seats = seats_res.json()
    seat1_id = screen_seats[0]["id"]
    seat2_id = screen_seats[1]["id"]

    # 1. Hold seats
    hold_payload = {
        "user_id": 2,
        "show_id": show_id,
        "seat_ids": [seat1_id, seat2_id],
    }
    hold_res = client.post("/api/bookings", json=hold_payload)
    assert hold_res.status_code == 201
    booking = hold_res.json()
    assert booking["status"] == "pending"
    booking_id = booking["id"]
    assert len(booking["booking_seats"]) == 2

    # Verify seat map marks them as "held"
    map_res = client.get(f"/api/shows/{show_id}/seats")
    seat_map = {s["id"]: s["status"] for s in map_res.json()}
    assert seat_map[seat1_id] == "held"
    assert seat_map[seat2_id] == "held"

    # Attempting to hold again immediately should fail with 409 Conflict
    conflict_res = client.post("/api/bookings", json=hold_payload)
    assert conflict_res.status_code == 409
    assert conflict_res.json()["error"]["code"] == "RESOURCE_CONFLICT"

    # 2. Confirm booking via payment
    pay_payload = {
        "booking_id": booking_id,
        "method": "upi",
    }
    pay_res = client.post("/api/payments", json=pay_payload)
    assert pay_res.status_code == 200
    payment = pay_res.json()
    assert payment["status"] == "success"
    assert payment["txn_ref"].startswith("TXN-")

    # Verify booking status is now confirmed
    booking_res = client.get(f"/api/bookings/{booking_id}")
    assert booking_res.status_code == 200
    assert booking_res.json()["status"] == "confirmed"

    # Verify seat map marks them as "booked"
    map_res2 = client.get(f"/api/shows/{show_id}/seats")
    seat_map2 = {s["id"]: s["status"] for s in map_res2.json()}
    assert seat_map2[seat1_id] == "booked"
    assert seat_map2[seat2_id] == "booked"


def test_hold_expiry_releases_seats(client: TestClient, db_session: Session):
    """Verify that seats held for >5 minutes expire and become available again."""
    # Find a future show
    shows_res = client.get("/api/shows?page_size=10")
    target_show = shows_res.json()["items"][3]
    show_id = target_show["id"]
    screen_id = target_show["screen_id"]

    seats = client.get(f"/api/screens/{screen_id}/seats").json()
    seat_id = seats[5]["id"]

    # Hold seat
    hold_res = client.post(
        "/api/bookings",
        json={"user_id": 2, "show_id": show_id, "seat_ids": [seat_id]},
    )
    assert hold_res.status_code == 201
    booking_id = hold_res.json()["id"]

    # Manually expire the hold in the database by setting expires_at to the past
    booking = db_session.get(Booking, booking_id)
    booking.expires_at = datetime.utcnow() - timedelta(minutes=10)
    db_session.commit()
    db_session.expire_all()

    # Query seat map - this triggers release_expired_holds
    seat_map_res = client.get(f"/api/shows/{show_id}/seats")
    seat_map = {s["id"]: s["status"] for s in seat_map_res.json()}
    assert seat_map[seat_id] == "available"

    # Attempting to pay for expired booking should fail with 400
    pay_res = client.post(
        "/api/payments",
        json={"booking_id": booking_id, "method": "card"},
    )
    assert pay_res.status_code == 400
    msg = pay_res.json()["error"]["message"].lower()
    assert "expired" in msg or "cancelled" in msg


def test_cancellation_and_refund_tiers(client: TestClient, db_session: Session):
    """Verify cancellation rules: 100% refund (>24h), 50% refund (2-24h), disallowed (<2h)."""
    # 1. Test 100% Refund (> 24 hours before showtime)
    now = datetime.utcnow()
    screen = db_session.get(Screen, 1)
    movie = db_session.get(Movie, 1)

    show_48h = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=48),
        end_time=now + timedelta(hours=50),
        base_price=Decimal("200.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(show_48h)
    db_session.commit()
    show_48h_id = show_48h.id

    seat_res = client.get(f"/api/screens/{screen.id}/seats").json()
    seat_id = seat_res[8]["id"]

    # Hold and confirm
    hold_res = client.post(
        "/api/bookings",
        json={"user_id": 3, "show_id": show_48h_id, "seat_ids": [seat_id]},
    )
    booking_id = hold_res.json()["id"]
    client.post("/api/payments", json={"booking_id": booking_id, "method": "card"})

    # Cancel > 24h
    cancel_res = client.post(f"/api/bookings/{booking_id}/cancel")
    assert cancel_res.status_code == 200
    data = cancel_res.json()
    assert data["refund_percentage"] == 100
    assert Decimal(str(data["refund_amount"])) == Decimal(str(data["original_amount"]))

    # 2. Test 50% Refund (between 2 and 24 hours before showtime)
    show_10h = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=10),
        end_time=now + timedelta(hours=12),
        base_price=Decimal("200.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(show_10h)
    db_session.commit()
    show_10h_id = show_10h.id

    hold_res2 = client.post(
        "/api/bookings",
        json={"user_id": 3, "show_id": show_10h_id, "seat_ids": [seat_id]},
    )
    booking_id2 = hold_res2.json()["id"]
    client.post("/api/payments", json={"booking_id": booking_id2, "method": "wallet"})

    cancel_res2 = client.post(f"/api/bookings/{booking_id2}/cancel")
    assert cancel_res2.status_code == 200
    data2 = cancel_res2.json()
    assert data2["refund_percentage"] == 50
    expected_half = (Decimal(str(data2["original_amount"])) * Decimal("0.5")).quantize(Decimal("0.01"))
    assert Decimal(str(data2["refund_amount"])) == expected_half

    # 3. Test Disallowed (< 2 hours before showtime)
    show_1h = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        base_price=Decimal("200.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(show_1h)
    db_session.commit()
    show_1h_id = show_1h.id

    hold_res3 = client.post(
        "/api/bookings",
        json={"user_id": 3, "show_id": show_1h_id, "seat_ids": [seat_id]},
    )
    booking_id3 = hold_res3.json()["id"]
    client.post("/api/payments", json={"booking_id": booking_id3, "method": "card"})

    cancel_res3 = client.post(f"/api/bookings/{booking_id3}/cancel")
    assert cancel_res3.status_code == 400
    assert "2 hours" in cancel_res3.json()["error"]["message"]


def test_user_bookings_history(client: TestClient):
    """Verify retrieving bookings for a user."""
    res = client.get("/api/users/2/bookings", headers={"X-User-Id": "2"})
    assert res.status_code == 200
    bookings = res.json()
    assert isinstance(bookings, list)
    if bookings:
        assert "booking_seats" in bookings[0]
        assert "show" in bookings[0]


def test_cross_user_authorization_rejected(client: TestClient, db_session: Session):
    """Verify cross-user access is rejected with 403 Forbidden and non-existent booking returns 404."""
    from app.ai.tools import tool_cancel_booking

    now = datetime.utcnow()
    screen = db_session.get(Screen, 1)
    movie = db_session.get(Movie, 1)

    show = Show(
        movie_id=movie.id,
        screen_id=screen.id,
        start_time=now + timedelta(hours=30),
        end_time=now + timedelta(hours=32),
        base_price=Decimal("200.00"),
        status=ShowStatus.SCHEDULED,
    )
    db_session.add(show)
    db_session.commit()

    seat = screen.seats[2]

    # User 2 holds and confirms a booking
    hold_res = client.post("/api/bookings", json={"user_id": 2, "show_id": show.id, "seat_ids": [seat.id]})
    assert hold_res.status_code == 201
    booking_id = hold_res.json()["id"]

    client.post("/api/payments", json={"booking_id": booking_id, "method": "card"})

    # 1. User 3 attempts to view User 2's booking details -> 403 Forbidden
    view_res = client.get(f"/api/bookings/{booking_id}", headers={"X-User-Id": "3"})
    assert view_res.status_code == 403
    assert view_res.json()["error"]["code"] == "FORBIDDEN"

    # 2. User 3 attempts to cancel User 2's booking -> 403 Forbidden
    cancel_res = client.post(f"/api/bookings/{booking_id}/cancel", headers={"X-User-Id": "3"})
    assert cancel_res.status_code == 403
    assert cancel_res.json()["error"]["code"] == "FORBIDDEN"

    # 3. User 3 attempts to view User 2's booking history -> 403 Forbidden
    history_res = client.get("/api/users/2/bookings", headers={"X-User-Id": "3"})
    assert history_res.status_code == 403
    assert history_res.json()["error"]["code"] == "FORBIDDEN"

    # 4. Admin (User 1) can view User 2's booking -> 200 OK
    admin_view = client.get(f"/api/bookings/{booking_id}", headers={"X-User-Id": "1"})
    assert admin_view.status_code == 200

    # 5. Non-existent booking returns 404 Not Found
    not_found_res = client.get("/api/bookings/999999", headers={"X-User-Id": "2"})
    assert not_found_res.status_code == 404
    assert not_found_res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # 6. AI tool: tool_cancel_booking blocks cross-user cancellation
    tool_res = tool_cancel_booking(db_session, {"booking_id": booking_id, "user_id": 3})
    assert tool_res["success"] is False
    assert "unauthorized" in tool_res["error"].lower() or "permission" in tool_res["error"].lower()

