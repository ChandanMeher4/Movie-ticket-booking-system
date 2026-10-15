"""Tests for Movie CRUD, pagination, filtering, sorting, and error formats."""

from datetime import datetime
from fastapi.testclient import TestClient


def test_list_movies_pagination(client: TestClient):
    """Verify movie listing returns paginated results with total count."""
    response = client.get("/api/movies?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) == 5
    assert data["total"] >= 8


def test_filter_movies_by_genre(client: TestClient):
    """Verify filtering movies by genre returns only matching movies."""
    response = client.get("/api/movies?genre=Sci-Fi")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["genre"].lower() == "sci-fi"


def test_filter_movies_by_language(client: TestClient):
    """Verify filtering movies by language returns only matching titles."""
    response = client.get("/api/movies?language=Telugu")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(m["title"] == "RRR" for m in data["items"])


def test_search_movies_by_title(client: TestClient):
    """Verify keyword search returns relevant titles."""
    response = client.get("/api/movies?search=Inception")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["items"][0]["title"] == "Inception"


def test_get_movie_by_id(client: TestClient):
    """Verify retrieving a single movie by ID."""
    response = client.get("/api/movies/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "title" in data
    assert "duration_min" in data


def test_get_movie_not_found(client: TestClient):
    """Verify retrieving non-existent movie returns 404 with standard error format."""
    response = client.get("/api/movies/99999")
    assert response.status_code == 404
    err = response.json()
    assert "error" in err
    assert err["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "not found" in err["error"]["message"].lower()


def test_create_movie_success(client: TestClient):
    """Verify creating a new movie succeeds with 201 Created."""
    payload = {
        "title": "Gladiator II",
        "description": "Years after witnessing the death of Maximus, Lucius must enter the Colosseum.",
        "genre": "Action",
        "language": "English",
        "duration_min": 148,
        "rating": "A",
        "release_date": "2024-11-22T00:00:00",
        "poster_url": "https://example.com/gladiator2.jpg",
        "is_active": True,
    }
    response = client.post("/api/movies", json=payload, headers={"X-User-Id": "1"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Gladiator II"
    assert data["id"] > 8


def test_create_movie_forbidden_for_non_admin(client: TestClient):
    """Verify non-admin customer is forbidden from adding movie listings."""
    payload = {
        "title": "Hacker Movie",
        "description": "Unauthorized listing attempt",
        "genre": "Thriller",
        "language": "English",
        "duration_min": 100,
        "rating": "UA",
        "release_date": "2024-11-22T00:00:00",
    }
    # Customer user ID 2 attempting admin action
    response = client.post("/api/movies", json=payload, headers={"X-User-Id": "2"})
    assert response.status_code == 403
    err = response.json()
    assert err["error"]["code"] == "FORBIDDEN"
    assert "administrator" in err["error"]["message"].lower()

    # Missing user credentials
    missing_auth = client.post("/api/movies", json=payload)
    assert missing_auth.status_code == 403


def test_create_movie_invalid_payload(client: TestClient):
    """Verify invalid payload returns 422 with standardized validation details."""
    payload = {
        "title": "",  # min_length is 1
        "description": "Short",
        "genre": "Action",
        "language": "English",
        "duration_min": -10,  # gt 0
        "rating": "INVALID_RATING",
        "release_date": "2024-11-22T00:00:00",
    }
    response = client.post("/api/movies", json=payload, headers={"X-User-Id": "1"})
    assert response.status_code == 422
    err = response.json()
    assert "error" in err
    assert err["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(err["error"]["details"], list)
    assert len(err["error"]["details"]) > 0


def test_update_movie(client: TestClient):
    """Verify partial update of movie attributes."""
    response = client.put("/api/movies/1", json={"description": "Updated Inception synopsis description."}, headers={"X-User-Id": "1"})
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated Inception synopsis description."


def test_delete_movie(client: TestClient):
    """Verify soft-delete deactivates movie."""
    response = client.delete("/api/movies/1", headers={"X-User-Id": "1"})
    assert response.status_code == 200
    assert response.json()["id"] == 1

    # Verify movie is now is_active == False
    get_res = client.get("/api/movies/1")
    assert get_res.status_code == 200
    assert get_res.json()["is_active"] is False
