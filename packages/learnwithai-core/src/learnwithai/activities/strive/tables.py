"""Database-backed tables for the Strive activity type.

Minimal tables to support quiz submission storage for the Strive activity.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.types import JSON
from sqlmodel import Field, Relationship, SQLModel

from ...tables.submission import Submission  # noqa: F401 — registered for relationships


class StriveActivity(SQLModel, table=True):
    """Stores Strive-specific activity configuration linked to Activity."""

    __tablename__: str = "strive_activity"

    id: int | None = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    activity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("activity.id"), unique=True, nullable=False)
    )
    # Optional human-readable settings for the activity
    module_name: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    topic: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


class StriveSubmission(SQLModel, table=True):
    """Stores Strive quiz instance details associated with a base Submission.

    The `questions` column stores a list of question objects including correct
    answers and metadata; the API omits correct answers when returning questions
    to students.
    """

    __tablename__: str = "strive_submission"

    id: int | None = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    submission_id: int = Field(
        sa_column=Column(Integer, ForeignKey("submission.id"), unique=True, nullable=False)
    )
    mode: str = Field(default="daily", sa_column=Column(Text, nullable=False))
    module_name: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    topic: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    question_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    questions: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default="now()", nullable=False),
        default=None,
    )

    submission: Optional["Submission"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "StriveSubmission.submission_id == Submission.id",
            "foreign_keys": "[StriveSubmission.submission_id]",
            "lazy": "select",
            "viewonly": True,
            "uselist": False,
        }
    )
