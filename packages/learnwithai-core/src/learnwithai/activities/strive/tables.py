from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.types import JSON
from sqlmodel import Field, Relationship, SQLModel

from ...tables.submission import Submission


class StriveActivity(SQLModel, table=True):
    __tablename__: str = "strive_activity"

    id: int | None = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    activity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("activity.id"), unique=True, nullable=False)
    )
    module_name: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    topic: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


class StriveSubmission(SQLModel, table=True):
    __tablename__: str = "strive_submission"

    id: int | None = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    submission_id: int = Field(
        sa_column=Column(Integer, ForeignKey("submission.id"), unique=True, nullable=False)
    )
    mode: str = Field(default="daily", sa_column=Column(Text, nullable=False))
    module_name: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    topic: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    question_count: int = Field(default=5, sa_column=Column(Integer, nullable=False))
    questions: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
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
