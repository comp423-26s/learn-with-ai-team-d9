from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from starlette.status import HTTP_201_CREATED

from api.di import AuthenticatedUserDI, StriveServiceDI
from api.models.strive import (
    QuizCreateRequest,
    QuizCreateResponse,
    QuizQuestionsResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)

router = APIRouter(tags=["Strive"])

# The router now uses the `StriveService` DI factory from `api.di`.


@router.post(
    "/activities/{activity_id}/quizzes",
    status_code=HTTP_201_CREATED,
    response_model=QuizCreateResponse,
    summary="Start a quiz for an activity",
    description=(
        "Create a new quiz submission for the given activity. "
        "Delegates quiz creation to the Strive service."
    ),
    responses={
        400: {"description": "Bad request (invalid parameters)"},
        401: {"description": "Unauthorized"},
        404: {"description": "Activity not found"},
        501: {"description": "Service not implemented (TODO)"},
    },
)
def start_quiz(
    activity_id: Annotated[
        int,
        Path(
            ...,
            description="Unique identifier of the activity for which the quiz is being created.",
            examples=[42],
            gt=0,
        ),
    ],
    body: Annotated[
        QuizCreateRequest,
        Body(
            ...,
            description="Quiz creation parameters.",
            openapi_examples={
                "daily_quiz": {
                    "summary": "Daily quiz",
                    "description": "Create a standard 5-question daily practice quiz.",
                    "value": {
                        "mode": "daily",
                        "question_count": 5,
                    },
                },
                "module_quiz": {
                    "summary": "Module quiz",
                    "description": "Create a quiz focused on a selected module and topic.",
                    "value": {
                        "mode": "module",
                        "module_name": "Module 2: Python Basics",
                        "topic": "Loops",
                        "question_count": 5,
                    },
                },
            },
        ),
    ],
    subject: AuthenticatedUserDI = Depends(),
    strive_svc: StriveServiceDI = Depends(),
) -> QuizCreateResponse:
    """
    Start a new quiz submission.

    The route handler stays thin and delegates creation logic to the Strive service.
    """
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired (TODO).")

    return strive_svc.start_quiz(
        subject=subject,
        activity_id=activity_id,
        request=body,
    )


@router.get(
    "/quizzes/{quiz_submission_id}",
    response_model=QuizQuestionsResponse,
    summary="Get questions for a quiz submission",
    description=(
        "Retrieve the quiz questions for the specified submission. "
        "Correct answers are not included in this response."
    ),
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Quiz submission not found"},
        501: {"description": "Service not implemented (TODO)"},
    },
)
def get_quiz(
    quiz_submission_id: Annotated[
        int,
        Path(
            ...,
            description="Unique identifier of the quiz submission.",
            examples=[101],
            gt=0,
        ),
    ],
    subject: AuthenticatedUserDI = Depends(),
    strive_svc: StriveServiceDI = Depends(),
) -> QuizQuestionsResponse:
    """
    Return the questions for a quiz submission.

    Business logic is delegated to the Strive service.
    """
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired (TODO).")

    return strive_svc.get_quiz(
        subject=subject,
        submission_id=quiz_submission_id,
    )


@router.post(
    "/quizzes/{quiz_submission_id}/submit",
    response_model=QuizSubmitResponse,
    summary="Submit answers for grading",
    description=(
        "Submit student answers for grading and return the score along with "
        "per-question feedback."
    ),
    responses={
        400: {"description": "Malformed request or invalid answers"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden (not owner's submission)"},
        404: {"description": "Quiz submission not found"},
        409: {"description": "Submission already graded or closed"},
        501: {"description": "Service not implemented (TODO)"},
    },
)
def submit_quiz(
    quiz_submission_id: Annotated[
        int,
        Path(
            ...,
            description="Unique identifier of the quiz submission being submitted.",
            examples=[101],
            gt=0,
        ),
    ],
    body: Annotated[
        QuizSubmitRequest,
        Body(
            ...,
            description="Student answers for the quiz submission.",
        ),
    ],
    subject: AuthenticatedUserDI = Depends(),
    strive_svc: StriveServiceDI = Depends(),
) -> QuizSubmitResponse:
    """
    Grade the provided answers and return score plus feedback.

    Business logic belongs in the Strive service, not in this route handler.
    """
    if strive_svc is None:
        raise HTTPException(status_code=501, detail="StriveService not wired (TODO).")

    return strive_svc.submit_quiz(
        subject=subject,
        submission_id=quiz_submission_id,
        answers=body.answers,
    )