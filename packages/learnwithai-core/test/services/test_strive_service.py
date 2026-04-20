from __future__ import annotations

from typing import Any, cast

from learnwithai.services.strive_service import StriveService
from learnwithai.tables.activity import Activity
from learnwithai.tables.user import User


def test_start_get_submit_flow() -> None:
    svc = StriveService()

    # lightweight dummy objects with required attrs; cast to expected types for static checks
    subject = cast(User, type("U", (), {"pid": 123})())
    activity = cast(Activity, type("A", (), {"id": 99})())

    options = type("O", (), {"question_count": 3, "mode": "daily", "module_name": None, "topic": None})()

    handle = svc.start_quiz(subject=subject, activity=activity, options=options)
    assert handle.question_count == 3

    quiz = svc.get_quiz(subject=subject, submission_id=handle.id)
    assert quiz["id"] == handle.id
    assert len(quiz["questions"]) == 3

    # submit answers as dicts
    answers = [
        {"question_id": 1, "selected_choice_id": 1},
        {"question_id": 2, "selected_choice_id": 1},
        {"question_id": 3, "selected_choice_id": 2},
    ]
    result = svc.submit_quiz(subject=subject, submission_id=handle.id, answers=answers)
    assert result["total_count"] == 3
    assert "score" in result


def test_submit_accepts_model_like_objects() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 222})())
    activity = cast(Activity, type("A", (), {"id": 11})())
    handle = svc.start_quiz(subject=subject, activity=activity, options=None)

    # create model-like answer objects with attributes
    class Ans:
        def __init__(self, q, s):
            self.question_id = q
            self.selected_choice_id = s

    answers = cast(list[dict[str, Any]], [Ans(1, 1), Ans(2, 1), Ans(3, 1)])
    result = svc.submit_quiz(subject=subject, submission_id=handle.id, answers=answers)
    assert result["total_count"] == handle.question_count


def test_get_and_submit_raise_for_missing_quiz() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 999})())

    try:
        svc.get_quiz(subject=subject, submission_id=9999999)
        raise AssertionError("expected KeyError")
    except KeyError:
        pass

    try:
        svc.submit_quiz(subject=subject, submission_id=9999999, answers=[])
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
