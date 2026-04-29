"""Persistence helpers for uploaded Strive source files."""

from learnwithai.tables.strive import StriveSource
from sqlmodel import select

from .base_repository import BaseRepository


class StriveSourceRepository(BaseRepository[StriveSource, int]):
    """Provides CRUD and lookup operations for uploaded source material."""

    @property
    def model_type(self) -> type[StriveSource]:
        """Returns the SQLModel class managed by this repository."""
        return StriveSource

    def create_source(self, source: StriveSource) -> StriveSource:
        """Persists a newly uploaded source file."""
        return self.create(source)

    def list_by_student_and_activity(self, student_pid: int, activity_id: int) -> list[StriveSource]:
        """Returns uploaded sources for a user/activity pair, newest first."""
        stmt = (
            select(StriveSource)
            .where(StriveSource.student_pid == student_pid)
            .where(StriveSource.activity_id == activity_id)
            .order_by(StriveSource.created_at.desc())  # type: ignore[union-attr]
        )
        return list(self._session.exec(stmt).all())

    def list_by_student(self, student_pid: int) -> list[StriveSource]:
        """Returns all uploaded sources for a user, newest first."""
        stmt = (
            select(StriveSource).where(StriveSource.student_pid == student_pid).order_by(StriveSource.created_at.desc())  # type: ignore[union-attr]
        )
        return list(self._session.exec(stmt).all())
