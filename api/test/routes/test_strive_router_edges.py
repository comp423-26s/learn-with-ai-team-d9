from typing import Any

from fastapi import HTTPException

from api.models.strive import QuizCreateRequest, QuizSubmitRequest
from api.routes.strive_router import get_quiz, start_quiz, submit_quiz


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
    subject = DummyUser(123)
    try:
        get_quiz(quiz_submission_id=999, subject=subject, strive_svc=FailingService())  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 404


def test_get_and_submit_unwired_raise_501() -> None:
    subject = DummyUser(123)
    try:
        get_quiz(quiz_submission_id=1, subject=subject, strive_svc=None)  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 501

    body = QuizSubmitRequest.model_validate({"answers": []})
    try:
        submit_quiz(quiz_submission_id=1, body=body, subject=subject, strive_svc=None)  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 501

    body = QuizSubmitRequest.model_validate({"answers": []})
    try:
        submit_quiz(quiz_submission_id=999, body=body, subject=subject, strive_svc=FailingService())  # type: ignore[arg-type]
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 404
