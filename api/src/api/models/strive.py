from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class QuizCreateRequest(BaseModel):
    """
    Request body for creating/starting a Strive quiz.
    This is explicit so the frontend knows exactly what it can send.
    """

    mode: Literal["daily", "module"] = Field(
        ...,
        description="Type of quiz to generate. 'daily' creates a daily practice quiz, while 'module' creates a quiz focused on a selected unit or module.",
        examples=["daily", "module"],
    )

    module_name: Optional[str] = Field(
        default=None,
        description="Optional module or unit name to target when generating a quiz. Usually used for module-specific practice.",
        examples=["Module 2: Python Basics", "Unit 4: Functions and Loops"],
    )

    topic: Optional[str] = Field(
        default=None,
        description="Optional topic the student wants to practice directly.",
        examples=["Loops", "Lists", "Conditionals"],
    )

    question_count: int = Field(
        default=5,
        description="Number of questions to generate for this quiz attempt.",
        examples=[5],
        ge=1,
        le=10,
    )

    model_config = ConfigDict(from_attributes=True)

class QuizSubmissionResponse(BaseModel):
    """
    Response returned immediately when a quiz is created/started.
    """
    id: UUID = Field(
        default_factory=uuid4,
        description="Unique id for this quiz submission (quiz_submission_id).",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )
    activity_id: UUID = Field(
        ...,
        description="The activity this quiz is associated with.",
        example="9a7b1c2d-3e4f-5678-90ab-cdef12345678",
    )
    student_id: UUID = Field(
        ...,
        description="The id of the student who started the quiz.",
        example="b7a9f1e2-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
    )
    status: str = Field(
        default="in_progress",
        description="Current status of the submission. One of 'in_progress' | 'submitted'.",
        example="in_progress",
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the quiz was started (UTC).",
        example="2026-04-15T12:00:00Z",
    )
    question_count: int = Field(
        ...,
        description="Number of questions included in this submission.",
        example=5,
    )

    model_config = ConfigDict(from_attributes=True)


class ChoiceDTO(BaseModel):
    """
    A single multiple-choice option for a question.
    """
    id: UUID = Field(
        default_factory=uuid4,
        description="Unique id for this choice option.",
        example="d290f1ee-6c54-4b01-90e6-d701748f0851",
    )
    text: str = Field(
        ...,
        description="Display text for the choice option.",
        example="Paris",
    )

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionDTO(BaseModel):
    """
    A question delivered to the frontend (no correct answer included).
    """
    question_id: UUID = Field(
        default_factory=uuid4,
        description="Unique id for this question instance in the submission.",
        example="7c9e6679-7425-40de-944b-e07fc1f90ae7",
    )
    text: str = Field(
        ...,
        description="The question text presented to the student.",
        example="Which Python keyword is used to define a function?",
    )
    choices: List[ChoiceDTO] = Field(
        ...,
        description="Ordered list of possible choices for this question.",
        example=[
            {"id": "1", "text": "func"},
            {"id": "2", "text": "def"},
            {"id": "3", "text": "function"},
            {"id": "4", "text": "lambda"},
        ],
    )

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionsResponse(BaseModel):
    """
    Response for retrieving a quiz submission's questions.
    (Do NOT include correct answers.)
    """
    id: UUID = Field(
        ...,
        description="Quiz submission id.",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )
    activity_id: UUID = Field(
        ...,
        description="Associated activity id.",
        example="9a7b1c2d-3e4f-5678-90ab-cdef12345678",
    )
    student_id: UUID = Field(
        ...,
        description="Student who owns this submission.",
        example="b7a9f1e2-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
    )
    status: str = Field(
        ...,
        description="Submission status: 'in_progress' or 'submitted'.",
        example="in_progress",
    )
    questions: List[QuizQuestionDTO] = Field(
        ...,
        description="List of questions for the submission. Correct answers are omitted.",
    )

    model_config = ConfigDict(from_attributes=True)


class QuizAnswerDTO(BaseModel):
    """
    Single answer provided by the frontend when submitting a quiz.
    """
    question_id: UUID = Field(
        ...,
        description="The `question_id` for which this answer applies.",
        example="7c9e6679-7425-40de-944b-e07fc1f90ae7",
    )
    selected_choice_id: UUID = Field(
        ...,
        description="The id of the selected choice option.",
        example="11111111-1111-1111-1111-111111111111",
    )

    model_config = ConfigDict(from_attributes=True)


class QuizSubmitRequest(BaseModel):
    """
    Request body for submitting answers to a quiz submission.
    """
    answers: List[QuizAnswerDTO] = Field(
        ...,
        description="Answers provided by the student for the submission's questions.",
        example=[
            {
                "question_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                "selected_choice_id": "11111111-1111-1111-1111-111111111111",
            }
        ],
    )

    model_config = ConfigDict(from_attributes=True)


class QuizFeedbackDTO(BaseModel):
    """
    Per-question feedback returned after grading.
    """
    question_id: UUID = Field(
        ...,
        description="Question id this feedback refers to.",
        example="7c9e6679-7425-40de-944b-e07fc1f90ae7",
    )
    correct: bool = Field(
        ...,
        description="Whether the student's selected answer was correct.",
        example=True,
    )
    correct_choice_id: Optional[UUID] = Field(
        default=None,
        description="The id of the correct choice (provided for feedback only).",
        example="11111111-1111-1111-1111-111111111111",
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Optional short explanation for the correct answer.",
        example="Paris is the capital and most populous city of France.",
    )

    model_config = ConfigDict(from_attributes=True)


class QuizSubmitResponse(BaseModel):
    """
    Response after grading a quiz submission.
    """
    id: UUID = Field(
        ...,
        description="Quiz submission id which was graded.",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )
    score: float = Field(
        ...,
        description="Score as a percentage between 0 and 100.",
        example=80.0,
    )
    correct_count: int = Field(
        ...,
        description="Number of correctly answered questions.",
        example=4,
    )
    total_count: int = Field(
        ...,
        description="Total number of questions in the submission.",
        example=5,
    )
    feedback: List[QuizFeedbackDTO] = Field(
        ...,
        description="Per-question feedback describing correctness and optional explanation.",
    )
    finished_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the quiz was graded/completed (UTC).",
        example="2026-04-15T12:05:00Z",
    )

    model_config = ConfigDict(from_attributes=True)
