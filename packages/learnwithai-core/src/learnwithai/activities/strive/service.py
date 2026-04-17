"""Business logic for Strive quizzes (start, fetch questions, submit)."""

from datetime import datetime, timezone
from typing import Any

from ...errors import AuthorizationError
from ...repositories.activity_repository import ActivityRepository
from ...repositories.membership_repository import MembershipRepository
from ...repositories.submission_repository import SubmissionRepository
from ...tables.activity import Activity, ActivityType
from ...tables.submission import Submission
from .repository import StriveSubmissionRepository, StriveActivityRepository


class StriveService:
    """Orchestrates quiz creation and grading for Strive activities.

    This implementation focuses on `start_quiz` for Sprint 1. Other methods
    are present as placeholders to be implemented later.
    """

    def __init__(
        self,
        activity_repo: ActivityRepository,
        strive_activity_repo: StriveActivityRepository,
        submission_repo: SubmissionRepository,
        strive_submission_repo: StriveSubmissionRepository,
        membership_repo: MembershipRepository,
    ):
        self._activity_repo = activity_repo
        self._strive_activity_repo = strive_activity_repo
        self._submission_repo = submission_repo
        self._strive_submission_repo = strive_submission_repo
        self._membership_repo = membership_repo

    def start_quiz(self, subject: Any, activity_id: int, request: Any) -> dict:
        """Start a new quiz submission and return a summary dict matching the API schema.

        Args:
            subject: Authenticated `User` object. Must have `pid` attribute.
            activity_id: Base activity id the quiz belongs to.
            request: Object with `mode`, optional `module_name`, `topic`, and `question_count`.

        Returns:
            A dict shaped like the API `QuizCreateResponse`.

        Raises:
            AuthorizationError: If the subject is not a member of the activity's course.
            ValueError: If the activity is missing or not a Strive activity.
        """
        activity = self._activity_repo.get_by_id(activity_id)
        if activity is None:
            raise ValueError("Activity not found")
        if activity.type != ActivityType.STRIVE:
            raise ValueError("Activity is not a Strive activity")

        # membership check (students and staff may create preview submissions)
        membership = self._membership_repo.get_by_user_and_course_ids(subject.pid, activity.course_id)
        if membership is None:
            raise AuthorizationError("Not a member of this course")

        # Deactivate prior active submission for this student/activity
        self._submission_repo.deactivate_active(activity.id, subject.pid)

        now = datetime.now(timezone.utc)

        # Create base submission
        submission = Submission(
            activity_id=activity.id,
            student_pid=subject.pid,
            is_active=True,
            submitted_at=now,
        )
        submission = self._submission_repo.create(submission)
        assert submission.id is not None

        # Generate simple placeholder questions for MVP
        qcount = int(getattr(request, "question_count", 5))
        mode = getattr(request, "mode", "daily")
        module_name = getattr(request, "module_name", None)
        topic = getattr(request, "topic", None)

        questions: list[dict] = []
        for i in range(1, qcount + 1):
            # local question id within submission
            q = {
                "question_id": i,
                "text": f"Placeholder question {i}: practice {topic or module_name or 'concepts'}.",
                "choices": [
                    {"id": 1, "text": "Option A"},
                    {"id": 2, "text": "Option B"},
                    {"id": 3, "text": "Option C"},
                    {"id": 4, "text": "Option D"},
                ],
                # store correct answer for grading later
                "correct_choice_id": 2,
            }
            questions.append(q)

        # Persist Strive-specific submission detail
        strive_detail = self._strive_submission_repo.create(
            self._strive_submission_repo.model_type(
                submission_id=submission.id,
                mode=mode,
                module_name=module_name,
                topic=topic,
                question_count=qcount,
                questions=questions,
            )
        )

        # Update submission max points
        submission.max_points = float(qcount)
        self._submission_repo.update(submission)

        return {
            "id": submission.id,
            "activity_id": activity.id,
            "student_pid": subject.pid,
            "status": "in_progress",
            "started_at": now,
            "question_count": qcount,
            "mode": mode,
            "module_name": module_name,
            "topic": topic,
        }

    def get_quiz(self, subject: Any, submission_id: int) -> dict:
        raise NotImplementedError()

    def submit_quiz(self, subject: Any, submission_id: int, answers: list[dict]) -> dict:
        raise NotImplementedError()
