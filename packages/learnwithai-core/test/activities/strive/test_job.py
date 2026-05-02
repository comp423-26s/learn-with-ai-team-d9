# Copyright (c) 2026 Kris Jordan
# SPDX-License-Identifier: MIT

"""Tests for Strive quiz generation jobs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from learnwithai.activities.strive.job import StriveQuizGenerationJobHandler
from learnwithai.activities.strive.models import StriveQuizGenerationJob
from learnwithai.tables.async_job import AsyncJobStatus


def test_strive_quiz_generation_job_type() -> None:
    job = StriveQuizGenerationJob(job_id=1)

    assert job.type == "strive_quiz_generation"


def test_handler_generates_quiz_without_source_context() -> None:
    handler = StriveQuizGenerationJobHandler()
    session = MagicMock()
    async_job = MagicMock()
    async_job.input_data = {
        "activity_id": 7,
        "student_pid": 123,
        "question_count": 2,
        "mode": "daily",
        "module_name": "Module 1",
        "topic": "Loops",
        "source_id": None,
    }

    async_repo = MagicMock()
    async_repo.get_by_id.return_value = async_job
    async_repo_cls = MagicMock(return_value=async_repo)
    source_repo_cls = MagicMock()
    strive_service = MagicMock()
    questions = [{"question_id": 1, "text": "Q", "choices": [], "correct_choice_id": 1, "explanation": "x"}]
    strive_service._generate_questions_with_llm.return_value = questions

    with (
        patch("learnwithai.activities.strive.job.AsyncJobRepository", async_repo_cls),
        patch("learnwithai.activities.strive.job.StriveSourceRepository", source_repo_cls),
        patch("learnwithai.activities.strive.job.StriveService", return_value=strive_service),
        patch("learnwithai.activities.strive.job.get_settings", return_value=MagicMock()),
    ):
        handler._execute(StriveQuizGenerationJob(job_id=42), session)

    strive_service._generate_questions_with_llm.assert_called_once_with(qcount=2, source_excerpt=None)
    assert async_job.output_data["quiz"]["id"] == 42
    assert async_job.output_data["quiz"]["module_name"] == "Module 1"
    assert async_job.output_data["quiz"]["questions"] == questions
    assert async_job.status == AsyncJobStatus.COMPLETED
    assert async_job.completed_at is not None
    async_repo.update.assert_called_once_with(async_job)


def test_handler_generates_quiz_with_source_context() -> None:
    handler = StriveQuizGenerationJobHandler()
    session = MagicMock()
    async_job = MagicMock()
    async_job.input_data = {
        "activity_id": 7,
        "student_pid": 123,
        "question_count": 1,
        "mode": "module",
        "module_name": None,
        "topic": None,
        "source_id": 9,
    }
    source = MagicMock()
    source.student_pid = 123

    async_repo = MagicMock()
    async_repo.get_by_id.return_value = async_job
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = source
    strive_service = MagicMock()
    strive_service._build_source_context_from_sources.return_value = "source excerpt"
    strive_service._generate_questions_with_llm.return_value = []

    with (
        patch("learnwithai.activities.strive.job.AsyncJobRepository", return_value=async_repo),
        patch("learnwithai.activities.strive.job.StriveSourceRepository", return_value=source_repo),
        patch("learnwithai.activities.strive.job.StriveService", return_value=strive_service),
        patch("learnwithai.activities.strive.job.get_settings", return_value=MagicMock()),
    ):
        handler._execute(StriveQuizGenerationJob(job_id=42), session)

    source_repo.get_by_id.assert_called_once_with(9)
    strive_service._build_source_context_from_sources.assert_called_once_with([source])
    strive_service._generate_questions_with_llm.assert_called_once_with(qcount=1, source_excerpt="source excerpt")
    assert async_job.output_data["quiz"]["source_id"] == 9


def test_handler_raises_when_async_job_is_missing() -> None:
    handler = StriveQuizGenerationJobHandler()

    with patch("learnwithai.activities.strive.job.AsyncJobRepository") as repo_cls:
        repo_cls.return_value.get_by_id.return_value = None
        with pytest.raises(ValueError, match="AsyncJob 42 not found"):
            handler._execute(StriveQuizGenerationJob(job_id=42), MagicMock())


def test_handler_raises_when_source_is_missing() -> None:
    handler = StriveQuizGenerationJobHandler()
    async_job = MagicMock()
    async_job.input_data = {"question_count": 1, "source_id": 9, "student_pid": 123}

    with (
        patch("learnwithai.activities.strive.job.AsyncJobRepository") as async_repo_cls,
        patch("learnwithai.activities.strive.job.StriveSourceRepository") as source_repo_cls,
        patch("learnwithai.activities.strive.job.StriveService"),
        patch("learnwithai.activities.strive.job.get_settings", return_value=MagicMock()),
    ):
        async_repo_cls.return_value.get_by_id.return_value = async_job
        source_repo_cls.return_value.get_by_id.return_value = None
        with pytest.raises(ValueError, match="StriveSource 9 not found"):
            handler._execute(StriveQuizGenerationJob(job_id=42), MagicMock())


def test_handler_rejects_source_owned_by_another_student() -> None:
    handler = StriveQuizGenerationJobHandler()
    async_job = MagicMock()
    async_job.input_data = {"question_count": 1, "source_id": 9, "student_pid": 123}
    source = MagicMock()
    source.student_pid = 999

    with (
        patch("learnwithai.activities.strive.job.AsyncJobRepository") as async_repo_cls,
        patch("learnwithai.activities.strive.job.StriveSourceRepository") as source_repo_cls,
        patch("learnwithai.activities.strive.job.StriveService"),
        patch("learnwithai.activities.strive.job.get_settings", return_value=MagicMock()),
    ):
        async_repo_cls.return_value.get_by_id.return_value = async_job
        source_repo_cls.return_value.get_by_id.return_value = source
        with pytest.raises(PermissionError, match="not allowed"):
            handler._execute(StriveQuizGenerationJob(job_id=42), MagicMock())
