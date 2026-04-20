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


def grade_answers(questions: List[dict], answers: Any, mode: str | None = None) -> dict[str, Any]:
    """Grade submitted answers against `questions`.

    Simple, unweighted scoring: percent correct.

    - `questions` is a list of dicts; each should include `question_id`
      and `correct_choice_id`.
    - `answers` is an iterable of dicts or objects with `question_id`
      and `selected_choice_id`.
    - `mode` is accepted for callers that need to distinguish
      (e.g. 'daily' vs 'module') but does not affect scoring here.

    Returns a dict with keys: `score`, `accuracy`, `correct_count`,
    `total_count`, and `feedback` (list per question).
    """
    correct_map = {q["question_id"]: q.get("correct_choice_id") for q in questions}

    feedback: List[dict] = []
    correct_count = 0

    for a in answers:
        if isinstance(a, dict):
            qid = int(a["question_id"])
            selected = int(a["selected_choice_id"])
        else:
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
            }
        )

    total = len(questions)
    score = (correct_count / total) * 100.0 if total > 0 else 0.0
    accuracy = score

    return {
        "score": score,
        "accuracy": accuracy,
        "correct_count": correct_count,
        "total_count": total,
        "feedback": feedback,
    }


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

    def submit_quiz(self, subject: User, submission_id: int, answers: Any) -> dict[str, Any]:
        data = _QUIZ_STORE.get(int(submission_id))
        if data is None:
            raise KeyError("quiz not found")
        questions = data["questions"]
        mode = data["submission"].get("mode")

        # Use grading helper
        result = grade_answers(questions, answers, mode=mode)
        score = result["score"]
        accuracy = result["accuracy"]
        correct_count = result["correct_count"]
        total = result["total_count"]
        feedback = result["feedback"]
        finished_at = datetime.now(timezone.utc)

        # update store
        data["submission"].update({"status": "submitted", "finished_at": finished_at})

        return {
            "id": submission_id,
            "score": score,
            "accuracy": accuracy,
            "correct_count": correct_count,
            "total_count": total,
            "feedback": feedback,
            "finished_at": finished_at,
        }
