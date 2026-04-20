from __future__ import annotations

from typing import Any, List, Optional

from learnwithai.repositories.base_repository import BaseRepository
from learnwithai.tables.activity import Activity, ActivityType
from learnwithai.tables.strive import QuizAnswer, QuizQuestion, QuizSubmission
from learnwithai.tables.submission import Submission
from learnwithai.tables.user import User
from sqlalchemy import func
from sqlmodel import select


class StriveRepository(BaseRepository[QuizSubmission, int]):
    """Repository for quiz submissions and related objects."""

    @property
    def model_type(self) -> type[QuizSubmission]:
        return QuizSubmission

    def create_submission(self, submission: QuizSubmission) -> QuizSubmission:
        return self.create(submission)

    def get_submission_with_questions(self, submission_id: int) -> Optional[QuizSubmission]:
        # Use BaseRepository.get_by_id for now; callers can eager-load if needed
        return self.get_by_id(submission_id)

    def add_questions(self, submission_id: int, questions: List[QuizQuestion]) -> None:
        for q in questions:
            self._session.add(q)
        self._session.flush()

    def bulk_create_answers(self, answers: List[QuizAnswer]) -> None:
        for a in answers:
            self._session.add(a)
        self._session.flush()

    def update_submission(self, submission: QuizSubmission) -> QuizSubmission:
        return self.update(submission)

    def get_leaderboard_stats(self, course_id: int) -> list[dict[str, Any]]:
        """Aggregate total scores and attempt counts for a course.

        Args:
            course_id: The course identifier to scope the leaderboard.

        Returns:
            A list of dicts containing user metadata, total score, and attempt count.
        """
        stmt = (
            select(
                User.pid,
                User.onyen,
                User.name,
                func.sum(QuizSubmission.score).label("total_score"),
                func.count(QuizSubmission.id).label("attempt_count"),
            )
            .join(Submission, Submission.id == QuizSubmission.submission_id)
            .join(Activity, Activity.id == Submission.activity_id)
            .join(User, User.pid == QuizSubmission.student_pid)
            .where(
                Activity.course_id == course_id,
                Activity.type == ActivityType.STRIVE,
                QuizSubmission.score.is_not(None),
            )
            .group_by(User.pid, User.onyen, User.name)
            .order_by(func.sum(QuizSubmission.score).desc())
        )

        rows = self._session.exec(stmt).all()
        results: list[dict[str, Any]] = []
        for row in rows:
            total_score = float(row.total_score or 0.0)
            attempt_count = int(row.attempt_count or 0)
            results.append(
                {
                    "user_pid": int(row.pid),
                    "username": row.onyen or row.name,
                    "total_score": total_score,
                    "attempt_count": attempt_count,
                }
            )
        return results
