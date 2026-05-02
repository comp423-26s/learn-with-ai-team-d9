from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import count
from typing import Any, cast
from unittest.mock import MagicMock, patch

import learnwithai.services.strive_service as strive_service_module
import pytest
from learnwithai.services.strive_service import StriveService
from learnwithai.tables.activity import Activity
from learnwithai.tables.async_job import AsyncJob, AsyncJobStatus
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


def test_generate_questions_uses_source_aware_prompt() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[
        0
    ].message.content = (
        '[{"question": "Q", "choices": ["a", "b", "c", "d"], "correct_choice_index": 0, "explanation": "x"}]'
    )

    with patch.object(svc.client.chat.completions, "create", return_value=mock_completion) as mock_create:
        result = svc._generate_questions_with_llm(1, source_excerpt="Functions return values.")

    assert len(result) == 1
    prompt = mock_create.call_args.kwargs["messages"][1]["content"]
    assert "database-backed" in prompt
    assert "SOURCE DOCUMENTS retrieved from the database-backed" in prompt
    assert "Functions return values." in prompt


def test_generate_questions_without_sources_uses_backup_prompt() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[
        0
    ].message.content = (
        '[{"question": "Q", "choices": ["a", "b", "c", "d"], "correct_choice_index": 0, "explanation": "x"}]'
    )

    with patch.object(svc.client.chat.completions, "create", return_value=mock_completion) as mock_create:
        result = svc._generate_questions_with_llm(1, source_excerpt="")

    assert len(result) == 1
    prompt = mock_create.call_args.kwargs["messages"][1]["content"]
    assert "beginner-level Python multiple-choice questions" in prompt
    assert "DATABASE SOURCE DOCUMENTS" not in prompt


def test_extract_study_material_from_pdf_returns_json_payload() -> None:
    svc = StriveService()
    reader = MagicMock()
    reader.metadata = {"/Title": "  Functions  ", "/Empty": None}
    reader.pages = [
        MagicMock(extract_text=MagicMock(return_value="Functions\nreturn values.")),
        MagicMock(extract_text=MagicMock(return_value="   ")),
        MagicMock(extract_text=MagicMock(return_value="Loops repeat work.")),
    ]

    with patch("learnwithai.services.strive_service.PdfReader", return_value=reader):
        extracted = svc.extract_study_material_from_pdf(b"%PDF-1.4 test")

    assert extracted == {
        "schema_version": 1,
        "source_type": "pdf",
        "page_count": 3,
        "metadata": {"Title": "Functions", "Empty": ""},
        "pages": [
            {"page": 1, "text": "Functions return values."},
            {"page": 2, "text": ""},
            {"page": 3, "text": "Loops repeat work."},
        ],
        "text": "Functions return values. Loops repeat work.",
    }


def test_extract_study_material_from_pdf_truncates_combined_text() -> None:
    svc = StriveService()
    reader = MagicMock()
    reader.metadata = None
    reader.pages = [
        MagicMock(extract_text=MagicMock(return_value="abc")),
        MagicMock(extract_text=MagicMock(return_value="def")),
    ]

    with patch("learnwithai.services.strive_service.PdfReader", return_value=reader):
        extracted = svc.extract_study_material_from_pdf(b"%PDF-1.4 test", max_chars=3)

    assert extracted["metadata"] == {}
    assert extracted["pages"] == [{"page": 1, "text": "abc"}, {"page": 2, "text": ""}]
    assert extracted["text"] == "abc"


def test_extract_study_material_from_pdf_raises_when_no_text() -> None:
    svc = StriveService()
    reader = MagicMock()
    reader.metadata = {}
    reader.pages = [
        MagicMock(extract_text=MagicMock(return_value=None)),
        MagicMock(extract_text=MagicMock(return_value="   ")),
    ]

    with patch("learnwithai.services.strive_service.PdfReader", return_value=reader):
        with pytest.raises(ValueError, match="Could not extract readable text from PDF"):
            svc.extract_study_material_from_pdf(b"%PDF-1.4 test")


def test_extract_study_material_from_pdf_raises_when_pdf_cannot_be_read() -> None:
    svc = StriveService()

    with patch("learnwithai.services.strive_service.PdfReader", side_effect=RuntimeError("bad pdf")):
        with pytest.raises(ValueError, match="Could not read PDF"):
            svc.extract_study_material_from_pdf(b"not a pdf")


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


def test_generate_quiz_from_pdf_success(tmp_path: Any) -> None:
    svc = StriveService()
    source_repo = MagicMock()
    persisted_source: Any = type(
        "Source",
        (),
        {
            "id": 321,
            "filename": "lesson-notes.pdf",
            "content_type": "application/pdf",
            "created_at": datetime(2026, 4, 20, tzinfo=timezone.utc),
            "pdf_bytes": b"%PDF-1.4 test",
        },
    )()
    source_repo.create_source.return_value = persisted_source
    source_repo.list_by_student_and_activity.return_value = [persisted_source]
    svc.source_repo = source_repo
    subject = cast(User, type("U", (), {"pid": 77})())
    activity = cast(Activity, type("A", (), {"id": 55})())
    pdf_bytes = b"%PDF-1.4 test"

    questions = _mock_questions(3)
    study_material = {"schema_version": 1, "source_type": "pdf", "text": "A source excerpt."}

    with (
        patch.object(svc, "extract_study_material_from_pdf", return_value=study_material) as extract_mock,
        patch.object(svc, "_generate_questions_with_llm", return_value=questions) as gen_mock,
    ):
        result = svc.generate_quiz_from_pdf(subject=subject, activity=activity, pdf_bytes=pdf_bytes, question_count=3)

    extract_mock.assert_called_once_with(persisted_source.pdf_bytes)
    gen_mock.assert_called_once()
    assert gen_mock.call_args.kwargs["qcount"] == 3
    source_excerpt = json.loads(gen_mock.call_args.kwargs["source_excerpt"])
    assert source_excerpt["retrieved_from"] == "database-backed_strive_source_store"
    assert len(source_excerpt["sources"]) == 1
    assert source_excerpt["sources"][0]["source_id"] == 321
    assert source_excerpt["sources"][0]["filename"] == "lesson-notes.pdf"
    assert source_excerpt["sources"][0]["study_material"] == study_material

    assert result["student_pid"] == 77
    assert result["activity_id"] == 55
    assert result["status"] == "in_progress"
    assert result["question_count"] == 3
    assert result["mode"] == "module"
    assert result["source_id"] == 321
    assert len(result["questions"]) == 3
    # public questions must not include correct_choice_id
    for q in result["questions"]:
        assert "correct_choice_id" not in q
    assert result["id"] in strive_service_module._QUIZ_STORE
    source_repo.create_source.assert_called_once()
    created_source = source_repo.create_source.call_args.args[0]
    assert created_source.student_pid == 77
    assert created_source.activity_id == 55
    assert created_source.pdf_bytes == pdf_bytes


def test_generate_quiz_from_pdf_llm_fallback(tmp_path: Any) -> None:
    svc = StriveService()
    source_repo = MagicMock()
    persisted_source = type(
        "Source",
        (),
        {
            "id": 654,
            "filename": "fallback.pdf",
            "content_type": "application/pdf",
            "created_at": datetime(2026, 4, 20, tzinfo=timezone.utc),
            "pdf_bytes": b"%PDF-1.4 test",
        },
    )()
    source_repo.create_source.return_value = persisted_source
    source_repo.list_by_student_and_activity.return_value = [persisted_source]
    svc.source_repo = source_repo
    subject = cast(User, type("U", (), {"pid": 88})())
    activity = cast(Activity, type("A", (), {"id": 66})())
    pdf_bytes = b"%PDF-1.4 test"

    with (
        patch.object(svc, "extract_study_material_from_pdf", return_value={"text": "A"}),
        patch.object(svc, "_generate_questions_with_llm", side_effect=RuntimeError("LLM down")),
    ):
        result = svc.generate_quiz_from_pdf(subject=subject, activity=activity, pdf_bytes=pdf_bytes, question_count=2)

    assert result["question_count"] == 2
    assert result["source_id"] == 654
    assert len(result["questions"]) == 2
    for q in result["questions"]:
        assert "PDF source" in q["text"]
        assert len(q["choices"]) == 4


def test_list_uploaded_sources_returns_saved_sources() -> None:
    svc = StriveService()
    source_repo = MagicMock()
    saved_source: Any = type(
        "Source",
        (),
        {
            "id": 901,
            "activity_id": 44,
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "created_at": datetime(2026, 4, 20, tzinfo=timezone.utc),
        },
    )()
    source_repo.list_by_student.return_value = [saved_source]
    svc.source_repo = source_repo
    subject = cast(User, type("U", (), {"pid": 123})())

    sources = svc.list_uploaded_sources(subject)

    assert sources == [
        {
            "source_id": 901,
            "activity_id": 44,
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "created_at": saved_source.created_at,
        }
    ]
    source_repo.list_by_student.assert_called_once_with(123)


def test_generate_quiz_from_source_uses_saved_source_row() -> None:
    svc = StriveService()
    source_repo = MagicMock()
    saved_source: Any = type(
        "Source",
        (),
        {
            "id": 777,
            "activity_id": 88,
            "student_pid": 456,
            "filename": "saved.pdf",
            "content_type": "application/pdf",
            "created_at": datetime(2026, 4, 20, tzinfo=timezone.utc),
            "pdf_bytes": b"%PDF-1.4 test",
        },
    )()
    source_repo.get_by_id.return_value = saved_source
    svc.source_repo = source_repo
    subject = cast(User, type("U", (), {"pid": 456})())

    with (
        patch.object(svc, "extract_study_material_from_pdf", return_value={"text": "A saved source"}) as extract_mock,
        patch.object(svc, "_generate_questions_with_llm", return_value=_mock_questions(2)) as gen_mock,
    ):
        result = svc.generate_quiz_from_source(subject=subject, source_id=777, question_count=2)

    extract_mock.assert_called_once_with(saved_source.pdf_bytes)
    gen_mock.assert_called_once()
    assert gen_mock.call_args.kwargs["qcount"] == 2
    assert "database-backed_strive_source_store" in gen_mock.call_args.kwargs["source_excerpt"]
    assert result["source_id"] == 777
    assert result["activity_id"] == 88
    assert result["student_pid"] == 456
    source_repo.get_by_id.assert_called_once_with(777)


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


def test_list_uploaded_sources_no_repo() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 1})())
    with pytest.raises(RuntimeError):
        svc.list_uploaded_sources(subject)


def test_store_uploaded_source_no_repo() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 1})())
    activity = cast(Activity, type("A", (), {"id": 1})())
    with pytest.raises(RuntimeError):
        svc._store_uploaded_source(
            subject, activity, b"pdf", source_filename="f.pdf", source_content_type="application/pdf"
        )


def test_build_source_context_no_repo() -> None:
    svc = StriveService()
    with pytest.raises(RuntimeError):
        svc._build_source_context_from_sources([])


def test_build_source_context_empty_sources() -> None:
    svc = StriveService()
    svc.source_repo = MagicMock()  # type: ignore[assignment]
    with pytest.raises(ValueError, match="No persisted source context"):
        svc._build_source_context_from_sources([])


def test_generate_quiz_from_source_no_repo() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 1})())
    with pytest.raises(RuntimeError):
        svc.generate_quiz_from_source(subject=subject, source_id=1)


def test_generate_quiz_from_source_not_found() -> None:
    svc = StriveService()
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = None
    svc.source_repo = source_repo  # type: ignore[assignment]
    subject = cast(User, type("U", (), {"pid": 1})())
    with pytest.raises(KeyError):
        svc.generate_quiz_from_source(subject=subject, source_id=99)


def test_generate_quiz_from_source_permission_denied() -> None:
    svc = StriveService()
    source_repo = MagicMock()
    saved_source: Any = type("Source", (), {"id": 1, "student_pid": 999, "activity_id": 1})()
    source_repo.get_by_id.return_value = saved_source
    svc.source_repo = source_repo  # type: ignore[assignment]
    subject = cast(User, type("U", (), {"pid": 1})())
    with pytest.raises(PermissionError):
        svc.generate_quiz_from_source(subject=subject, source_id=1)


def test_generate_quiz_from_source_llm_fallback() -> None:
    svc = StriveService()
    source_repo = MagicMock()
    saved_source: Any = type(
        "Source",
        (),
        {
            "id": 42,
            "student_pid": 7,
            "activity_id": 3,
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "created_at": datetime(2026, 4, 20, tzinfo=timezone.utc),
            "pdf_bytes": b"%PDF-1.4 test",
        },
    )()
    source_repo.get_by_id.return_value = saved_source
    svc.source_repo = source_repo  # type: ignore[assignment]
    subject = cast(User, type("U", (), {"pid": 7})())

    with (
        patch.object(svc, "extract_study_material_from_pdf", return_value={"text": "X"}),
        patch.object(svc, "_generate_questions_with_llm", side_effect=RuntimeError("LLM down")),
    ):
        result = svc.generate_quiz_from_source(subject=subject, source_id=42, question_count=2)

    assert result["question_count"] == 2
    assert len(result["questions"]) == 2
    for q in result["questions"]:
        assert "saved source" in q["text"]


def test_start_quiz_job_creates_async_job() -> None:
    async_job_repo = MagicMock()
    queued_job = AsyncJob(
        id=404,
        course_id=1,
        created_by_pid=77,
        kind="strive_quiz_generation",
        input_data={},
    )
    async_job_repo.create.side_effect = lambda job: queued_job.model_copy(
        update={
            "course_id": job.course_id,
            "created_by_pid": job.created_by_pid,
            "input_data": job.input_data,
        }
    )
    job_queue = MagicMock()
    svc = StriveService(async_job_repo=async_job_repo, job_queue=job_queue)
    subject = cast(User, type("U", (), {"pid": 77})())
    activity = cast(Activity, type("A", (), {"id": 12, "course_id": 3})())
    options = type("O", (), {"question_count": 4, "mode": "daily", "module_name": "M1", "topic": "Loops"})()

    job = svc.start_quiz_job(subject=subject, activity=activity, options=options)

    assert job.id == 404
    created_job = async_job_repo.create.call_args.args[0]
    assert created_job.course_id == 3
    assert created_job.created_by_pid == 77
    assert created_job.input_data == {
        "activity_id": 12,
        "student_pid": 77,
        "question_count": 4,
        "mode": "daily",
        "module_name": "M1",
        "topic": "Loops",
        "source_id": None,
    }
    job_queue.enqueue.assert_called_once()


def test_generate_quiz_from_pdf_job_stores_source_and_queues_job() -> None:
    source_repo = MagicMock()
    source_repo.create_source.return_value = type("Source", (), {"id": 9})()
    async_job_repo = MagicMock()
    async_job_repo.create.side_effect = lambda job: job.model_copy(update={"id": 505})
    job_queue = MagicMock()
    svc = StriveService(source_repo=source_repo, async_job_repo=async_job_repo, job_queue=job_queue)
    subject = cast(User, type("U", (), {"pid": 88})())
    activity = cast(Activity, type("A", (), {"id": 33, "course_id": 4})())

    job = svc.generate_quiz_from_pdf_job(
        subject=subject,
        activity=activity,
        pdf_bytes=b"%PDF-1.4",
        question_count=2,
        source_filename="notes.pdf",
    )

    assert job.id == 505
    created_source = source_repo.create_source.call_args.args[0]
    assert created_source.student_pid == 88
    assert created_source.activity_id == 33
    assert created_source.filename == "notes.pdf"
    assert async_job_repo.create.call_args.args[0].input_data["source_id"] == 9
    job_queue.enqueue.assert_called_once()


def test_generate_quiz_from_source_job_validation_and_success() -> None:
    subject = cast(User, type("U", (), {"pid": 10})())

    with pytest.raises(RuntimeError):
        StriveService().generate_quiz_from_source_job(subject=subject, source_id=1)

    source_repo = MagicMock()
    source_repo.get_by_id.return_value = None
    svc = StriveService(source_repo=source_repo, async_job_repo=MagicMock(), job_queue=MagicMock())
    with pytest.raises(KeyError):
        svc.generate_quiz_from_source_job(subject=subject, source_id=1)

    source_repo.get_by_id.return_value = type("Source", (), {"id": 1, "student_pid": 999, "activity_id": 6})()
    with pytest.raises(PermissionError):
        svc.generate_quiz_from_source_job(subject=subject, source_id=1)

    async_job_repo = MagicMock()
    async_job_repo.create.side_effect = lambda job: job.model_copy(update={"id": 606})
    job_queue = MagicMock()
    source_repo.get_by_id.return_value = type("Source", (), {"id": 1, "student_pid": 10, "activity_id": 6})()
    svc = StriveService(source_repo=source_repo, async_job_repo=async_job_repo, job_queue=job_queue)

    job = svc.generate_quiz_from_source_job(subject=subject, source_id=1, question_count=3)

    assert job.id == 606
    assert async_job_repo.create.call_args.args[0].input_data["source_id"] == 1
    job_queue.enqueue.assert_called_once()


def test_async_quiz_access_and_submission_paths() -> None:
    questions = _mock_questions(2)
    quiz_payload = {
        "id": 707,
        "activity_id": 5,
        "student_pid": 12,
        "status": "in_progress",
        "started_at": datetime.now(timezone.utc),
        "question_count": 2,
        "mode": "daily",
        "module_name": None,
        "topic": None,
        "questions": questions,
    }
    async_job = AsyncJob(
        id=707,
        course_id=1,
        created_by_pid=12,
        kind="strive_quiz_generation",
        status=AsyncJobStatus.COMPLETED,
        input_data={},
        output_data={"quiz": quiz_payload},
    )
    async_job_repo = MagicMock()
    async_job_repo.get_by_id.return_value = async_job
    svc = StriveService(async_job_repo=async_job_repo, job_queue=MagicMock())
    subject = cast(User, type("U", (), {"pid": 12})())

    public_quiz = svc.get_async_quiz(subject=subject, job_id=707)

    assert public_quiz["questions"][0]["text"] == "Q1"
    assert "correct_choice_id" not in public_quiz["questions"][0]

    result = svc.submit_async_quiz(
        subject=subject,
        job_id=707,
        answers=[
            {"question_id": 1, "selected_choice_id": 1},
            {"question_id": 2, "selected_choice_id": 2},
        ],
    )
    assert result["id"] == 707
    assert result["total_count"] == 2

    async_job.status = AsyncJobStatus.PENDING
    with pytest.raises(ValueError, match="pending"):
        svc.get_async_quiz(subject=subject, job_id=707)

    async_job.status = AsyncJobStatus.COMPLETED
    async_job.output_data = None
    with pytest.raises(ValueError, match="no quiz output"):
        svc.get_async_quiz(subject=subject, job_id=707)
    with pytest.raises(ValueError, match="no quiz output"):
        svc.submit_async_quiz(subject=subject, job_id=707, answers=[])


def test_async_quiz_job_ownership_errors() -> None:
    subject = cast(User, type("U", (), {"pid": 12})())
    with pytest.raises(KeyError):
        StriveService().get_async_quiz(subject=subject, job_id=1)

    async_job_repo = MagicMock()
    async_job_repo.get_by_id.return_value = None
    svc = StriveService(async_job_repo=async_job_repo, job_queue=MagicMock())
    with pytest.raises(KeyError):
        svc.get_async_quiz(subject=subject, job_id=1)

    async_job_repo.get_by_id.return_value = AsyncJob(
        id=1,
        course_id=1,
        created_by_pid=12,
        kind="other",
        input_data={},
    )
    with pytest.raises(KeyError):
        svc.get_async_quiz(subject=subject, job_id=1)

    async_job_repo.get_by_id.return_value = AsyncJob(
        id=1,
        course_id=1,
        created_by_pid=99,
        kind="strive_quiz_generation",
        input_data={},
    )
    with pytest.raises(PermissionError):
        svc.get_async_quiz(subject=subject, job_id=1)


def test_start_quiz_job_requires_async_dependencies() -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 1})())
    activity = cast(Activity, type("A", (), {"id": 1})())

    with pytest.raises(RuntimeError, match="Async job dependencies"):
        svc.start_quiz_job(subject=subject, activity=activity, options=None)
