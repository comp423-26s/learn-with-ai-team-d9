from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, Query
from learnwithai.interfaces.jobs import JobUpdate
from learnwithai_jobqueue.rabbitmq_job_notifier import RabbitMQJobNotifier
from starlette.status import HTTP_201_CREATED

from api.di import ActivityByPathDI, AuthenticatedUserDI, SettingsDI, StriveServiceDI
from api.models.strive import (
    LeaderboardResponse,
    QuizCreateRequest,
    QuizCreateResponse,
    QuizQuestionsResponse,
    QuizResultsResponse,
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
    settings: SettingsDI,
) -> QuizSubmitResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    try:
        # Convert Pydantic DTOs to plain dicts for the in-memory service implementation
        answers = [a.model_dump() for a in body.answers]
        response = QuizSubmitResponse.model_validate(
            strive_svc.submit_quiz(subject=subject, submission_id=quiz_submission_id, answers=answers)
        )
        course_id = strive_svc.get_submission_course_id(subject=subject, submission_id=quiz_submission_id)
        notifier = RabbitMQJobNotifier(settings.effective_rabbitmq_url)
        notifier.notify(
            JobUpdate(
                job_id=quiz_submission_id,
                course_id=course_id,
                user_id=subject.pid,
                kind="daily_practice_leaderboard",
                status="updated",
            )
        )
        notifier.close()
        return response
    except KeyError:
        raise HTTPException(status_code=404, detail="Quiz submission not found")


@router.get(
    "/quizzes/{quiz_submission_id}/results",
    response_model=QuizResultsResponse,
    summary="Get final quiz results with summary feedback",
)
def get_quiz_results(
    subject: AuthenticatedUserDI,
    quiz_submission_id: Annotated[int, Path(...)],
    strive_svc: StriveServiceDI,
) -> QuizResultsResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    try:
        return QuizResultsResponse.model_validate(
            strive_svc.get_results(subject=subject, submission_id=quiz_submission_id)
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Quiz results not found")


@router.get(
    "/daily-practice/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get the daily practice leaderboard",
)
def get_leaderboard(
    subject: AuthenticatedUserDI,
    course_id: Annotated[int, Query(...)],
    strive_svc: StriveServiceDI,
    limit: int = Query(10, ge=1, le=100),
) -> LeaderboardResponse:
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired.")
    return LeaderboardResponse.model_validate(
        strive_svc.get_leaderboard(subject=subject, course_id=course_id, limit=limit)
    )
