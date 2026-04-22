from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Any, cast
from unittest.mock import MagicMock, patch

import learnwithai.services.strive_service as strive_service_module
import pytest
from learnwithai.services.strive_service import StriveService
from learnwithai.tables.activity import Activity
from learnwithai.tables.user import User


@pytest.fixture(autouse=True)
def clear_quiz_store() -> None:
    strive_service_module._QUIZ_STORE.clear()
    strive_service_module._NEXT_ID = count(1)


def _mock_questions(qcount: int) -> list[dict[str, Any]]:
    return [
        {
            "question_id": i,
            "text": f"Q{i}",
            "choices": [
                {"id": 1, "text": "A"},
                {"id": 2, "text": "B"},
                {"id": 3, "text": "C"},
                {"id": 4, "text": "D"},
            ],
            "correct_choice_id": 1,
            "explanation": "Because.",
        }
        for i in range(1, qcount + 1)
    ]


def test_start_get_submit_flow() -> None:
    svc = StriveService()

    # lightweight dummy objects with required attrs; cast to expected types for static checks
    subject = cast(User, type("U", (), {"pid": 123})())
    activity = cast(Activity, type("A", (), {"id": 99})())

    options = type("O", (), {"question_count": 3, "mode": "daily", "module_name": None, "topic": None})()

    with patch.object(svc, "_generate_questions_with_llm", return_value=_mock_questions(3)):
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
    with patch.object(svc, "_generate_questions_with_llm", return_value=_mock_questions(5)):
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


def test_start_quiz_reuses_existing_matching_submission() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 456})())
    activity = cast(Activity, type("A", (), {"id": 77})())

    options = type("O", (), {"question_count": 5, "mode": "daily", "module_name": None, "topic": None})()

    with patch.object(svc, "_generate_questions_with_llm", return_value=_mock_questions(5)):
        first = svc.start_quiz(subject=subject, activity=activity, options=options)
        second = svc.start_quiz(subject=subject, activity=activity, options=options)

    assert second.id == first.id
    assert second.question_count == first.question_count

    try:
        svc.submit_quiz(subject=subject, submission_id=9999999, answers=[])
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_generate_questions_handles_invalid_json_then_fails() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "not json"

    with patch.object(svc.client.chat.completions, "create", side_effect=[mock_completion, mock_completion]):
        try:
            svc._generate_questions_with_llm(2)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "invalid JSON" in str(exc)


def test_generate_questions_rejects_too_few_questions() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[
        0
    ].message.content = (
        '[{"question": "Q", "choices": ["a", "b", "c", "d"], "correct_choice_index": 0, "explanation": "x"}]'
    )

    with patch.object(svc.client.chat.completions, "create", side_effect=[mock_completion, mock_completion]):
        try:
            svc._generate_questions_with_llm(2)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "invalid JSON content" in str(exc)
            assert exc.__cause__ is not None
            assert "too few questions" in str(exc.__cause__)


def test_generate_questions_rejects_invalid_question_payload() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "[1]"

    with patch.object(svc.client.chat.completions, "create", return_value=mock_completion):
        try:
            svc._generate_questions_with_llm(1)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "invalid question payload" in str(exc)


def test_generate_questions_rejects_invalid_choices() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[
        0
    ].message.content = '[{"question": "Q", "choices": ["a", "b"], "correct_choice_index": 0, "explanation": "x"}]'

    with patch.object(svc.client.chat.completions, "create", return_value=mock_completion):
        try:
            svc._generate_questions_with_llm(1)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "invalid choices" in str(exc)


def test_generate_questions_rejects_invalid_correct_choice_index() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[
        0
    ].message.content = (
        '[{"question": "Q", "choices": ["a", "b", "c", "d"], "correct_choice_index": 4, "explanation": "x"}]'
    )

    with patch.object(svc.client.chat.completions, "create", return_value=mock_completion):
        try:
            svc._generate_questions_with_llm(1)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "invalid correct choice index" in str(exc)


def test_reusable_submission_filters_mismatched_metadata() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 456})())
    activity = cast(Activity, type("A", (), {"id": 77})())
    started_at = datetime.now(timezone.utc)

    strive_service_module._QUIZ_STORE[1] = {
        "submission": {
            "id": 1,
            "activity_id": 88,
            "student_pid": subject.pid,
            "status": "in_progress",
            "started_at": started_at,
            "question_count": 5,
            "mode": "daily",
            "module_name": None,
            "topic": None,
        },
        "questions": [],
    }
    strive_service_module._QUIZ_STORE[8] = {
        "submission": {
            "id": 8,
            "activity_id": activity.id,
            "student_pid": 999999,
            "status": "in_progress",
            "started_at": started_at,
            "question_count": 5,
            "mode": "daily",
            "module_name": None,
            "topic": None,
        },
        "questions": [],
    }
    strive_service_module._QUIZ_STORE[2] = {
        "submission": {
            "id": 2,
            "activity_id": activity.id,
            "student_pid": subject.pid,
            "status": "in_progress",
            "started_at": started_at,
            "question_count": 4,
            "mode": "daily",
            "module_name": None,
            "topic": None,
        },
        "questions": [],
    }
    strive_service_module._QUIZ_STORE[3] = {
        "submission": {
            "id": 3,
            "activity_id": activity.id,
            "student_pid": subject.pid,
            "status": "in_progress",
            "started_at": started_at,
            "question_count": 5,
            "mode": "module",
            "module_name": None,
            "topic": None,
        },
        "questions": [],
    }
    strive_service_module._QUIZ_STORE[4] = {
        "submission": {
            "id": 4,
            "activity_id": activity.id,
            "student_pid": subject.pid,
            "status": "in_progress",
            "started_at": started_at,
            "question_count": 5,
            "mode": "daily",
            "module_name": "Module 1",
            "topic": None,
        },
        "questions": [],
    }
    strive_service_module._QUIZ_STORE[5] = {
        "submission": {
            "id": 5,
            "activity_id": activity.id,
            "student_pid": subject.pid,
            "status": "in_progress",
            "started_at": started_at,
            "question_count": 5,
            "mode": "daily",
            "module_name": None,
            "topic": "Loops",
        },
        "questions": [],
    }
    strive_service_module._QUIZ_STORE[6] = {
        "submission": {
            "id": 6,
            "activity_id": activity.id,
            "student_pid": subject.pid,
            "status": "archived",
            "started_at": started_at,
            "question_count": 5,
            "mode": "daily",
            "module_name": None,
            "topic": None,
        },
        "questions": [],
    }
    strive_service_module._QUIZ_STORE[7] = {
        "submission": {
            "id": 7,
            "activity_id": activity.id,
            "student_pid": subject.pid,
            "status": "submitted",
            "started_at": started_at,
            "question_count": 5,
            "mode": "daily",
            "module_name": None,
            "topic": None,
        },
        "questions": [],
    }

    reusable = svc._find_reusable_submission(
        subject,
        activity,
        qcount=5,
        mode="daily",
        module_name=None,
        topic=None,
    )

    assert reusable is not None
    assert reusable["submission"]["id"] == 7


def test_get_and_submit_reject_other_student() -> None:
    svc = StriveService()
    owner = cast(User, type("U", (), {"pid": 456})())
    other = cast(User, type("U", (), {"pid": 999})())
    activity = cast(Activity, type("A", (), {"id": 77})())

    with patch.object(
        svc,
        "_generate_questions_with_llm",
        return_value=[{"question_id": 1, "text": "Q", "choices": [], "correct_choice_id": 1, "explanation": "x"}],
    ):
        handle = svc.start_quiz(subject=owner, activity=activity, options=None)

    try:
        svc.get_quiz(subject=other, submission_id=handle.id)
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass

    try:
        svc.submit_quiz(subject=other, submission_id=handle.id, answers=[])
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass
