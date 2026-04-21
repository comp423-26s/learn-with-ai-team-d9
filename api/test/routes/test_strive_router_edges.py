from datetime import datetime, timezone
from typing import Any, cast

import pytest
from fastapi import HTTPException
from learnwithai.config import Settings

from api.di import AuthenticatedUserDI
from api.models.strive import QuizCreateRequest, QuizSubmitRequest
from api.routes.strive_router import get_leaderboard, get_quiz, get_quiz_results, start_quiz, submit_quiz


def test_submit_quiz_success_publishes_job_update(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    strive_router_module = importlib.import_module("api.routes.strive_router")

    subject = cast(AuthenticatedUserDI, DummyUser(123))
    body = QuizSubmitRequest.model_validate({"answers": [{"question_id": 1, "selected_choice_id": 1}]})

    captured: dict[str, Any] = {}

    class DummyNotifier:
        def __init__(self, url: str) -> None:
            captured["url"] = url
            captured["closed"] = False

        def notify(self, update: Any) -> None:
            captured["update"] = update

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(strive_router_module, "RabbitMQJobNotifier", DummyNotifier)

    class WorkingService:
        def submit_quiz(self, *a: Any, **k: Any) -> dict[str, Any]:
            submission_id = int(k.get("submission_id") or a[1])
            return {
                "id": submission_id,
                "score": 100.0,
                "correct_count": 1,
                "total_count": 1,
                "feedback": [
                    {
                        "question_id": 1,
                        "correct": True,
                        "correct_choice_id": 1,
                        "explanation": "ok",
                    }
                ],
                "finished_at": datetime.now(timezone.utc),
            }

        def get_submission_course_id(self, *a: Any, **k: Any) -> int:
            return 42

        def get_leaderboard_rank_snapshot(self, *a: Any, **k: Any) -> dict[str, Any]:
            return {"rank": 1, "score": 100.0, "accuracy": 1.0, "attempt_count": 1}

    response = submit_quiz(
        quiz_submission_id=1,
        body=body,
        subject=subject,
        strive_svc=WorkingService(),  # type: ignore[arg-type]
        settings=Settings(),
    )

    assert response.id == 1
    update = captured["update"]
    assert update.job_id == 1
    assert update.course_id == 42
    assert update.user_id == 123
    assert update.kind == "daily_practice_leaderboard"
    assert update.status == "updated"
    assert update.metadata is not None
    assert captured["closed"] is True


class DummyActivity:
    def __init__(self, id: int) -> None:
        self.id = id


class DummyUser:
    def __init__(self, pid: int) -> None:
        self.pid = pid


class FailingService:
    def start_quiz(self, *a: Any, **k: Any) -> None:
        raise KeyError("no activity")

    def get_quiz(self, *a: Any, **k: Any) -> None:
        raise KeyError("no quiz")

    def submit_quiz(self, *a: Any, **k: Any) -> None:
        raise KeyError("no quiz")

    def get_results(self, *a: Any, **k: Any) -> None:
        raise KeyError("no results")

    def get_leaderboard(self, *a: Any, **k: Any) -> None:
        raise KeyError("no leaderboard")


def test_start_quiz_unwired_raises_501() -> None:
    activity = DummyActivity(1)
    body = QuizCreateRequest.model_validate({"question_count": 1, "mode": "daily"})
    subject = DummyUser(123)
    try:
        start_quiz(activity=activity, body=body, subject=subject, strive_svc=None)  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 501


def test_start_quiz_keyerror_converted_to_404() -> None:
    activity = DummyActivity(1)
    body = QuizCreateRequest.model_validate({"question_count": 1, "mode": "daily"})
    subject = DummyUser(123)
    try:
        start_quiz(activity=activity, body=body, subject=subject, strive_svc=FailingService())  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 404


def test_get_and_submit_keyerror_converted_to_404() -> None:
    subject = cast(AuthenticatedUserDI, DummyUser(123))
    try:
        get_quiz(quiz_submission_id=999, subject=subject, strive_svc=FailingService())  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 404


def test_get_and_submit_unwired_raise_501() -> None:
    subject = cast(AuthenticatedUserDI, DummyUser(123))
    try:
        get_quiz(quiz_submission_id=1, subject=subject, strive_svc=None)  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 501

    body = QuizSubmitRequest.model_validate({"answers": []})
    try:
        submit_quiz(
            quiz_submission_id=1,
            body=body,
            subject=subject,
            strive_svc=None,  # type: ignore[arg-type]
            settings=Settings(),
        )
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 501

    body = QuizSubmitRequest.model_validate({"answers": []})
    try:
        submit_quiz(
            quiz_submission_id=999,
            body=body,
            subject=subject,
            strive_svc=FailingService(),  # type: ignore[arg-type]
            settings=Settings(),
        )
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 404


def test_get_quiz_results_unwired_raises_501() -> None:
    subject = cast(AuthenticatedUserDI, DummyUser(123))
    with pytest.raises(HTTPException) as excinfo:
        get_quiz_results(subject=subject, quiz_submission_id=1, strive_svc=None)  # type: ignore[arg-type]
    assert excinfo.value.status_code == 501


def test_get_quiz_results_keyerror_converted_to_404() -> None:
    subject = cast(AuthenticatedUserDI, DummyUser(123))
    with pytest.raises(HTTPException) as excinfo:
        get_quiz_results(subject=subject, quiz_submission_id=999, strive_svc=FailingService())  # type: ignore[arg-type]
    assert excinfo.value.status_code == 404


def test_get_quiz_results_success_returns_model() -> None:
    subject = cast(AuthenticatedUserDI, DummyUser(123))

    class ResultsService:
        def get_results(self, *a: Any, **k: Any) -> dict[str, Any]:
            submission_id = int(k.get("submission_id") or a[1])
            return {
                "id": submission_id,
                "score": 100.0,
                "correct_count": 1,
                "total_count": 1,
                "finished_at": datetime.now(timezone.utc),
                "feedback_summary": "ok",
            }

    result = get_quiz_results(subject=subject, quiz_submission_id=1, strive_svc=ResultsService())  # type: ignore[arg-type]
    assert result.id == 1
    assert result.score == 100.0


def test_get_leaderboard_unwired_raises_501() -> None:
    subject = cast(AuthenticatedUserDI, DummyUser(123))
    with pytest.raises(HTTPException) as excinfo:
        get_leaderboard(subject=subject, course_id=1, strive_svc=None, limit=10)  # type: ignore[arg-type]
    assert excinfo.value.status_code == 501
