from __future__ import annotations

# ruff: noqa: I001

from typing import Any, List, Literal, Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field as _PydanticField

# Some pydantic Field callsites use keyword combinations that the type stubs
# flag as not matching overloads. Treat `Field` as `Any` here so the type
# checker does not raise spurious overload errors for legitimate runtime use.
Field: Any = _PydanticField


class QuizCreateRequest(BaseModel):
    """Request body to start a Strive quiz (minimal)."""

    mode: Literal["daily", "module"] = Field(
        ...,
        description="Quiz generation mode. 'daily' for a daily practice quiz, 'module' for a module-focused quiz.",
        json_schema_extra={"examples": ["daily", "module"]},
    )

    module_name: Optional[str] = Field(
        default=None,
        description="Optional module name when `mode` is 'module'.",
        json_schema_extra={"examples": ["Module 2: Python Basics"]},
    )

    topic: Optional[str] = Field(
        default=None,
        description="Optional topic to focus the questions on.",
        json_schema_extra={"examples": ["Loops", "Lists"]},
    )

    question_count: int = Field(
        default=5,
        description="Number of multiple-choice questions to generate (1–10).",
        json_schema_extra={"example": 5},
        ge=1,
        le=10,
    )

    model_config = ConfigDict(from_attributes=True)


class QuizCreateResponse(BaseModel):
    """Response returned when a quiz submission is created."""

    id: int = Field(..., description="Quiz submission id (numeric).", json_schema_extra={"example": 101})
    activity_id: int = Field(..., description="Associated activity id.", json_schema_extra={"example": 42})
    student_pid: int = Field(..., description="Owner student's pid.", json_schema_extra={"example": 730611076})
    status: str = Field(
        ...,
        description="Submission status: 'in_progress' or 'submitted'.",
        json_schema_extra={"example": "in_progress"},
    )
    started_at: datetime = Field(
        ..., description="UTC timestamp when quiz was started.", json_schema_extra={"example": "2026-04-15T12:00:00Z"}
    )
    question_count: int = Field(
        ..., description="Number of questions in the submission.", json_schema_extra={"example": 5}
    )
    mode: Literal["daily", "module"] = Field(
        ..., description="Generation mode used.", json_schema_extra={"example": "daily"}
    )
    module_name: Optional[str] = Field(
        default=None,
        description="Module name when mode='module'.",
        json_schema_extra={"example": "Module 2: Python Basics"},
    )
    topic: Optional[str] = Field(
        default=None, description="Topic focus for this quiz.", json_schema_extra={"example": "Functions"}
    )

    model_config = ConfigDict(from_attributes=True)


class ChoiceDTO(BaseModel):
    """Single multiple-choice option."""

    id: int = Field(..., description="Choice id local to the question.", json_schema_extra={"example": 2})
    text: str = Field(..., description="Display text for the choice.", json_schema_extra={"example": "def"})

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionDTO(BaseModel):
    """Question returned to the frontend (no correct answer)."""

    question_id: int = Field(
        ..., description="Local question id within the submission.", json_schema_extra={"example": 1}
    )
    text: str = Field(
        ...,
        description="Question text shown to the student.",
        json_schema_extra={"example": "Which keyword defines a function in Python?"},
    )
    choices: List[ChoiceDTO] = Field(..., description="Ordered list of choices.")

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionsResponse(BaseModel):
    """Response for retrieving a quiz's questions (no answers included)."""

    id: int = Field(..., description="Quiz submission id.", json_schema_extra={"example": 101})
    activity_id: int = Field(..., description="Associated activity id.", json_schema_extra={"example": 42})
    student_pid: int = Field(..., description="Owner student's pid.", json_schema_extra={"example": 730611076})
    status: str = Field(..., description="Submission status.", json_schema_extra={"example": "in_progress"})
    mode: Literal["daily", "module"] = Field(
        ..., description="Generation mode.", json_schema_extra={"example": "daily"}
    )
    module_name: Optional[str] = Field(
        default=None,
        description="Module name when mode='module'.",
        json_schema_extra={"example": "Module 2: Python Basics"},
    )
    topic: Optional[str] = Field(default=None, description="Topic focus.", json_schema_extra={"example": "Functions"})
    questions: List[QuizQuestionDTO] = Field(..., description="List of questions for the submission.")

    model_config = ConfigDict(from_attributes=True)


class QuizAnswerDTO(BaseModel):
    """Single answer payload from the frontend when submitting a quiz."""

    question_id: int = Field(..., description="Local question id being answered.", json_schema_extra={"example": 1})
    selected_choice_id: int = Field(..., description="Selected choice id.", json_schema_extra={"example": 2})

    model_config = ConfigDict(from_attributes=True)


class QuizSubmitRequest(BaseModel):
    """Request body for submitting quiz answers."""

    answers: List[QuizAnswerDTO] = Field(
        ...,
        description="List of answers for the submission.",
        json_schema_extra={"example": [{"question_id": 1, "selected_choice_id": 2}]},
    )

    model_config = ConfigDict(from_attributes=True)


class QuizFeedbackDTO(BaseModel):
    """Per-question feedback returned after grading."""

    question_id: int = Field(..., description="Question id.", json_schema_extra={"example": 1})
    correct: bool = Field(
        ..., description="Whether the submitted answer was correct.", json_schema_extra={"example": True}
    )
    correct_choice_id: Optional[int] = Field(
        default=None,
        description="The correct choice id.",
        json_schema_extra={"example": 2},
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Short explanation for the correct answer.",
        json_schema_extra={"example": "The `def` keyword declares a function."},
    )

    model_config = ConfigDict(from_attributes=True)


class QuizSubmitResponse(BaseModel):
    """Response after grading a quiz submission."""

    id: int = Field(..., description="Quiz submission id.", json_schema_extra={"example": 101})
    score: float = Field(..., description="Score as percentage (0-100).", json_schema_extra={"example": 80.0})
    correct_count: int = Field(..., description="Number of correct answers.", json_schema_extra={"example": 4})
    total_count: int = Field(..., description="Total number of questions.", json_schema_extra={"example": 5})
    feedback: List[QuizFeedbackDTO] = Field(..., description="Per-question feedback.")
    finished_at: datetime = Field(
        ..., description="UTC timestamp when grading completed.", json_schema_extra={"example": "2026-04-15T12:05:00Z"}
    )

    model_config = ConfigDict(from_attributes=True)


class SourceSummaryResponse(BaseModel):
    """Summary for a persisted Strive source file."""

    source_id: int = Field(..., description="Source row id.", json_schema_extra={"example": 501})
    activity_id: int = Field(
        ..., description="Activity id the source was uploaded for.", json_schema_extra={"example": 42}
    )
    filename: Optional[str] = Field(
        default=None,
        description="Original uploaded filename.",
        json_schema_extra={"example": "lesson-notes.pdf"},
    )
    content_type: str = Field(
        ..., description="MIME type for the stored file.", json_schema_extra={"example": "application/pdf"}
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the source was stored.",
        json_schema_extra={"example": "2026-04-20T12:00:00Z"},
    )

    model_config = ConfigDict(from_attributes=True)


class SourceQuizCreateRequest(BaseModel):
    """Request body for generating a quiz from a stored source."""

    question_count: int = Field(
        default=5,
        description="Number of multiple-choice questions to generate (1–10).",
        json_schema_extra={"example": 5},
        ge=1,
        le=10,
    )

    model_config = ConfigDict(from_attributes=True)
