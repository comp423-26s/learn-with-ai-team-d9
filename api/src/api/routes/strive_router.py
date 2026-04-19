from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from starlette.status import HTTP_201_CREATED

from api.di import AuthenticatedUserDI, ActivityByPathDI, StriveServiceDI
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
    activity: ActivityByPathDI = Depends(),
    body: Annotated[QuizCreateRequest, Body(...)]=Body(...),
    subject: AuthenticatedUserDI = Depends(),
    strive_svc: StriveServiceDI = Depends(),
) -> QuizCreateResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    # Delegate to service (service is authoritative for persistence and generation)
    return strive_svc.start_quiz(subject=subject, activity=activity)


@router.get(
    "/quizzes/{quiz_submission_id}",
    response_model=QuizQuestionsResponse,
    summary="Get questions for a quiz submission",
)
def get_quiz(
    quiz_submission_id: Annotated[int, Path(...)],
    subject: AuthenticatedUserDI = Depends(),
    strive_svc: StriveServiceDI = Depends(),
) -> QuizQuestionsResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    return strive_svc.get_quiz(subject=subject, submission_id=quiz_submission_id)


@router.post(
    "/quizzes/{quiz_submission_id}/submit",
    response_model=QuizSubmitResponse,
    summary="Submit answers for grading",
)
def submit_quiz(
    quiz_submission_id: Annotated[int, Path(...)],
    body: Annotated[QuizSubmitRequest, Body(...)],
    subject: AuthenticatedUserDI = Depends(),
    strive_svc: StriveServiceDI = Depends(),
) -> QuizSubmitResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    return strive_svc.submit_quiz(subject=subject, submission_id=quiz_submission_id, answers=body.answers)
