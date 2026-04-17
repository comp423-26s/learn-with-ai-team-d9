from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, JSON


class QuizStatus(str, Enum):
    in_progress = "in_progress"
    submitted = "submitted"


class QuizSubmission(SQLModel, table=True):
    """Represents a student's quiz session/submission."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    activity_id: UUID
    student_id: UUID
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    status: QuizStatus = Field(default=QuizStatus.in_progress)
    score: Optional[float] = None


class QuizQuestion(SQLModel, table=True):
    """A question instance attached to a specific submission. Embedded for MVP."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    submission_id: UUID
    question_text: str
    choices: dict = Field(sa_column=JSON(), default_factory=dict)
    correct_choice_id: str


class QuizAnswer(SQLModel, table=True):
    """An answer provided by the student for a question in a submission."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    submission_id: UUID
    question_id: UUID
    selected_choice_id: str
    is_correct: bool = False
