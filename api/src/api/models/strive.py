from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

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

class QuizCreateResponse(BaseModel):
    """Response returned immediately when a quiz is created/started."""

    id: int = Field(
        ...,
        description="Numeric id for this quiz submission (matches existing Submission.id conventions).",
        example=101,
    )
    activity_id: int = Field(
        ...,
        description="The activity id this quiz is associated with (int path id).",
        example=42,
    )
    student_pid: int = Field(
        ...,
        description="The student's pid (internal numeric identifier).",
        example=730611076,
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
    mode: Literal["daily", "module"] = Field(
        ...,
        description="The quiz generation mode used for this submission.",
        example="daily",
    )
    module_name: Optional[str] = Field(
        default=None,
        description="Module name when mode='module'.",
        example="Module 2: Python Basics",
    )
    topic: Optional[str] = Field(
        default=None,
        description="Topic focus for this submission.",
        example="Loops",
    )

    model_config = ConfigDict(from_attributes=True)


class ChoiceDTO(BaseModel):
    """
    A single multiple-choice option for a question.
    """
    id: int = Field(
        ...,
        description="Local numeric id for the choice option (frontend-friendly).",
        example=2,
    )
    text: str = Field(
        ...,
        description="Display text for the choice option.",
        example="def",
    )

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionDTO(BaseModel):
    """
    A question delivered to the frontend (no correct answer included).
    """
    question_id: int = Field(
        ...,
        description="Local numeric id for this question instance within the submission.",
        example=501,
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
            {"id": 1, "text": "func"},
            {"id": 2, "text": "def"},
            {"id": 3, "text": "function"},
            {"id": 4, "text": "lambda"},
        ],
    )

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionsResponse(BaseModel):
    """
    Response for retrieving a quiz submission's questions.
    (Do NOT include correct answers.)
    """
    id: int = Field(
        ...,
        description="Quiz submission id (numeric).",
        example=101,
    )
    activity_id: int = Field(
        ...,
        description="Associated activity id (int path id).",
        example=42,
    )
    student_pid: int = Field(
        ...,
        description="Student pid who owns this submission.",
        example=730611076,
    )
    status: str = Field(
        ...,
        description="Submission status: 'in_progress' or 'submitted'.",
        example="in_progress",
    )
    mode: Literal["daily", "module"] = Field(
        ...,
        description="Mode used when creating this quiz.",
        example="daily",
    )
    module_name: Optional[str] = Field(
        default=None,
        description="Module name when mode='module'.",
        example="Module 2: Python Basics",
    )
    topic: Optional[str] = Field(
        default=None,
        description="Focus topic for this submission.",
        example="Functions",
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
    question_id: int = Field(
        ...,
        description="The `question_id` for which this answer applies.",
        example=501,
    )
    selected_choice_id: int = Field(
        ...,
        description="The numeric id of the selected choice option.",
        example=2,
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
            {"question_id": 501, "selected_choice_id": 2}
        ],
    )

    model_config = ConfigDict(from_attributes=True)


class QuizFeedbackDTO(BaseModel):
    """
    Per-question feedback returned after grading.
    """
    question_id: int = Field(
        ...,
        description="Question id this feedback refers to.",
        example=501,
    )
    correct: bool = Field(
        ...,
        description="Whether the student's selected answer was correct.",
        example=True,
    )
    correct_choice_id: Optional[int] = Field(
        default=None,
        description="The id of the correct choice (provided for feedback only).",
        example=2,
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Optional short explanation for the correct answer.",
        example="The `def` keyword declares a function in Python.",
    )

    model_config = ConfigDict(from_attributes=True)


class QuizSubmitResponse(BaseModel):
    """
    Response after grading a quiz submission.
    """
    id: int = Field(
        ...,
        description="Quiz submission id which was graded (numeric).",
        example=101,
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
