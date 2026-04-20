from api.routes.test_router import team_test


def test_team_test_returns_payload() -> None:
    resp = team_test()
    assert resp.team == "your-team"
    assert "Hello from the team router" in resp.message
