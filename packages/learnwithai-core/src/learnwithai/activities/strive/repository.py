"""Persistence helpers for Strive activity and submission records."""

from sqlalchemy.orm import contains_eager, joinedload
from sqlmodel import col, select

from ...repositories.base_repository import BaseRepository
from ...tables.submission import Submission
from .tables import StriveActivity, StriveSubmission


class StriveActivityRepository(BaseRepository[StriveActivity, int]):
    @property
    def model_type(self) -> type[StriveActivity]:
        return StriveActivity

    def get_by_activity_id(self, activity_id: int) -> StriveActivity | None:
        stmt = select(StriveActivity).where(StriveActivity.activity_id == activity_id)
        return self._session.exec(stmt).first()


class StriveSubmissionRepository(BaseRepository[StriveSubmission, int]):
    @property
    def model_type(self) -> type[StriveSubmission]:
        return StriveSubmission

    def get_by_submission_id(self, submission_id: int) -> StriveSubmission | None:
        stmt = select(StriveSubmission).where(StriveSubmission.submission_id == submission_id)
        return self._session.exec(stmt).first()

    def list_active_for_activity(self, activity_id: int) -> list[StriveSubmission]:
        stmt = (
            select(StriveSubmission)
            .join(Submission, col(StriveSubmission.submission_id) == col(Submission.id))
            .options(
                contains_eager(StriveSubmission.submission),
                joinedload(StriveSubmission.submission),
            )
            .where(col(Submission.activity_id) == activity_id, col(Submission.is_active))
            .order_by(col(Submission.submitted_at).desc())
        )
        return list(self._session.exec(stmt).all())
