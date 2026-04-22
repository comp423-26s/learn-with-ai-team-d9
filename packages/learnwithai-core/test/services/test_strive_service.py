from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from learnwithai.services import strive_service as strive_service_module
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


def test_select_language_prefers_java_and_c_when_explicit() -> None:
    svc = StriveService()

    assert svc._select_language(module_name="Intro to Java", topic=None) == "Java"
    assert svc._select_language(module_name="Pointers in C", topic=None) == "C"


@pytest.mark.parametrize(
    ("content", "expected_first_text"),
    [
        ("[]", "Sample question 1"),
        ("[1]", "Sample question 1"),
        (
            '[{"question": "Q1", "choices": "not-a-list", "correct_choice_index": 0}]',
            "Sample question 1",
        ),
        (
            '[{"question": "Q1", "choices": ["a", "b", "c", "d"], "correct_choice_index": 9}]',
            "Sample question 1",
        ),
    ],
)
def test_generate_questions_with_llm_falls_back_on_invalid_payloads(content: str, expected_first_text: str) -> None:
    svc = StriveService()
    svc.settings = cast(
        Any,
        type(
            "Settings",
            (),
            {"openai_api_key": "sk-test-key", "openai_model": "gpt-5-mini", "is_test": False},
        )(),
    )

    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_completion
    svc.client = mock_client

    questions = svc._generate_questions_with_llm(qcount=1, topics=("functions",), module_name=None, topic=None)

    assert questions[0]["text"].startswith(expected_first_text)
    assert questions[0]["choices"][0]["id"] == 1


def test_find_reusable_submission_skips_nonmatching_entries() -> None:
    original_store = dict(strive_service_module._QUIZ_STORE)
    strive_service_module._QUIZ_STORE.clear()

    try:
        svc = StriveService()
        subject = cast(User, type("U", (), {"pid": 321})())
        activity = cast(Activity, type("A", (), {"id": 654})())

        strive_service_module._QUIZ_STORE[1] = {
            "submission": {
                "id": 1,
                "activity_id": 999,
                "student_pid": 321,
                "status": "in_progress",
                "started_at": 1,
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
                "activity_id": 654,
                "student_pid": 321,
                "status": "in_progress",
                "started_at": 2,
                "question_count": 5,
                "mode": "daily",
                "module_name": None,
                "topic": "other-topic",
            },
            "questions": [],
        }
        strive_service_module._QUIZ_STORE[3] = {
            "submission": {
                "id": 3,
                "activity_id": 654,
                "student_pid": 321,
                "status": "draft",
                "started_at": 3,
                "question_count": 5,
                "mode": "daily",
                "module_name": None,
                "topic": None,
            },
            "questions": [],
        }
        strive_service_module._QUIZ_STORE[4] = {
            "submission": {
                "id": 4,
                "activity_id": 654,
                "student_pid": 321,
                "status": "submitted",
                "started_at": 4,
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
        assert reusable["submission"]["id"] == 4
    finally:
        strive_service_module._QUIZ_STORE.clear()
        strive_service_module._QUIZ_STORE.update(original_store)


def test_start_quiz_reuses_existing_matching_submission() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 456})())
    activity = cast(Activity, type("A", (), {"id": 77})())

    options = type("O", (), {"question_count": 5, "mode": "daily", "module_name": None, "topic": None})()

    first = svc.start_quiz(subject=subject, activity=activity, options=options)
    second = svc.start_quiz(subject=subject, activity=activity, options=options)

    assert second.id == first.id
    assert second.question_count == first.question_count

    try:
        svc.submit_quiz(subject=subject, submission_id=9999999, answers=[])
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
