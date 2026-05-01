from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from itertools import count
from typing import Any, List

from learnwithai.config import Settings, get_settings
from learnwithai.repositories.strive_source_repository import StriveSourceRepository
from learnwithai.tables.activity import Activity
from learnwithai.tables.strive import StriveSource
from learnwithai.tables.user import User
from openai import OpenAI
from PyPDF2 import PdfReader

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

    def __init__(
        self,
        quiz_repo: object | None = None,
        source_repo: StriveSourceRepository | None = None,
        settings: Settings | None = None,
        **_kwargs: object,
    ) -> None:
        self.quiz_repo = quiz_repo
        self.source_repo = source_repo
        self.settings = settings or get_settings()
        self.client = OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=f"{self.settings.openai_endpoint.rstrip('/')}/openai/v1/",
            timeout=20.0,
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
        """Build a concise prompt grounded in database-backed source content."""
        return (
            f"Generate exactly {qcount} beginner-level Python multiple-choice questions for students.\n"
            "Base questions and answers only on the SOURCE DOCUMENTS retrieved from the database-backed\n"
            "Strive source store below. Do not rely on filesystem paths or attempt to fetch files yourself.\n"
            "If multiple sources are present, combine them consistently and do not contradict the stored text.\n"
            "Each question must have exactly 4 answer choices and one correct answer.\n"
            "Keep explanations brief (one sentence).\n"
            "Return ONLY valid JSON as an array with schema: "
            '[{"question":"string","choices":["string","string","string","string"],"correct_choice_index":0,"explanation":"string"}]\n'
            "DATABASE SOURCE DOCUMENTS:\n"
            f"{source_excerpt}"
        )

    def _build_source_context_from_sources(self, sources: list[StriveSource]) -> str:
        """Load persisted source uploads into promptable JSON."""
        if self.source_repo is None:
            raise RuntimeError("StriveSourceRepository not configured.")

        database_sources: list[dict[str, Any]] = []

        for source in sources:
            study_material = self.extract_study_material_from_pdf(source.pdf_bytes)
            database_sources.append(
                {
                    "source_id": source.id,
                    "filename": source.filename,
                    "content_type": source.content_type,
                    "created_at": source.created_at.isoformat() if source.created_at is not None else None,
                    "study_material": study_material,
                }
            )

        if not database_sources:
            raise ValueError("No persisted source context is available for this activity.")

        return json.dumps(
            {
                "retrieved_from": "database-backed_strive_source_store",
                "sources": database_sources,
            },
            sort_keys=True,
        )

    def list_uploaded_sources(self, subject: User) -> list[dict[str, Any]]:
        """Return persisted source summaries for the current student."""
        if self.source_repo is None:
            raise RuntimeError("StriveSourceRepository not configured.")

        sources = self.source_repo.list_by_student(subject.pid)
        return [
            {
                "source_id": source.id,
                "activity_id": source.activity_id,
                "filename": source.filename,
                "content_type": source.content_type,
                "created_at": source.created_at,
            }
            for source in sources
        ]

    def _store_uploaded_source(
        self,
        subject: User,
        activity: Activity,
        pdf_bytes: bytes,
        *,
        source_filename: str | None,
        source_content_type: str,
    ) -> StriveSource:
        """Persist an uploaded source and return the database row."""
        if self.source_repo is None:
            raise RuntimeError("StriveSourceRepository not configured.")

        assert activity.id is not None, "Activity must be persisted before uploading a source"
        source = StriveSource(
            student_pid=subject.pid,
            activity_id=activity.id,
            filename=source_filename,
            content_type=source_content_type,
            pdf_bytes=pdf_bytes,
        )
        return self.source_repo.create_source(source)

    def extract_study_material_from_pdf(self, pdf_bytes: bytes, max_chars: int = 12000) -> dict[str, Any]:
        """Extract PDF content into a JSON-serializable study material payload.

        Args:
            pdf_bytes: Raw bytes for the uploaded PDF.
            max_chars: Maximum combined text length to keep in the payload.

        Returns:
            A JSON-serializable dictionary containing PDF metadata and page text.

        Raises:
            ValueError: If the PDF cannot be read or contains no extractable text.
        """
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
        except Exception as exc:
            raise ValueError("Could not read PDF.") from exc

        metadata: dict[str, str] = {}
        for raw_key, raw_value in (reader.metadata or {}).items():
            key = str(raw_key).lstrip("/")
            value = "" if raw_value is None else " ".join(str(raw_value).split())
            metadata[key] = value

        pages: list[dict[str, Any]] = []
        text_parts: list[str] = []
        remaining_chars = max_chars

        for page_number, page in enumerate(reader.pages, start=1):
            page_text = " ".join((page.extract_text() or "").split())
            if page_text and remaining_chars > 0:
                page_text = page_text[:remaining_chars]
                remaining_chars -= len(page_text)
                text_parts.append(page_text)
            else:
                page_text = ""
            pages.append({"page": page_number, "text": page_text})

        text = " ".join(text_parts).strip()
        if not text:
            raise ValueError("Could not extract readable text from PDF.")

        return {
            "schema_version": 1,
            "source_type": "pdf",
            "page_count": len(reader.pages),
            "metadata": metadata,
            "pages": pages,
            "text": text,
        }

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
        self,
        subject: User,
        activity: Activity,
        pdf_bytes: bytes,
        question_count: int = 5,
        *,
        source_filename: str | None = None,
        source_content_type: str = "application/pdf",
    ) -> dict[str, Any]:
        """Save uploaded PDF and generate a quiz synchronously from it.

        The uploaded source is stored in the database so the user can revisit
        it later, and the generated quiz still uses the in-memory store for
        the existing quiz flow.
        """
        source = self._store_uploaded_source(
            subject,
            activity,
            pdf_bytes,
            source_filename=source_filename,
            source_content_type=source_content_type,
        )

        source_excerpt = self._build_source_context_from_sources([source])

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
                "source_id": source.id,
            },
            "questions": questions,
        }

        # Return the public-facing quiz shape (strip correct answers)
        public_questions = [
            {"question_id": q["question_id"], "text": q["text"], "choices": q["choices"]} for q in questions
        ]

        return {**_QUIZ_STORE[submission_id]["submission"], "questions": public_questions}

    def generate_quiz_from_source(self, subject: User, source_id: int, question_count: int = 5) -> dict[str, Any]:
        """Generate a quiz from a previously stored source."""
        if self.source_repo is None:
            raise RuntimeError("StriveSourceRepository not configured.")

        source = self.source_repo.get_by_id(source_id)
        if source is None:
            raise KeyError("source not found")

        if source.student_pid != subject.pid:
            raise PermissionError("not allowed")

        source_excerpt = self._build_source_context_from_sources([source])

        try:
            questions = self._generate_questions_with_llm(qcount=question_count, source_excerpt=source_excerpt)
        except Exception:
            questions = []
            for i in range(1, question_count + 1):
                questions.append(
                    {
                        "question_id": i,
                        "text": f"Sample question {i} (saved source)",
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
                "activity_id": source.activity_id,
                "student_pid": subject.pid,
                "status": "in_progress",
                "started_at": started_at,
                "question_count": question_count,
                "mode": "module",
                "module_name": None,
                "topic": None,
                "source_id": source.id,
            },
            "questions": questions,
        }

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
