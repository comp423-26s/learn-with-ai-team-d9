from __future__ import annotations

import json
import zlib
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
    assert "Base questions and answers on the SOURCE CONTENT below." in prompt
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
    assert "SOURCE CONTENT" not in prompt


def test_extract_text_from_pdf_bytes_returns_empty_when_no_text_fragments() -> None:
    svc = StriveService()

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    extracted = svc._extract_text_from_pdf_bytes(pdf_bytes)

    assert extracted == ""


def test_extract_text_from_pdf_bytes_breaks_and_truncates_at_max_chars() -> None:
    svc = StriveService()

    # Multiple TJ fragments ensure the loop can hit the early-break branch.
    stream_payload = "(aaaaa) TJ\n(bbbbb) TJ\n(ccccc) TJ\n(dddddd) TJ\n"
    pdf_like = f"stream\n{stream_payload}endstream\n".encode("latin-1")

    extracted = svc._extract_text_from_pdf_bytes(pdf_like, max_chars=11)

    assert extracted == "aaaaa bbbbb"


def test_extract_text_from_pdf_bytes_reads_multiple_streams_when_under_limit() -> None:
    svc = StriveService()

    pdf_like = ("stream\n(hello) TJ\nendstream\nstream\n(world) TJ\nendstream\n").encode("latin-1")

    extracted = svc._extract_text_from_pdf_bytes(pdf_like, max_chars=100)

    assert extracted == "hello world"


def test_extract_text_from_pdf_bytes_unescapes_literal_sequences() -> None:
    svc = StriveService()

    pdf_like = (r"stream\n(Hello\ \(world\)\nline) Tj\nendstream\n").encode("latin-1")

    extracted = svc._extract_text_from_pdf_bytes(pdf_like, max_chars=200)

    assert extracted == "Hello (world) line"


def test_extract_text_from_pdf_bytes_reads_hex_text_tokens() -> None:
    svc = StriveService()

    pdf_like = b"stream\n<48656C6C6F> Tj\nendstream\n"

    extracted = svc._extract_text_from_pdf_bytes(pdf_like, max_chars=200)

    assert extracted == "Hello"


def test_extract_text_from_pdf_bytes_reads_flate_streams() -> None:
    svc = StriveService()

    compressed_stream = zlib.compress(b"(Compressed text) Tj\n")
    pdf_like = b"stream\n" + compressed_stream + b"\nendstream\n"

    extracted = svc._extract_text_from_pdf_bytes(pdf_like, max_chars=200)

    assert extracted == "Compressed text"


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
    subject = cast(User, type("U", (), {"pid": 77})())
    activity = cast(Activity, type("A", (), {"id": 55})())
    pdf_bytes = b"%PDF-1.4 test"

    questions = _mock_questions(3)
    study_material = {
        "schema_version": 1,
        "title": "Functions",
        "facts": ["Functions can return values."],
    }

    with (
        patch("learnwithai.services.strive_service.os.makedirs"),
        patch("builtins.open", MagicMock()),
        patch.object(svc, "extract_study_material_from_pdf", return_value=study_material) as extract_mock,
        patch.object(svc, "_extract_text_from_pdf_bytes", return_value="A source excerpt."),
        patch.object(svc, "_generate_questions_with_llm", return_value=questions) as gen_mock,
    ):
        result = svc.generate_quiz_from_pdf(subject=subject, activity=activity, pdf_bytes=pdf_bytes, question_count=3)

    extract_mock.assert_called_once_with(pdf_bytes)
    gen_mock.assert_called_once()
    assert gen_mock.call_args.kwargs["qcount"] == 3
    assert json.loads(gen_mock.call_args.kwargs["source_excerpt"]) == study_material
    gen_mock.assert_called_once_with(qcount=3, source_excerpt="A source excerpt.")

    assert result["student_pid"] == 77
    assert result["activity_id"] == 55
    assert result["status"] == "in_progress"
    assert result["question_count"] == 3
    assert result["mode"] == "module"
    assert len(result["questions"]) == 3
    # public questions must not include correct_choice_id
    for q in result["questions"]:
        assert "correct_choice_id" not in q
    assert result["id"] in strive_service_module._QUIZ_STORE


def test_generate_quiz_from_pdf_llm_fallback(tmp_path: Any) -> None:
    svc = StriveService()
    subject = cast(User, type("U", (), {"pid": 88})())
    activity = cast(Activity, type("A", (), {"id": 66})())
    pdf_bytes = b"%PDF-1.4 test"

    with (
        patch("learnwithai.services.strive_service.os.makedirs"),
        patch("builtins.open", MagicMock()),
        patch.object(svc, "extract_study_material_from_pdf", return_value={"facts": ["A"]}),
        patch.object(svc, "_generate_questions_with_llm", side_effect=RuntimeError("LLM down")),
    ):
        result = svc.generate_quiz_from_pdf(subject=subject, activity=activity, pdf_bytes=pdf_bytes, question_count=2)

    assert result["question_count"] == 2
    assert len(result["questions"]) == 2
    for q in result["questions"]:
        assert "PDF source" in q["text"]
        assert len(q["choices"]) == 4


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


def test_extract_study_material_from_pdf_raises_when_no_text() -> None:
    svc = StriveService()

    with patch.object(svc, "_extract_text_from_pdf_bytes", return_value=""):
        with pytest.raises(ValueError, match="Could not extract readable text from PDF"):
            svc.extract_study_material_from_pdf(b"%PDF-1.4")


def test_extract_study_material_from_pdf_calls_llm_helper() -> None:
    svc = StriveService()
    expected = {"title": "Study", "facts": ["A"]}

    with (
        patch.object(svc, "_extract_text_from_pdf_bytes", return_value="source text"),
        patch.object(svc, "_extract_study_material_with_llm", return_value=expected) as helper,
    ):
        result = svc.extract_study_material_from_pdf(b"%PDF-1.4")

    helper.assert_called_once_with("source text")
    assert result == expected


def test_extract_study_material_with_llm_retries_and_fails_on_invalid_json() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "not-json"

    with patch.object(svc.client.chat.completions, "create", side_effect=[mock_completion, mock_completion]):
        with pytest.raises(ValueError, match="Study material extraction returned invalid JSON content"):
            svc._extract_study_material_with_llm("source")


def test_extract_study_material_with_llm_retries_after_normalize_error() -> None:
    svc = StriveService()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "{}"

    with (
        patch.object(svc.client.chat.completions, "create", side_effect=[mock_completion, mock_completion]),
        patch.object(
            svc,
            "_normalize_study_material_payload",
            side_effect=[ValueError("bad payload"), {"title": "ok"}],
        ) as normalize,
    ):
        result = svc._extract_study_material_with_llm("source")

    assert result == {"title": "ok"}
    assert normalize.call_count == 2


def test_normalize_study_material_payload_rejects_non_object() -> None:
    svc = StriveService()

    with pytest.raises(ValueError, match="non-object"):
        svc._normalize_study_material_payload([1, 2, 3], source_text="src")


def test_normalize_study_material_payload_branches() -> None:
    svc = StriveService()

    # No summary/concepts/facts should fail validation.
    with pytest.raises(ValueError, match="did not include usable study content"):
        svc._normalize_study_material_payload(
            {
                "title": "",
                "summary": "",
                "learning_objectives": "not-a-list",
                "key_terms": [123, {"term": "", "definition": "x"}],
                "concepts": [123, {"name": "", "explanation": ""}],
                "facts": [],
                "examples": ["bad"],
                "misconceptions": ["bad"],
            },
            source_text="source",
        )

    payload = svc._normalize_study_material_payload(
        {
            "title": "  ",
            "summary": "  Some summary.  ",
            "learning_objectives": ["  Understand loops  ", ""],
            "key_terms": [
                123,
                {"term": " variable ", "definition": " storage value "},
                {"term": "", "definition": "ignored"},
            ],
            "concepts": [
                "bad",
                {"name": "Loops", "explanation": "Repeat actions", "supporting_details": [" while ", ""]},
                {"name": "", "explanation": "missing name"},
            ],
            "facts": ["  Fact 1  "],
            "examples": [{"prompt": " Example ", "explanation": " Details "}],
            "misconceptions": [{"misconception": "A", "correction": "B"}],
        },
        source_text="source text",
    )

    assert payload["title"] == "Uploaded study material"
    assert payload["summary"] == "Some summary."
    assert payload["learning_objectives"] == ["Understand loops"]
    assert payload["key_terms"] == [{"term": "variable", "definition": "storage value"}]
    assert payload["concepts"] == [{"name": "Loops", "explanation": "Repeat actions", "supporting_details": ["while"]}]
    assert payload["facts"] == ["Fact 1"]


def test_extract_text_from_pdf_bytes_uses_plaintext_fragments_fallback() -> None:
    svc = StriveService()

    pdf_like = (
        "%PDF-1.4\n"
        "1 0 obj\n"
        "Tiny\n"
        "This is a meaningful sentence for fallback extraction.\n"
        "Another helpful sentence for quiz creation.\n"
        "endobj\n"
    ).encode("latin-1")

    extracted = svc._extract_text_from_pdf_bytes(pdf_like, max_chars=300)

    assert "meaningful sentence" in extracted
    assert "helpful sentence" in extracted


def test_decode_pdf_hex_text_branch_cases() -> None:
    svc = StriveService()

    assert svc._decode_pdf_hex_text("") == ""
    assert svc._decode_pdf_hex_text("ZZ") == ""
    assert svc._decode_pdf_hex_text("414") == "A@"
    assert svc._decode_pdf_hex_text("FEFF00410042") == "AB"


def test_helper_branch_returns_for_non_list_inputs() -> None:
    svc = StriveService()

    assert svc._clean_text(None) == ""
    assert svc._normalize_named_items("not-a-list", name_key="term", text_key="definition") == []
    assert svc._normalize_concepts("not-a-list") == []


def test_extract_pdf_text_fragments_covers_array_and_direct_hex_paths() -> None:
    svc = StriveService()

    # Covers array literals/hex and direct hex Tj including non-appending decoded blank text.
    content = "[(alpha) <4869>] TJ <4142> Tj <20> Tj"
    fragments = svc._extract_pdf_text_fragments(content)

    assert "alpha" in fragments
    assert "Hi" in fragments
    assert "AB" in fragments


def test_extract_pdf_text_fragments_skips_whitespace_only_hex_chunks() -> None:
    svc = StriveService()

    fragments = svc._extract_pdf_text_fragments("[(keep) <20>] TJ")

    assert fragments == ["keep"]


def test_unescape_pdf_literal_octal_sequence() -> None:
    svc = StriveService()

    assert svc._unescape_pdf_literal(r"Letter:\040\141") == "Letter: a"
