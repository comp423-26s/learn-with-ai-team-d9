# Copyright (c) 2026 Kris Jordan
# SPDX-License-Identifier: MIT

"""Background job handler for Strive quiz generation."""

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from ...config import get_settings
from ...jobs.base_job_handler import BaseJobHandler
from ...repositories.async_job_repository import AsyncJobRepository
from ...repositories.strive_source_repository import StriveSourceRepository
from ...services.strive_service import StriveService
from ...tables.async_job import AsyncJobStatus
from .models import StriveQuizGenerationJob


class StriveQuizGenerationJobHandler(BaseJobHandler[StriveQuizGenerationJob]):
    """Generates Strive quiz questions outside the request/response cycle."""

    def _execute(self, job: StriveQuizGenerationJob, session: Session) -> None:
        """Generates questions and stores the completed quiz payload on the job."""
        async_job_repo = AsyncJobRepository(session)
        async_job = async_job_repo.get_by_id(job.job_id)
        if async_job is None:
            raise ValueError(f"AsyncJob {job.job_id} not found")

        input_data = async_job.input_data
        question_count = int(input_data.get("question_count", 5))
        source_id = input_data.get("source_id")
        source_repo = StriveSourceRepository(session)
        strive_service = StriveService(source_repo=source_repo, settings=get_settings())

        source_excerpt: str | None = None
        if source_id is not None:
            source = source_repo.get_by_id(int(source_id))
            if source is None:
                raise ValueError(f"StriveSource {source_id} not found")
            if source.student_pid != int(input_data["student_pid"]):
                raise PermissionError("not allowed to use this source")
            source_excerpt = strive_service._build_source_context_from_sources([source])

        questions = strive_service._generate_questions_with_llm(
            qcount=question_count,
            source_excerpt=source_excerpt,
        )

        quiz_payload: dict[str, Any] = {
            "id": job.job_id,
            "activity_id": int(input_data["activity_id"]),
            "student_pid": int(input_data["student_pid"]),
            "status": "in_progress",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "question_count": question_count,
            "mode": input_data.get("mode", "daily"),
            "module_name": input_data.get("module_name"),
            "topic": input_data.get("topic"),
            "source_id": source_id,
            "questions": questions,
        }

        async_job.output_data = {"quiz": quiz_payload}
        async_job.status = AsyncJobStatus.COMPLETED
        async_job.completed_at = datetime.now(timezone.utc)
        async_job_repo.update(async_job)
