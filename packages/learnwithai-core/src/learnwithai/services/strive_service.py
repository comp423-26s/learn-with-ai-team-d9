from __future__ import annotations

import json
import os
import re
import uuid
import zlib
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

    def extract_study_material_from_pdf(self, pdf_bytes: bytes) -> dict[str, Any]:
        """Extract reusable study material JSON from uploaded PDF bytes.

        The returned payload is intentionally quiz-agnostic. It captures the
        concepts, terms, facts, and examples that a later quiz generator can
        consume without re-reading the PDF.

        Args:
            pdf_bytes: Raw bytes for the uploaded PDF.

        Returns:
            A normalized study-material JSON payload.

        Raises:
            ValueError: If no text can be extracted or the LLM returns invalid
                structured content.
        """
        source_text = self._extract_text_from_pdf_bytes(pdf_bytes, max_chars=12000)
        if not source_text:
            raise ValueError("Could not extract readable text from PDF.")

        return self._extract_study_material_with_llm(source_text)

    def _build_study_material_extraction_prompt(self, source_text: str) -> str:
        """Build a prompt that turns source text into quiz-ready study JSON."""
        return (
            "Extract structured study material from the SOURCE CONTENT below.\n"
            "Only include information supported by the source. Do not invent facts.\n"
            "Write for beginner programming students.\n"
            "Return ONLY valid JSON as one object with this schema:\n"
            "{\n"
            '  "title": "short source title",\n'
            '  "summary": "2-4 sentence source summary",\n'
            '  "learning_objectives": ["objective students should be able to do"],\n'
            '  "key_terms": [{"term": "string", "definition": "string"}],\n'
            '  "concepts": [{"name": "string", "explanation": "string", "supporting_details": ["string"]}],\n'
            '  "facts": ["atomic fact useful for quiz generation"],\n'
            '  "examples": [{"prompt": "source-grounded example or scenario", "explanation": "string"}],\n'
            '  "misconceptions": [{"misconception": "string", "correction": "string"}]\n'
            "}\n"
            "Use empty arrays when a category is not present in the source.\n"
            "SOURCE CONTENT:\n"
            f"{source_text}"
        )

    def _extract_study_material_with_llm(self, source_text: str) -> dict[str, Any]:
        """Ask the LLM to produce and validate a study-material JSON object."""
        prompt = self._build_study_material_extraction_prompt(source_text)
        last_error: Exception | None = None

        for _ in range(2):
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You extract source-grounded educational study material and return strict JSON only."
                        ),
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

            try:
                return self._normalize_study_material_payload(parsed, source_text=source_text)
            except ValueError as exc:
                last_error = exc

        raise ValueError("Study material extraction returned invalid JSON content.") from last_error

    def _normalize_study_material_payload(self, payload: Any, *, source_text: str) -> dict[str, Any]:
        """Normalize LLM output into the study-material contract."""
        if not isinstance(payload, dict):
            raise ValueError("Study material extraction returned a non-object payload.")

        material = {
            "schema_version": 1,
            "title": self._clean_text(payload.get("title")) or "Uploaded study material",
            "summary": self._clean_text(payload.get("summary")),
            "learning_objectives": self._clean_text_list(payload.get("learning_objectives")),
            "key_terms": self._normalize_named_items(
                payload.get("key_terms"),
                name_key="term",
                text_key="definition",
            ),
            "concepts": self._normalize_concepts(payload.get("concepts")),
            "facts": self._clean_text_list(payload.get("facts")),
            "examples": self._normalize_named_items(
                payload.get("examples"),
                name_key="prompt",
                text_key="explanation",
            ),
            "misconceptions": self._normalize_named_items(
                payload.get("misconceptions"),
                name_key="misconception",
                text_key="correction",
            ),
            "source_excerpt": source_text[:1000],
        }

        if not material["summary"] and not material["concepts"] and not material["facts"]:
            raise ValueError("Study material extraction did not include usable study content.")

        return material

    def _clean_text(self, value: Any) -> str:
        """Return a whitespace-normalized string for scalar LLM output."""
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _clean_text_list(self, value: Any) -> list[str]:
        """Normalize a possibly malformed LLM list into a list of strings."""
        if not isinstance(value, list):
            return []

        cleaned: list[str] = []
        for item in value:
            text = self._clean_text(item)
            if text:
                cleaned.append(text)
        return cleaned

    def _normalize_named_items(self, value: Any, *, name_key: str, text_key: str) -> list[dict[str, str]]:
        """Normalize list items that contain a label plus explanatory text."""
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue

            name = self._clean_text(item.get(name_key))
            text = self._clean_text(item.get(text_key))
            if name and text:
                normalized.append({name_key: name, text_key: text})

        return normalized

    def _normalize_concepts(self, value: Any) -> list[dict[str, Any]]:
        """Normalize concept objects and their supporting details."""
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue

            name = self._clean_text(item.get("name"))
            explanation = self._clean_text(item.get("explanation"))
            supporting_details = self._clean_text_list(item.get("supporting_details"))
            if name and explanation:
                normalized.append(
                    {
                        "name": name,
                        "explanation": explanation,
                        "supporting_details": supporting_details,
                    }
                )

        return normalized

    def _extract_text_from_pdf_bytes(self, pdf_bytes: bytes, max_chars: int = 3000) -> str:
        """Extract a best-effort text snippet from PDF bytes without external dependencies."""
        streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, flags=re.DOTALL)
        chunks: list[str] = []

        # Try each raw stream and a best-effort decompressed variant when possible.
        for stream_bytes in streams:
            for candidate in self._stream_text_candidates(stream_bytes):
                chunks.extend(self._extract_pdf_text_fragments(candidate))
                if len(" ".join(chunks)) >= max_chars:
                    break
            if len(" ".join(chunks)) >= max_chars:
                break

        # Fallback: scan whole payload if no stream text was captured.
        if not chunks:
            decoded = pdf_bytes.decode("latin-1", errors="ignore")
            chunks.extend(self._extract_pdf_text_fragments(decoded))
            if not chunks:
                chunks.extend(self._extract_plaintext_fragments(decoded))

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

    def _stream_text_candidates(self, stream_bytes: bytes) -> list[str]:
        """Return decoded stream variants (raw and, when possible, Flate-decoded)."""
        candidates: list[str] = [stream_bytes.decode("latin-1", errors="ignore")]

        try:
            decompressed = zlib.decompress(stream_bytes)
        except Exception:
            decompressed = None

        if decompressed:
            candidates.append(decompressed.decode("latin-1", errors="ignore"))

        return candidates

    def _extract_pdf_text_fragments(self, content: str) -> list[str]:
        """Extract likely text-showing fragments from PDF content streams."""
        fragments: list[str] = []

        # Simple text-show operators: (text) Tj and (text) TJ
        for literal in re.findall(r"\(((?:\\.|[^\\()])*)\)\s*T[Jj]", content):
            fragments.append(self._unescape_pdf_literal(literal))

        # Text arrays: [ ... ] TJ can include strings and hex chunks.
        for array_content in re.findall(r"\[(.*?)\]\s*TJ", content, flags=re.DOTALL):
            for literal in re.findall(r"\(((?:\\.|[^\\()])*)\)", array_content):
                fragments.append(self._unescape_pdf_literal(literal))
            for hex_text in re.findall(r"<([0-9A-Fa-f\s]+)>", array_content):
                decoded_hex = self._decode_pdf_hex_text(hex_text)
                if decoded_hex:
                    fragments.append(decoded_hex)

        # Some PDFs emit direct hex text-showing tokens: <...> Tj / TJ
        for hex_text in re.findall(r"<([0-9A-Fa-f\s]+)>\s*T[Jj]", content):
            decoded_hex = self._decode_pdf_hex_text(hex_text)
            if decoded_hex:
                fragments.append(decoded_hex)

        return [f for f in (frag.strip() for frag in fragments) if f]

    def _extract_plaintext_fragments(self, content: str) -> list[str]:
        """Extract readable fallback text from PDF-like payloads used in tests/dev."""
        fragments: list[str] = []

        for line in content.splitlines():
            line = self._clean_text(line)
            if not line or line.startswith("%PDF-") or line.endswith(" obj") or line == "endobj":
                continue
            if len(line) < 20 and not re.search(r"[.!?]$", line):
                continue
            fragments.append(line)

        return fragments

    def _unescape_pdf_literal(self, text: str) -> str:
        """Unescape common PDF literal-string escape sequences."""
        text = text.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
        text = text.replace(r"\ ", " ")
        text = text.replace(r"\n", "\n").replace(r"\r", "\r")
        text = text.replace(r"\t", "\t").replace(r"\b", "\b").replace(r"\f", "\f")

        def _octal_replace(match: re.Match[str]) -> str:
            return chr(int(match.group(1), 8))

        text = re.sub(r"\\([0-7]{1,3})", _octal_replace, text)
        return re.sub(r"\s+", " ", text).strip()

    def _decode_pdf_hex_text(self, hex_text: str) -> str:
        """Decode a PDF hex string, trying UTF-16BE first when it looks BOM-prefixed."""
        normalized = re.sub(r"\s+", "", hex_text)
        if not normalized:
            return ""

        if len(normalized) % 2 == 1:
            normalized += "0"

        try:
            raw = bytes.fromhex(normalized)
        except ValueError:
            return ""

        if raw.startswith(b"\xfe\xff"):
            try:
                return raw[2:].decode("utf-16-be", errors="ignore").strip()
            except Exception:  # pragma: no cover - defensive guard for malformed runtime codec state
                return ""

        decoded = raw.decode("latin-1", errors="ignore")
        return re.sub(r"\s+", " ", decoded).strip()

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
            study_material = self.extract_study_material_from_pdf(pdf_bytes)
            source_context = json.dumps(study_material, sort_keys=True)
            questions = self._generate_questions_with_llm(qcount=question_count, source_excerpt=source_context)
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
