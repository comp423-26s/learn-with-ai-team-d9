# Copyright (c) 2026 Kris Jordan
# SPDX-License-Identifier: MIT

"""Pydantic models for Strive quiz generation jobs."""

from typing import Literal

from ...interfaces import TrackedJob

STRIVE_QUIZ_GENERATION_KIND = "strive_quiz_generation"


class StriveQuizGenerationJob(TrackedJob):
    """Dramatiq job payload for Strive quiz question generation."""

    type: Literal["strive_quiz_generation"] = "strive_quiz_generation"
