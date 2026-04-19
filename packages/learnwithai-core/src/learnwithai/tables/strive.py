"""Strive activity DB tables (SQLModel).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class StriveActivity(SQLModel, table=True):
    """Configuration for a Strive activity tied to an existing activity."""

    __tablename__ = "strive_activity"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    activity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("activity.id"), nullable=False, unique=True),
    )
    mode: str = Field(sa_column=Column(String, nullable=False))
    module_name: str | None = Field(default=None)
    topic: str | None = Field(default=None)
    question_count: int = Field(default=5, sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        default=None,
    )


class StriveQuestionSet(SQLModel, table=True):
    """A stored set of questions for a Strive activity.

    `questions` is JSONB and expected to be an array of question objects with
    stable question ids to allow submissions to refer to them.
    """

    __tablename__ = "strive_question_set"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    strive_activity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("strive_activity.id", ondelete="CASCADE"), nullable=False),
    )
    questions: Any = Field(
        sa_column=Column(JSONB, nullable=False),
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        default=None,
    )


class StriveSubmission(SQLModel, table=True):
    """Per-submission detail for a Strive quiz attempt.

    `student_pid` references `user.pid` and is NOT UNIQUE (students can submit
    multiple times). `submitted_answers` is JSONB mapping question ids to
    selected choice ids (and optional metadata).
    """

    __tablename__ = "strive_submission"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    submission_id: int = Field(
        sa_column=Column(Integer, ForeignKey("submission.id"), nullable=False, unique=True),
    )
    question_set_id: int = Field(
        sa_column=Column(Integer, ForeignKey("strive_question_set.id"), nullable=False),
    )
    student_pid: int = Field(
        sa_column=Column(Integer, ForeignKey("user.pid"), nullable=False),
    )
    submitted_answers: Any = Field(sa_column=Column(JSONB, nullable=False))
    correct_count: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    score: float | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    feedback: str | None = Field(default=None)
    weak_topics: Any | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    status: str = Field(default="pending", sa_column=Column(String, nullable=False))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        default=None,
    )


# Compatibility shim: some repository code expects `QuizSubmission`, `QuizQuestion`,
# and `QuizAnswer` symbols. Provide minimal table-backed models for those names
# and alias `QuizSubmission` to the primary `StriveSubmission` table.
class QuizQuestion(SQLModel, table=True):
    __tablename__ = "quiz_question"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    strive_submission_id: int = Field(
        sa_column=Column(Integer, ForeignKey("strive_submission.id"), nullable=False),
    )
    payload: Any = Field(sa_column=Column(JSONB, nullable=False))


class QuizAnswer(SQLModel, table=True):
    __tablename__ = "quiz_answer"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    strive_submission_id: int = Field(
        sa_column=Column(Integer, ForeignKey("strive_submission.id"), nullable=False),
    )
    question_id: int = Field(sa_column=Column(Integer, nullable=False))
    selected_choice: Any = Field(sa_column=Column(JSONB, nullable=True))


QuizSubmission = StriveSubmission

