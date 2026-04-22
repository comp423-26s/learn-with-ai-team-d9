"""Integration tests for LLM-powered quiz generation in Strive."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


def _extract_token_from_redirect(resp) -> str | None:
    """Extract JWT token from redirect response."""
    full = str(resp.url)
    if "token=" in full:
        return parse_qs(urlparse(full).query).get("token", [None])[0]
    for h in getattr(resp, "history", []):
        if "token=" in str(h.url):
            return parse_qs(urlparse(str(h.url)).query).get("token", [None])[0]
    return None


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    """Get a TestClient with valid JWT token."""
    # Reset DB
    r = client.post("/api/dev/reset-db")
    assert r.status_code == 200

    # Get user
    r = client.get("/api/dev/users")
    assert r.status_code == 200
    users = r.json()
    assert users, "expected seeded users"
    pid = users[0]["pid"]

    # Login to get token
    r = client.get(f"/api/auth/as/{pid}")
    token = _extract_token_from_redirect(r)
    assert token is not None, "Failed to extract token from auth response"

    # Set header for all subsequent requests
    client.headers = {"Authorization": f"Bearer {token}"}
    return client


@pytest.mark.integration
def test_create_quiz_with_python_topics(authenticated_client: TestClient) -> None:
    """Test successful quiz creation with Python-only topics."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    llm_response = [
        {
            "question": "What is Python?",
            "choices": ["A programming language", "A type of snake", "An editor", "A database"],
            "correct_choice_index": 0,
            "explanation": "Python is a high-level programming language known for its simplicity.",
        },
        {
            "question": "What is a function?",
            "choices": ["A variable", "A reusable block of code", "A loop", "A string"],
            "correct_choice_index": 1,
            "explanation": "A function is a reusable block of code that performs a specific task.",
        },
        {
            "question": "Which keyword defines a function in Python?",
            "choices": ["function", "def", "define", "func"],
            "correct_choice_index": 1,
            "explanation": "The 'def' keyword is used to define a function in Python.",
        },
    ]

    # Mock OpenAI API
    with patch("learnwithai.services.strive_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock the chat completion response
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = json.dumps(llm_response)
        mock_client.chat.completions.create.return_value = mock_completion

        # Ensure API key is set
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            create_response = authenticated_client.post(
                f"/api/activities/{activity_id}/quizzes",
                json={"mode": "daily", "question_count": 3},
            )

            assert create_response.status_code == 201
            quiz_data = create_response.json()
            assert quiz_data["status"] == "in_progress"
            assert quiz_data["question_count"] == 3
            assert quiz_data["mode"] == "daily"
            quiz_id = quiz_data["id"]

            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert call_args.kwargs["messages"][0]["role"] == "system"
            prompt = call_args.kwargs["messages"][1]["content"]
            assert "beginner-level Python multiple-choice questions" in prompt
            assert (
                "variables, data types, lists, dictionaries, conditionals, loops, functions, and simple input/output"
                in prompt
            )
            assert "exactly 4 answer choices" in prompt

            questions_response = authenticated_client.get(f"/api/quizzes/{quiz_id}")
            assert questions_response.status_code == 200
            quiz_questions = questions_response.json()
            assert quiz_questions["id"] == quiz_id
            assert len(quiz_questions["questions"]) == 3

            first_question = quiz_questions["questions"][0]
            assert first_question["text"] == "What is Python?"
            assert len(first_question["choices"]) == 4
            assert first_question["choices"][0]["text"] == "A programming language"
            assert first_question["question_id"] == 1

            submit_response = authenticated_client.post(
                f"/api/quizzes/{quiz_id}/submit",
                json={
                    "answers": [
                        {"question_id": 1, "selected_choice_id": 1},
                        {"question_id": 2, "selected_choice_id": 2},
                        {"question_id": 3, "selected_choice_id": 2},
                    ]
                },
            )

            assert submit_response.status_code == 200
            submit_data = submit_response.json()
            assert submit_data["id"] == quiz_id
            assert submit_data["total_count"] == 3
            assert len(submit_data["feedback"]) == 3
