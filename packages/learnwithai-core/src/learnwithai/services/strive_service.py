from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
from typing import Any, List
from unittest.mock import Mock

from learnwithai.config import Settings, get_settings
from learnwithai.tables.activity import Activity
from learnwithai.tables.user import User
from openai import OpenAI

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


_MOCK_TOPIC_DB: dict[str, tuple[str, ...]] = {
    "Python": (
        "functions",
        "lists and dictionaries",
        "control flow",
        "exceptions",
        "file I/O",
    ),
    "Java": (
        "classes and objects",
        "interfaces",
        "collections framework",
        "exception handling",
        "streams",
    ),
    "C": (
        "pointers",
        "memory allocation",
        "structs",
        "file handling",
        "header files and compilation",
    ),
}


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

        # Pull explanation from the question itself so LLM-generated feedback is preserved
        question_match = next((q for q in questions if q["question_id"] == qid), None)
        explanation = question_match.get("explanation") if question_match else None

        feedback.append(
            {
                "question_id": qid,
                "correct": correct,
                "correct_choice_id": correct_map.get(qid),
                "explanation": explanation,
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

    def __init__(self, *_args: object, settings: Settings | None = None, **_kwargs: object) -> None:
        self.settings = settings or get_settings()
        self.client = OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=f"{self.settings.openai_endpoint.rstrip('/')}/openai/v1/",
        )

    def _select_language(self, module_name: str | None, topic: str | None) -> str:
        context = " ".join(part for part in [module_name, topic] if part).lower()
        if "python" in context:
            return "Python"
        if "java" in context:
            return "Java"
        if " c " in f" {context} " or "pointer" in context or "memory" in context or "struct" in context:
            return "C"
        return "Python"

    def _build_llm_prompt(
        self,
        *,
        qcount: int,
        topics: tuple[str, ...],
        module_name: str | None,
        topic: str | None,
    ) -> str:
        """Build the quiz-generation prompt with the requested learning context."""

        topic_list = ", ".join(topics)
        return (
            f"Generate {qcount} multiple-choice questions with 4 answer choices each. "
            "Focus on the learning objective, core concept, and common misconception for each question. "
            "Make the questions step-by-step and educational rather than trick questions.\n"
            f"Module: {module_name or 'none'}\n"
            f"Topic: {topic or 'none'}\n"
            f"Topics: {topic_list}\n"
            "Keep each explanation brief, but still step-by-step.\n"
            "Return ONLY valid JSON as an array with this schema:\n"
            "[\n"
            "  {\n"
            '    "question": "string",\n'
            '    "choices": ["string", "string", "string", "string"],\n'
            '    "correct_choice_index": 0,\n'
            '    "explanation": "string"\n'
            "  }\n"
            "]"
        )

    def _fallback_questions(self, qcount: int, topics: tuple[str, ...]) -> List[dict]:
        """Create deterministic sample questions when the LLM is unavailable."""

        questions: List[dict] = []
        topic_cycle = topics or ("general Python",)

        for index in range(1, qcount + 1):
            topic = topic_cycle[(index - 1) % len(topic_cycle)]
            questions.append(
                {
                    "question_id": index,
                    "text": f"Sample question {index}: Which statement best describes {topic}?",
                    "choices": [
                        {"id": 1, "text": f"It matches the core idea of {topic}."},
                        {"id": 2, "text": "It is unrelated to the concept."},
                        {"id": 3, "text": "It only matters for advanced debugging."},
                        {"id": 4, "text": "It is never useful in practice."},
                    ],
                    "correct_choice_id": 1,
                    "explanation": (
                        "Step 1: Identify the core idea being tested. "
                        f"Step 2: Compare the choices against {topic}. "
                        "Step 3: The first choice is the best supported answer because it directly matches the concept."
                    ),
                }
            )

        return questions

    def _generate_questions_with_llm(
        self, qcount: int, topics: tuple[str, ...], *, module_name: str | None, topic: str | None
    ) -> List[dict]:
        """Generate quiz questions with the LLM and normalize them into app format."""
        if not self.settings.openai_api_key or (self.settings.is_test and not isinstance(self.client, Mock)):
            return self._fallback_questions(qcount=qcount, topics=topics)

        prompt = self._build_llm_prompt(qcount=qcount, topics=topics, module_name=module_name, topic=topic)

        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[{"role": "system", "content": prompt}],
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
        except Exception:
            return self._fallback_questions(qcount=qcount, topics=topics)

        if not isinstance(parsed, list) or len(parsed) < qcount:
            return self._fallback_questions(qcount=qcount, topics=topics)

        questions: List[dict] = []

        for i, item in enumerate(parsed[:qcount], start=1):
            if not isinstance(item, dict):
                return self._fallback_questions(qcount=qcount, topics=topics)

            raw_choices = item.get("choices", [])
            if not isinstance(raw_choices, list) or len(raw_choices) != 4:
                return self._fallback_questions(qcount=qcount, topics=topics)

            correct_choice_index = item.get("correct_choice_index", 0)
            if not isinstance(correct_choice_index, int) or correct_choice_index not in range(4):
                return self._fallback_questions(qcount=qcount, topics=topics)

            choices = [{"id": idx + 1, "text": str(choice)} for idx, choice in enumerate(raw_choices)]

            questions.append(
                {
                    "question_id": i,
                    "text": str(item.get("question", f"Generated question {i}")),
                    "choices": choices,
                    "correct_choice_id": correct_choice_index + 1,
                    "explanation": str(
                        item.get(
                            "explanation",
                            (
                                "Step 1: Identify the relevant concept. "
                                "Step 2: Compare the options. "
                                "Step 3: Choose the best-supported answer."
                            ),
                        )
                    ),
                }
            )

        return questions

    def _find_reusable_submission(
        self,
        subject: User,
        activity: Activity,
        *,
        qcount: int,
        mode: str,
        module_name: str | None,
        topic: str | None,
    ) -> dict[str, Any] | None:
        """Find an existing quiz for this user/activity/options to avoid re-generating questions."""
        candidates: list[dict[str, Any]] = []

        for data in _QUIZ_STORE.values():
            submission = data.get("submission", {})
            if submission.get("student_pid") != subject.pid:
                continue
            if submission.get("activity_id") != activity.id:
                continue
            if submission.get("question_count") != qcount:
                continue
            if submission.get("mode") != mode:
                continue
            if submission.get("module_name") != module_name:
                continue
            if submission.get("topic") != topic:
                continue
            if submission.get("status") not in {"in_progress", "submitted"}:
                continue

            candidates.append(data)

        if not candidates:
            return None

        # Reuse the most recent matching submission.
        return max(candidates, key=lambda item: item["submission"]["started_at"])

    def start_quiz(self, subject: User, activity: Activity, options: Any | None = None) -> _QuizHandle:
        """Create an in-memory quiz and return a lightweight handle.

        `options` is expected to have attributes similar to the API request
        (question_count, mode, module_name, topic).
        """
        qcount = getattr(options, "question_count", 5) if options is not None else 5
        mode = getattr(options, "mode", "daily") if options is not None else "daily"
        module_name = getattr(options, "module_name", None) if options is not None else None
        topic = getattr(options, "topic", None) if options is not None else None

        reusable = self._find_reusable_submission(
            subject,
            activity,
            qcount=qcount,
            mode=mode,
            module_name=module_name,
            topic=topic,
        )
        if reusable is not None:
            existing = reusable["submission"]
            return _QuizHandle(
                id=existing["id"],
                activity_id=existing["activity_id"],
                student_pid=existing["student_pid"],
                status=existing["status"],
                started_at=existing["started_at"],
                question_count=existing["question_count"],
                mode=existing.get("mode"),
                module_name=existing.get("module_name"),
                topic=existing.get("topic"),
            )

        language = self._select_language(module_name=module_name, topic=topic)
        topics = _MOCK_TOPIC_DB[language]

        submission_id = next(_NEXT_ID)
        started_at = datetime.now(timezone.utc)

        questions = self._generate_questions_with_llm(
            qcount=qcount, topics=topics, module_name=module_name, topic=topic
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

        return _QuizHandle(
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
