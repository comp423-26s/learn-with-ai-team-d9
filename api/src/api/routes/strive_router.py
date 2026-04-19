from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path
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
        return strive_svc.start_quiz(subject=subject, activity=activity, options=body)
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
        return strive_svc.get_quiz(subject=subject, submission_id=quiz_submission_id)
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
        return strive_svc.submit_quiz(subject=subject, submission_id=quiz_submission_id, answers=body.answers)
    except KeyError:
        raise HTTPException(status_code=404, detail="Quiz submission not found")
