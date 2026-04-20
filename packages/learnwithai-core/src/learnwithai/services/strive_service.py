from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
from typing import Any, List

from ..repositories.strive_repository import StriveRepository
from ..tables.activity import Activity
from ..tables.user import User

# Simple in-memory store for dev/testing so the endpoints work without DB migrations.
_NEXT_ID = count(1)
_QUIZ_STORE: dict[int, dict[str, Any]] = {}


@dataclass
class _QuizHandle:
    id: int
    activity_id: int | None
    student_pid: int
    status: str
    started_at: datetime
    question_count: int
    mode: str | None = None
    module_name: str | None = None
    topic: str | None = None


class StriveService:
    """Lightweight dev implementation of Strive flows (in-memory).

    This implementation exists solely to allow frontend/API GUI testing
    without creating DB migrations. It is intentionally simple and not
    suitable for production.
    """

    def __init__(self, strive_repo: StriveRepository | None = None) -> None:
        """Initialize the Strive service.

        Args:
            strive_repo: Repository used for persistent Strive data.
        """
        self._strive_repo = strive_repo

    def start_quiz(self, subject: User, activity: Activity, options: Any | None = None) -> _QuizHandle:
        """Create an in-memory quiz and return a lightweight handle.

        `options` is expected to have attributes similar to the API request
        (question_count, mode, module_name, topic).
        """
        qcount = getattr(options, "question_count", 5) if options is not None else 5
        mode = getattr(options, "mode", "daily") if options is not None else "daily"
        module_name = getattr(options, "module_name", None) if options is not None else None
        topic = getattr(options, "topic", None) if options is not None else None

        submission_id = next(_NEXT_ID)
        started_at = datetime.now(timezone.utc)

        # Build simple questions with deterministic correct_choice_id
        questions: List[dict] = []
        for i in range(1, qcount + 1):
            choices = [
                {"id": 1, "text": "Option A"},
                {"id": 2, "text": "Option B"},
                {"id": 3, "text": "Option C"},
                {"id": 4, "text": "Option D"},
            ]
            questions.append(
                {
                    "question_id": i,
                    "text": f"Sample question {i}",
                    "choices": choices,
                    "correct_choice_id": 1,
                    "explanation": "Because it's the sample answer.",
                }
            )

        _QUIZ_STORE[submission_id] = {
            "submission": {
                "id": submission_id,
                "activity_id": activity.id,
                "course_id": getattr(activity, "course_id", None),
                "student_pid": subject.pid,
                "status": "in_progress",
                "started_at": started_at,
                "question_count": qcount,
                "mode": mode,
                "module_name": module_name,
                "topic": topic,
            },
            "questions": questions,
        }

        h = _QuizHandle(
            id=submission_id,
            activity_id=activity.id,
            student_pid=subject.pid,
            status="in_progress",
            started_at=started_at,
            question_count=qcount,
            mode=mode,
            module_name=module_name,
            topic=topic,
        )
        return h

    def get_quiz(self, subject: User, submission_id: int) -> dict[str, Any]:
        data = _QUIZ_STORE.get(int(submission_id))
        if data is None:
            raise KeyError("quiz not found")
        # strip correct answers from the questions when returning
        questions = []
        for q in data["questions"]:
            questions.append(
                {
                    "question_id": q["question_id"],
                    "text": q["text"],
                    "choices": q["choices"],
                }
            )
        resp = {**data["submission"], "questions": questions}
        return resp

    def submit_quiz(self, subject: User, submission_id: int, answers: List[dict]) -> dict[str, Any]:
        data = _QUIZ_STORE.get(int(submission_id))
        if data is None:
            raise KeyError("quiz not found")

        questions = data["questions"]
        # build a map of correct answers
        correct_map = {q["question_id"]: q["correct_choice_id"] for q in questions}
        feedback = []
        correct_count = 0
        for a in answers:
            if isinstance(a, dict):
                qid = int(a["question_id"])
                selected = int(a["selected_choice_id"])
            else:
                # Pydantic model objects may be passed; read attributes
                qid = int(getattr(a, "question_id"))
                selected = int(getattr(a, "selected_choice_id"))
            correct = correct_map.get(qid) == selected
            if correct:
                correct_count += 1
            feedback.append(
                {
                    "question_id": qid,
                    "correct": correct,
                    "correct_choice_id": correct_map.get(qid),
                    "explanation": "Because it's the sample answer.",
                }
            )

        total = len(questions)
        score = (correct_count / total) * 100.0 if total > 0 else 0.0
        finished_at = datetime.now(timezone.utc)

        # update store
        results = {
            "id": submission_id,
            "score": score,
            "correct_count": correct_count,
            "total_count": total,
            "feedback": feedback,
            "finished_at": finished_at,
            "feedback_summary": "Summary feedback is not yet available.",
        }

        data["submission"].update({"status": "submitted", "finished_at": finished_at})
        data["results"] = results

        return results

    def get_results(self, subject: User, submission_id: int) -> dict[str, Any]:
        data = _QUIZ_STORE.get(int(submission_id))
        if data is None:
            raise KeyError("quiz not found")
        results = data.get("results")
        if results is None:
            raise KeyError("quiz results not found")
        return results

    def get_submission_course_id(self, subject: User, submission_id: int) -> int:
        data = _QUIZ_STORE.get(int(submission_id))
        if data is None:
            raise KeyError("quiz not found")
        submission = data.get("submission")
        if submission is None or submission.get("course_id") is None:
            raise KeyError("quiz course not found")
        return int(submission["course_id"])

    def get_leaderboard(self, subject: User, course_id: int, limit: int = 10) -> dict[str, Any]:
        updated_at = datetime.now(timezone.utc)
        if self._strive_repo is None:
            return {
                "course_id": course_id,
                "updated_at": updated_at,
                "entries": [],
                "current_user": None,
            }

        stats = self._strive_repo.get_leaderboard_stats(course_id)
        ranked_entries: list[dict[str, Any]] = []
        for index, entry in enumerate(stats, start=1):
            total_score = float(entry["total_score"])
            attempt_count = int(entry["attempt_count"])
            percentage = (total_score / (attempt_count * 100.0)) if attempt_count > 0 else 0.0
            ranked_entries.append(
                {
                    "rank": index,
                    "user_pid": entry["user_pid"],
                    "username": entry["username"],
                    "score": total_score,
                    "accuracy": percentage,
                }
            )

        limited_entries = ranked_entries[: max(limit, 0)]
        current_user = next((e for e in ranked_entries if e["user_pid"] == subject.pid), None)

        return {
            "course_id": course_id,
            "updated_at": updated_at,
            "entries": limited_entries,
            "current_user": current_user,
        }

    def get_leaderboard_rank_snapshot(self, subject: User, course_id: int) -> dict[str, Any] | None:
        """Return the current user's leaderboard snapshot for a course.

        Args:
            subject: Authenticated user requesting the snapshot.
            course_id: Course identifier for the leaderboard.

        Returns:
            A dict containing rank, score, accuracy, and attempt_count when available.
        """
        if self._strive_repo is None:
            return None

        stats = self._strive_repo.get_leaderboard_stats(course_id)
        for index, entry in enumerate(stats, start=1):
            if entry["user_pid"] != subject.pid:
                continue
            total_score = float(entry["total_score"])
            attempt_count = int(entry["attempt_count"])
            accuracy = (total_score / (attempt_count * 100.0)) if attempt_count > 0 else 0.0
            return {
                "rank": index,
                "score": total_score,
                "accuracy": accuracy,
                "attempt_count": attempt_count,
            }

        return None
