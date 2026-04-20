from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
from typing import Any, List

from learnwithai.tables.activity import Activity
from learnwithai.tables.user import User

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

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        # Accept repository injection but do not require it for the dev shim
        return None

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
                "course_id": activity.course_id,
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
        leaderboard: dict[int, dict[str, Any]] = {}
        updated_at = datetime.now(timezone.utc)

        for data in _QUIZ_STORE.values():
            submission = data.get("submission")
            results = data.get("results")
            if submission is None or results is None:
                continue

            student_pid = int(submission.get("student_pid"))
            score = float(results.get("score", 0.0))
            correct_count = int(results.get("correct_count", 0))
            total_count = int(results.get("total_count", 0))
            accuracy = (correct_count / total_count) if total_count > 0 else 0.0

            existing = leaderboard.get(student_pid)
            if existing is None or score > existing["score"]:
                leaderboard[student_pid] = {
                    "user_pid": student_pid,
                    "username": f"student-{student_pid}",
                    "score": score,
                    "accuracy": accuracy,
                }

        entries = sorted(leaderboard.values(), key=lambda entry: entry["score"], reverse=True)
        ranked_entries = []
        for index, entry in enumerate(entries, start=1):
            ranked_entries.append({"rank": index, **entry})

        limited_entries = ranked_entries[: max(limit, 0)]
        current_user = next((e for e in ranked_entries if e["user_pid"] == subject.pid), None)

        return {
            "course_id": course_id,
            "updated_at": updated_at,
            "entries": limited_entries,
            "current_user": current_user,
        }
