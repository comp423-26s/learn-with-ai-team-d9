from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from learnwithai.repositories.base_repository import BaseRepository
from learnwithai.tables.strive import QuizAnswer, QuizQuestion, QuizSubmission


class StriveRepository(BaseRepository[QuizSubmission, int]):
    """Repository for quiz submissions and related objects."""

    @property
    def model_type(self) -> type[QuizSubmission]:
        return QuizSubmission

    def create_submission(self, submission: QuizSubmission) -> QuizSubmission:
        return self.create(submission)

    def get_submission_with_questions(self, submission_id: UUID) -> Optional[QuizSubmission]:
        # Use BaseRepository.get_by_id for now; callers can eager-load if needed
        return self.get_by_id(submission_id)

    def add_questions(self, submission_id: UUID, questions: List[QuizQuestion]) -> None:
        for q in questions:
            self._session.add(q)
        self._session.flush()

    def bulk_create_answers(self, answers: List[QuizAnswer]) -> None:
        for a in answers:
            self._session.add(a)
        self._session.flush()

    def update_submission(self, submission: QuizSubmission) -> QuizSubmission:
        return self.update(submission)
