from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
from typing import Any, List

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
    question_map = {q["question_id"]: q for q in questions}
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

        question_match = question_map.get(qid)
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

    def _build_llm_prompt(self, qcount: int) -> str:
        return (
            f"Generate exactly {qcount} beginner-level Python multiple-choice questions for students.\n"
            "Focus on basic Python concepts such as variables, data types, lists, dictionaries, "
            "conditionals, loops, functions, and simple input/output.\n"
            "Each question must have exactly 4 answer choices.\n"
            "Keep each explanation brief and beginner-friendly (one sentence).\n"
            "Avoid trick questions and advanced topics.\n"
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

    def _build_source_aware_llm_prompt(self, qcount: int, source_excerpt: str) -> str:
        """Build a concise prompt grounded in uploaded source content."""
        return (
            f"Generate exactly {qcount} beginner-level Python multiple-choice questions for students.\n"
            "Base questions and answers on the SOURCE CONTENT below.\n"
            "If needed, infer simple context but do not contradict the source.\n"
            "Each question must have exactly 4 answer choices and one correct answer.\n"
            "Keep explanations brief (one sentence).\n"
            "Return ONLY valid JSON as an array with schema: "
            '[{"question":"string","choices":["string","string","string","string"],"correct_choice_index":0,"explanation":"string"}]\n'
            "SOURCE CONTENT:\n"
            f"{source_excerpt}"
        )

    def _extract_text_from_pdf_bytes(self, pdf_bytes: bytes, max_chars: int = 3000) -> str:
        """Extract a best-effort text snippet from PDF bytes without external dependencies."""
        decoded = pdf_bytes.decode("latin-1", errors="ignore")
        streams = re.findall(r"stream\r?\n(.*?)\r?\nendstream", decoded, flags=re.DOTALL)

        chunks: list[str] = []
        for stream in streams:
            # Heuristic extraction of literal text fragments commonly used in PDF content streams.
            chunks.extend(re.findall(r"\(([^()]*)\)\s*T[Jj]", stream))
            if len(" ".join(chunks)) >= max_chars:
                break

        text = " ".join(chunk.strip() for chunk in chunks if chunk.strip())
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return ""
        return text[:max_chars]

    def _generate_questions_with_llm(self, qcount: int, source_excerpt: str | None = None) -> List[dict]:
        """Generate quiz questions with the LLM and normalize them into app format."""
        prompt = (
            self._build_source_aware_llm_prompt(qcount=qcount, source_excerpt=source_excerpt)
            if source_excerpt
            else self._build_llm_prompt(qcount=qcount)
        )

        last_error: Exception | None = None

        for _ in range(2):
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful educational question generator that returns strict JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            content = response.choices[0].message.content or ""

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue

            if not isinstance(parsed, list) or len(parsed) < qcount:
                last_error = ValueError("Strive quiz generation returned too few questions.")
                continue

            questions: List[dict] = []

            for i, item in enumerate(parsed[:qcount], start=1):
                if not isinstance(item, dict):
                    raise ValueError("Strive quiz generation returned an invalid question payload.")

                raw_choices = item.get("choices", [])
                if not isinstance(raw_choices, list) or len(raw_choices) != 4:
                    raise ValueError("Strive quiz generation returned invalid choices.")

                correct_choice_index = item.get("correct_choice_index", 0)
                if not isinstance(correct_choice_index, int) or correct_choice_index not in range(4):
                    raise ValueError("Strive quiz generation returned an invalid correct choice index.")

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

        raise ValueError("Strive quiz generation returned invalid JSON content.") from last_error

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

        submission_id = next(_NEXT_ID)
        started_at = datetime.now(timezone.utc)

        questions = self._generate_questions_with_llm(qcount=qcount)

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

    def generate_quiz_from_pdf(
        self, subject: User, activity: Activity, pdf_bytes: bytes, question_count: int = 5
    ) -> dict[str, Any]:
        """Save uploaded PDF and generate a quiz synchronously from it.

        This is a lightweight dev implementation: it persist the uploaded
        file to `data/uploads/strive/` with a UUID filename and then
        generates questions using the existing LLM helper. It stores the
        submission and questions in the in-memory `_QUIZ_STORE` so other
        endpoints (GET/submit) continue to work.
        """
        # Persist upload
        uploads_dir = os.path.join("data", "uploads", "strive")
        os.makedirs(uploads_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.pdf"
        path = os.path.join(uploads_dir, filename)
        with open(path, "wb") as fh:
            fh.write(pdf_bytes)

        source_excerpt = self._extract_text_from_pdf_bytes(pdf_bytes)

        # Try to generate questions using the existing LLM helper. If the
        # environment is not configured for OpenAI (no API key or network),
        # fall back to a simple deterministic placeholder set so the API
        # remains usable in dev environments.
        try:
            questions = self._generate_questions_with_llm(qcount=question_count, source_excerpt=source_excerpt)
        except Exception:
            questions = []
            for i in range(1, question_count + 1):
                questions.append(
                    {
                        "question_id": i,
                        "text": f"Sample question {i} (PDF source)",
                        "choices": [
                            {"id": 1, "text": "Choice A"},
                            {"id": 2, "text": "Choice B"},
                            {"id": 3, "text": "Choice C"},
                            {"id": 4, "text": "Choice D"},
                        ],
                        "correct_choice_id": 1,
                        "explanation": "Placeholder explanation.",
                    }
                )

        submission_id = next(_NEXT_ID)
        started_at = datetime.now(timezone.utc)

        _QUIZ_STORE[submission_id] = {
            "submission": {
                "id": submission_id,
                "activity_id": activity.id,
                "student_pid": subject.pid,
                "status": "in_progress",
                "started_at": started_at,
                "question_count": question_count,
                "mode": "module",
                "module_name": None,
                "topic": None,
                "source_path": path,
            },
            "questions": questions,
        }

        # Return the public-facing quiz shape (strip correct answers)
        public_questions = [
            {"question_id": q["question_id"], "text": q["text"], "choices": q["choices"]} for q in questions
        ]

        return {**_QUIZ_STORE[submission_id]["submission"], "questions": public_questions}

    def get_quiz(self, subject: User, submission_id: int) -> dict[str, Any]:
        data = _QUIZ_STORE.get(int(submission_id))
        if data is None:
            raise KeyError("quiz not found")

        if data["submission"]["student_pid"] != subject.pid:
            raise PermissionError("not allowed")

        # Strip correct answers from the questions when returning.
        questions = []
        for q in data["questions"]:
            questions.append(
                {
                    "question_id": q["question_id"],
                    "text": q["text"],
                    "choices": q["choices"],
                }
            )

        return {**data["submission"], "questions": questions}

    def submit_quiz(self, subject: User, submission_id: int, answers: Any) -> dict[str, Any]:
        data = _QUIZ_STORE.get(int(submission_id))
        if data is None:
            raise KeyError("quiz not found")

        if data["submission"]["student_pid"] != subject.pid:
            raise PermissionError("not allowed")

        questions = data["questions"]
        mode = data["submission"].get("mode")

        result = grade_answers(questions, answers, mode=mode)
        score = result["score"]
        accuracy = result["accuracy"]
        correct_count = result["correct_count"]
        total = result["total_count"]
        feedback = result["feedback"]
        finished_at = datetime.now(timezone.utc)

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
