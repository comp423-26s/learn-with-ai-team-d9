from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from api.models.strive import QuizCreateRequest, QuizSubmitRequest
from api.routes.strive_router import get_quiz, start_quiz, submit_quiz, upload_pdf_and_generate_quiz


class DummyActivity:
    def __init__(self, id: int) -> None:
        self.id = id


class DummyUser:
    def __init__(self, pid: int) -> None:
        self.pid = pid


class FailingBytesIO(BytesIO):
    def read(self, *args: Any, **kwargs: Any) -> bytes:
        raise RuntimeError("cannot read file")


def _stub_activity(activity_id: int = 1) -> Any:
    return DummyActivity(activity_id)


def _stub_user(pid: int = 123) -> Any:
    return DummyUser(pid)


def _make_pdf_upload_file(content: bytes = b"%PDF-1.4 test pdf") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename="quiz.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )


def _make_quiz_payload() -> dict[str, Any]:
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "id": 101,
        "activity_id": 1,
        "student_pid": 123,
        "status": "in_progress",
        "started_at": started_at,
        "question_count": 5,
        "mode": "module",
        "module_name": None,
        "topic": None,
        "questions": [
            {
                "question_id": 1,
                "text": "Sample question",
                "choices": [
                    {"id": 1, "text": "Choice A"},
                    {"id": 2, "text": "Choice B"},
                ],
            }
        ],
    }


class FailingService:
    def start_quiz(self, *a: Any, **k: Any) -> None:
        raise KeyError("no activity")

    def get_quiz(self, *a: Any, **k: Any) -> None:
        raise KeyError("no quiz")

    def submit_quiz(self, *a: Any, **k: Any) -> None:
        raise KeyError("no quiz")

    def generate_quiz_from_pdf(self, *a: Any, **k: Any) -> None:
        raise KeyError("no activity")


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


def test_upload_pdf_and_generate_quiz_returns_response() -> None:
    activity: Any = _stub_activity(1)
    subject: Any = _stub_user(123)
    strive_svc: Any = MagicMock()
    strive_svc.generate_quiz_from_pdf.return_value = _make_quiz_payload()
    file = _make_pdf_upload_file()

    result = upload_pdf_and_generate_quiz(
        activity=activity,
        file=file,
        subject=subject,
        strive_svc=strive_svc,  # type: ignore[arg-type]
        question_count=7,
    )

    assert result.id == 101
    assert result.activity_id == 1
    assert result.student_pid == 123
    assert result.questions[0].question_id == 1
    strive_svc.generate_quiz_from_pdf.assert_called_once_with(
        subject=subject,
        activity=activity,
        pdf_bytes=b"%PDF-1.4 test pdf",
        question_count=7,
    )


def test_upload_pdf_and_generate_quiz_rejects_non_pdf() -> None:
    activity: Any = _stub_activity(1)
    subject: Any = _stub_user(123)
    file = UploadFile(
        file=BytesIO(b"not a pdf"),
        filename="quiz.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    try:
        upload_pdf_and_generate_quiz(
            activity=activity,
            file=file,
            subject=subject,
            strive_svc=FailingService(),  # type: ignore[arg-type]
        )
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 400


def test_upload_pdf_and_generate_quiz_unwired_raises_501() -> None:
    activity: Any = _stub_activity(1)
    subject: Any = _stub_user(123)
    file = _make_pdf_upload_file()

    try:
        upload_pdf_and_generate_quiz(
            activity=activity,
            file=file,
            subject=subject,
            strive_svc=None,  # type: ignore[arg-type]
        )
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 501


def test_upload_pdf_and_generate_quiz_rejects_unreadable_file() -> None:
    activity: Any = _stub_activity(1)
    subject: Any = _stub_user(123)
    bad_file = UploadFile(
        file=FailingBytesIO(),
        filename="quiz.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    try:
        upload_pdf_and_generate_quiz(
            activity=activity,
            file=bad_file,
            subject=subject,
            strive_svc=FailingService(),  # type: ignore[arg-type]
        )
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 400


def test_upload_pdf_and_generate_quiz_rejects_oversized_file() -> None:
    activity: Any = _stub_activity(1)
    subject: Any = _stub_user(123)
    file = _make_pdf_upload_file(content=b"x" * (10 * 1024 * 1024 + 1))

    try:
        upload_pdf_and_generate_quiz(
            activity=activity,
            file=file,
            subject=subject,
            strive_svc=FailingService(),  # type: ignore[arg-type]
        )
        raise AssertionError("expected HTTPException")
    except HTTPException as e:
        assert e.status_code == 413


def test_upload_pdf_and_generate_quiz_translates_service_errors() -> None:
    activity: Any = _stub_activity(1)
    subject: Any = _stub_user(123)

    class ValueErrorService:
        def generate_quiz_from_pdf(self, *a: Any, **k: Any) -> None:
            raise ValueError("bad input")

    class GenericErrorService:
        def generate_quiz_from_pdf(self, *a: Any, **k: Any) -> None:
            raise RuntimeError("boom")

    cases: list[tuple[Any, int, str]] = [
        (FailingService(), 404, "Strive activity not found"),
        (ValueErrorService(), 400, "bad input"),
        (GenericErrorService(), 500, "Failed to generate quiz from PDF: boom"),
    ]

    for service, expected_status, expected_detail in cases:
        file = _make_pdf_upload_file()
        try:
            upload_pdf_and_generate_quiz(
                activity=activity,
                file=file,
                subject=subject,
                strive_svc=service,  # type: ignore[arg-type]
            )
            raise AssertionError("expected HTTPException")
        except HTTPException as e:
            assert e.status_code == expected_status
            assert e.detail == expected_detail
