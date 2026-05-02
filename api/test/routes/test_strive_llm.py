"""Integration tests for LLM-powered quiz generation in Strive."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


def _extract_token_from_redirect(resp) -> str | None:
    """Extract JWT token from redirect response."""
    full = str(resp.url)
    if "token=" in full:
        return parse_qs(urlparse(full).query).get("token", [None])[0]
    for h in getattr(resp, "history", []):
        if "token=" in str(h.url):
            return parse_qs(urlparse(str(h.url)).query).get("token", [None])[0]
    return None


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    """Get a TestClient with valid JWT token."""
    # Reset DB
    r = client.post("/api/dev/reset-db")
    assert r.status_code == 200

    # Get user
    r = client.get("/api/dev/users")
    assert r.status_code == 200
    users = r.json()
    assert users, "expected seeded users"
    pid = users[0]["pid"]

    # Login to get token
    r = client.get(f"/api/auth/as/{pid}")
    token = _extract_token_from_redirect(r)
    assert token is not None, "Failed to extract token from auth response"

    # Set header for all subsequent requests
    client.headers = {"Authorization": f"Bearer {token}"}
    return client


@pytest.mark.integration
def test_create_quiz_with_python_topics(authenticated_client: TestClient) -> None:
    """Test successful quiz generation queueing with Python-only topics."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    create_response = authenticated_client.post(
        f"/api/activities/{activity_id}/quizzes",
        json={"mode": "daily", "question_count": 3},
    )

    assert create_response.status_code == 201
    quiz_data = create_response.json()
    assert quiz_data["job"]["status"] == "pending"
    assert isinstance(quiz_data["job"]["id"], int)

    questions_response = authenticated_client.get(f"/api/quizzes/{quiz_data['job']['id']}")
    assert questions_response.status_code == 409
    assert "pending" in questions_response.json()["detail"]
