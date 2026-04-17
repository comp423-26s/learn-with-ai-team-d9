from __future__ import annotations
from typing import List, Optional
from uuid import UUID

from sqlmodel import Session

from learnwithai.repositories.base_repository import BaseRepository
from learnwithai.tables.strive import QuizSubmission, QuizQuestion, QuizAnswer


class StriveRepository(BaseRepository[QuizSubmission, UUID]):
    """Repository for quiz submissions and related objects."""

    def create_submission(self, submission: QuizSubmission) -> QuizSubmission:
        return self.create(submission)

    def get_submission_with_questions(self, submission_id: UUID) -> Optional[QuizSubmission]:
        # Use BaseRepository.get_by_id for now; callers can eager-load if needed
        return self.get_by_id(submission_id)

    def add_questions(self, submission_id: UUID, questions: List[QuizQuestion]) -> None:
        for q in questions:
            self.session.add(q)
        self.session.flush()

    def bulk_create_answers(self, answers: List[QuizAnswer]) -> None:
        for a in answers:
            self.session.add(a)
        self.session.flush()

    def update_submission(self, submission: QuizSubmission) -> QuizSubmission:
        return self.update(submission)
