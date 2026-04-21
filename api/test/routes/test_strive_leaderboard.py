from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest


def _extract_token_from_redirect(resp) -> str | None:
    full = str(resp.url)
    if "token=" in full:
        return parse_qs(urlparse(full).query).get("token", [None])[0]
    for h in getattr(resp, "history", []):
        if "token=" in str(h.url):
            return parse_qs(urlparse(str(h.url)).query).get("token", [None])[0]
    return None


@pytest.mark.integration
def test_leaderboard_uses_seeded_scores(client) -> None:
    r = client.post("/api/dev/reset-db")
    assert r.status_code == 200

    r = client.get("/api/dev/users")
    assert r.status_code == 200
    users = r.json()
    assert users, "expected seeded users"

    student = next((u for u in users if u.get("onyen") == "student"), users[0])
    pid = student["pid"]

    r = client.get(f"/api/auth/as/{pid}")
    token = _extract_token_from_redirect(r)
    assert token is not None
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/courses", headers=headers)
    assert r.status_code == 200
    courses = r.json()
    assert courses, "no courses seeded"
    course = courses[0]

    r = client.get(f"/api/daily-practice/leaderboard?course_id={course['id']}", headers=headers)
    assert r.status_code == 200
    data = r.json()

    entries = data["entries"]
    assert entries, "expected leaderboard entries"

    student_entry = next((e for e in entries if e["user_pid"] == pid), None)
    assert student_entry is not None
    assert student_entry["score"] == 170.0
    assert student_entry["accuracy"] == pytest.approx(0.85, abs=1e-6)
