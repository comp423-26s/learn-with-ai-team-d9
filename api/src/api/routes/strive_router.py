from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, File, Form, HTTPException, Path, UploadFile
from starlette.status import HTTP_201_CREATED

from api.di import ActivityByPathDI, AuthenticatedUserDI, StriveServiceDI
from api.models.strive import (
    QuizCreateRequest,
    QuizCreateResponse,
    QuizQuestionsResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)

router = APIRouter(tags=["Strive"])


@router.post(
    "/activities/{activity_id}/quizzes",
    status_code=HTTP_201_CREATED,
    response_model=QuizCreateResponse,
    summary="Start a quiz for an activity",
)
def start_quiz(
    activity: ActivityByPathDI,
    body: Annotated[QuizCreateRequest, Body(...)],
    subject: AuthenticatedUserDI,
    strive_svc: StriveServiceDI,
) -> QuizCreateResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    # Delegate to service (service is authoritative for persistence and generation)
    try:
        return QuizCreateResponse.model_validate(
            strive_svc.start_quiz(subject=subject, activity=activity, options=body)
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Strive activity not found")


@router.get(
    "/quizzes/{quiz_submission_id}",
    response_model=QuizQuestionsResponse,
    summary="Get questions for a quiz submission",
)
def get_quiz(
    quiz_submission_id: Annotated[int, Path(...)],
    subject: AuthenticatedUserDI,
    strive_svc: StriveServiceDI,
) -> QuizQuestionsResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    try:
        return QuizQuestionsResponse.model_validate(
            strive_svc.get_quiz(subject=subject, submission_id=quiz_submission_id)
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Quiz submission not found")


@router.post(
    "/quizzes/{quiz_submission_id}/submit",
    response_model=QuizSubmitResponse,
    summary="Submit answers for grading",
)
def submit_quiz(
    quiz_submission_id: Annotated[int, Path(...)],
    body: Annotated[QuizSubmitRequest, Body(...)],
    subject: AuthenticatedUserDI,
    strive_svc: StriveServiceDI,
) -> QuizSubmitResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    try:
        # Convert Pydantic DTOs to plain dicts for the in-memory service implementation
        answers = [a.model_dump() for a in body.answers]
        return QuizSubmitResponse.model_validate(
            strive_svc.submit_quiz(subject=subject, submission_id=quiz_submission_id, answers=answers)
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Quiz submission not found")


@router.post(
    "/activities/{activity_id}/quizzes/upload-pdf",
    status_code=HTTP_201_CREATED,
    response_model=QuizQuestionsResponse,
    summary="Upload PDF and generate a quiz synchronously",
)
def upload_pdf_and_generate_quiz(
    activity: ActivityByPathDI,
    file: Annotated[UploadFile, File(...)],
    subject: AuthenticatedUserDI,
    strive_svc: StriveServiceDI,
    question_count: int = Form(5),
) -> QuizQuestionsResponse:
    """
    Accepts a PDF upload and synchronously generates a quiz from its text.

    - `file`: uploaded PDF file (multipart/form-data)
    - `question_count`: optional form field (defaults to 5)
    """
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")

    # Basic validations
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF")

    # Read file synchronously from the underlying file object to avoid async
    # event-loop complications in a synchronous handler.
    try:
        content = file.file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read uploaded file")

    MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is too large")

    try:
        # Delegate to the Strive service; service should accept PDF bytes and return
        # a submission dict compatible with QuizQuestionsResponse
        result = strive_svc.generate_quiz_from_pdf(
            subject=subject, activity=activity, pdf_bytes=content, question_count=question_count
        )
        return QuizQuestionsResponse.model_validate(result)
    except KeyError:
        raise HTTPException(status_code=404, detail="Strive activity not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate quiz from PDF: {exc}")
