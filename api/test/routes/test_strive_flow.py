from __future__ import annotations

from urllib.parse import urlparse, parse_qs

import pytest


def _extract_token_from_redirect(resp) -> str | None:
    # TestClient may follow redirects; inspect final URL or history
    full = str(resp.url)
    if "token=" in full:
        return parse_qs(urlparse(full).query).get("token", [None])[0]
    for h in getattr(resp, "history", []):
        if "token=" in str(h.url):
            return parse_qs(urlparse(str(h.url)).query).get("token", [None])[0]
    return None


@pytest.mark.integration
def test_strive_end_to_end_flow(client) -> None:
    # Reset DB and get a dev user
    r = client.post("/api/dev/reset-db")
    assert r.status_code == 200

    r = client.get("/api/dev/users")
    assert r.status_code == 200
    users = r.json()
    assert users, "expected seeded users"
    pid = users[0]["pid"]

    # Dev login to get a JWT (redirect to /jwt?token=...)
    r = client.get(f"/api/auth/as/{pid}")
    token = _extract_token_from_redirect(r)
    assert token is not None
    headers = {"Authorization": f"Bearer {token}"}

    # Pick a course and an activity
    r = client.get("/api/courses", headers=headers)
    assert r.status_code == 200
    courses = r.json()
    assert courses, "no courses seeded"
    course = courses[0]

    r = client.get(f"/api/courses/{course['id']}/activities", headers=headers)
    assert r.status_code == 200
    activities = r.json()
    assert activities, "no activities for course"
    activity = activities[0]

    # Start a quiz
    body = {"mode": "daily", "module_name": "Module 2: Python Basics", "topic": "Loops", "question_count": 3}
    r = client.post(f"/api/activities/{activity['id']}/quizzes", json=body, headers=headers)
    assert r.status_code == 201
    quiz = r.json()
    assert quiz["status"] == "in_progress"
    quiz_id = quiz["id"]

    # Get questions
    r = client.get(f"/api/quizzes/{quiz_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "questions" in data and isinstance(data["questions"], list)

    # Submit answers (choose first option for each question)
    answers = [{"question_id": q["question_id"], "selected_choice_id": q["choices"][0]["id"]} for q in data["questions"]]
    r = client.post(f"/api/quizzes/{quiz_id}/submit", json={"answers": answers}, headers=headers)
    assert r.status_code == 200
    result = r.json()
    assert result["total_count"] == len(answers)
    assert result["correct_count"] == result["total_count"]
