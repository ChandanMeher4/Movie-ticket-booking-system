"""Tests for Shows and Theatres CRUD, conflict checks, and filtering."""

from datetime import datetime, timedelta
from fastapi.testclient import TestClient


def test_list_theatres(client: TestClient):
    """Verify listing theatres and filtering by city."""
    response = client.get("/api/theatres")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3

    mumbai_res = client.get("/api/theatres?city=Mumbai")
    assert mumbai_res.status_code == 200
    mumbai_data = mumbai_res.json()
    assert mumbai_data["total"] >= 1
    assert all("mumbai" in t["city"].lower() for t in mumbai_data["items"])


def test_list_shows_filtering(client: TestClient):
    """Verify show listing returns shows and filters by movie."""
    response = client.get("/api/shows")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 30

    # Filter by movie 2 (Interstellar)
    interstellar_res = client.get("/api/shows?movie_id=2")
    assert interstellar_res.status_code == 200
    inter_data = interstellar_res.json()
    assert inter_data["total"] >= 1
    for item in inter_data["items"]:
        assert item["movie_id"] == 2


def test_show_conflict_detection(client: TestClient):
    """Verify creating a show that overlaps with an existing show on the same screen returns 409 Conflict."""
    # First get an existing show to find its screen and window
    shows_res = client.get("/api/shows?page_size=1")
    first_show = shows_res.json()["items"][0]
    screen_id = first_show["screen_id"]
    start_time = first_show["start_time"]
    end_time = first_show["end_time"]

    # Attempt to schedule overlapping show
    overlap_payload = {
        "movie_id": 2,
        "screen_id": screen_id,
        "start_time": start_time,
        "end_time": end_time,
        "base_price": "300.00",
        "status": "scheduled",
    }
    conflict_res = client.post("/api/shows", json=overlap_payload, headers={"X-User-Id": "1"})
    assert conflict_res.status_code == 409
    err = conflict_res.json()
    assert "error" in err
    assert err["error"]["code"] == "RESOURCE_CONFLICT"
    assert "already booked" in err["error"]["message"].lower()


def test_create_show_forbidden_for_non_admin(client: TestClient):
    """Verify non-admin customer cannot schedule shows."""
    now = datetime.utcnow()
    payload = {
        "movie_id": 1,
        "screen_id": 1,
        "start_time": (now + timedelta(hours=5)).isoformat(),
        "end_time": (now + timedelta(hours=7)).isoformat(),
        "base_price": "250.00",
        "status": "scheduled",
    }
    res = client.post("/api/shows", json=payload, headers={"X-User-Id": "2"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_create_show_invalid_times(client: TestClient):
    """Verify end_time <= start_time returns 422 Validation Error."""
    now = datetime.utcnow()
    payload = {
        "movie_id": 1,
        "screen_id": 1,
        "start_time": (now + timedelta(hours=5)).isoformat(),
        "end_time": (now + timedelta(hours=4)).isoformat(),  # End before start
        "base_price": "250.00",
        "status": "scheduled",
    }
    res = client.post("/api/shows", json=payload, headers={"X-User-Id": "1"})
    assert res.status_code == 422
    err = res.json()
    assert err["error"]["code"] == "VALIDATION_ERROR"


def test_theatres_include_screens(client: TestClient):
    """Verify that listing theatres returns detailed screen arrays for each theatre."""
    res = client.get("/api/theatres")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
    first_theatre = data["items"][0]
    assert "screens" in first_theatre
    assert isinstance(first_theatre["screens"], list)
    assert len(first_theatre["screens"]) >= 1
    screen = first_theatre["screens"][0]
    assert "name" in screen
    assert "total_rows" in screen
    assert "seats_per_row" in screen


def test_system_health_endpoint(client: TestClient):
    """Verify the /health check endpoint returns healthy status and DB connected."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

