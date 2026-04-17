from __future__ import annotations
from typing import List
from uuid import UUID

from learnwithai.tables.strive import QuizSubmission
from learnwithai.repositories.strive_repository import StriveRepository
from learnwithai.tables.activity import Activity
from learnwithai.tables.user import User


class StriveService:
    """Core domain service for Strive quiz flows.

    Public methods are minimal and follow repository-driven persistence.
    """

    def __init__(self, strive_repo: StriveRepository):
        self.strive_repo = strive_repo

    def start_quiz(self, subject: User, activity: Activity) -> QuizSubmission:
        """Create a QuizSubmission and persist initial questions.

        Minimal implementation lives here; real logic added later.
        """
        raise NotImplementedError()

    def get_quiz(self, subject: User, submission_id: UUID) -> QuizSubmission:
        """Load submission with questions and validate access."""
        raise NotImplementedError()

    def submit_quiz(self, subject: User, submission_id: UUID, answers: List[dict]) -> dict:
        """Grade provided answers, persist QuizAnswer rows, and return result DTO."""
        raise NotImplementedError()
