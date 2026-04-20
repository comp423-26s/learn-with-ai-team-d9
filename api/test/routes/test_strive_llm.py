"""Integration tests for LLM-powered quiz generation in Strive."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock, patch

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


@pytest.fixture
def mock_llm_response() -> list[dict]:
    """Sample LLM-generated questions response."""
    return [
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


@pytest.fixture
def get_activity(authenticated_client: TestClient):
    """Helper to get a test activity."""
    r = authenticated_client.get("/api/courses")
    assert r.status_code == 200
    courses = r.json()
    assert courses, "expected seeded courses"
    course_id = courses[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    assert r.status_code == 200
    activities = r.json()
    assert activities, "expected seeded activities"
    activity_id = activities[0]["id"]

    return authenticated_client, activity_id


@pytest.mark.integration
def test_create_quiz_with_llm_success(authenticated_client: TestClient, mock_llm_response: list[dict]) -> None:
    """Test successful quiz creation with LLM-generated questions."""
    # Get an activity
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    # Mock OpenAI API
    with patch("learnwithai.services.strive_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock the chat completion response
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = json.dumps(mock_llm_response)
        mock_client.chat.completions.create.return_value = mock_completion

        # Ensure API key is set
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            # Step 1: Create quiz with LLM parameters
            create_response = authenticated_client.post(
                f"/api/activities/{activity_id}/quizzes",
                json={
                    "mode": "module",
                    "module_name": "Module 2: Python Basics",
                    "topic": "Functions",
                    "question_count": 3,
                },
            )

            # Assertions on creation
            assert create_response.status_code == 201
            quiz_data = create_response.json()
            assert quiz_data["status"] == "in_progress"
            assert quiz_data["question_count"] == 3
            assert quiz_data["mode"] == "module"
            assert quiz_data["topic"] == "Functions"
            assert quiz_data["module_name"] == "Module 2: Python Basics"
            quiz_id = quiz_data["id"]

            # Verify OpenAI was called with correct parameters
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "Functions" in prompt
            assert "Module 2: Python Basics" in prompt
            assert "3" in prompt

            # Step 2: Retrieve questions
            questions_response = authenticated_client.get(f"/api/quizzes/{quiz_id}")

            # Assertions on questions
            assert questions_response.status_code == 200
            quiz_questions = questions_response.json()
            assert quiz_questions["id"] == quiz_id
            assert len(quiz_questions["questions"]) == 3
            assert quiz_questions["mode"] == "module"

            # Verify first question structure
            first_question = quiz_questions["questions"][0]
            assert first_question["text"] == "What is Python?"
            assert len(first_question["choices"]) == 4
            assert first_question["choices"][0]["text"] == "A programming language"
            assert first_question["question_id"] == 1


@pytest.mark.integration
def test_create_quiz_with_topic_only(authenticated_client: TestClient, mock_llm_response: list[dict]) -> None:
    """Test quiz creation with only topic specified (no module_name)."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    with patch("learnwithai.services.strive_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = json.dumps(mock_llm_response[:2])
        mock_client.chat.completions.create.return_value = mock_completion

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            response = authenticated_client.post(
                f"/api/activities/{activity_id}/quizzes",
                json={
                    "mode": "daily",
                    "topic": "Variables",
                    "question_count": 2,
                },
            )

            assert response.status_code == 201
            quiz_data = response.json()
            assert quiz_data["status"] == "in_progress"
            assert quiz_data["question_count"] == 2
            assert quiz_data["topic"] == "Variables"
            assert quiz_data["module_name"] is None

            # Verify prompt includes topic but not module
            call_args = mock_client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "Variables" in prompt


@pytest.mark.integration
def test_create_quiz_when_llm_api_fails(authenticated_client: TestClient) -> None:
    """Test graceful fallback when LLM API raises an exception."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    with patch("learnwithai.services.strive_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        # Simulate API error
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            # Should still succeed (fallback to empty questions)
            response = authenticated_client.post(
                f"/api/activities/{activity_id}/quizzes",
                json={"mode": "daily", "question_count": 3},
            )

            assert response.status_code == 201
            quiz_data = response.json()
            quiz_id = quiz_data["id"]

            # Retrieve questions (should have empty or default questions)
            response = authenticated_client.get(f"/api/quizzes/{quiz_id}")
            assert response.status_code == 200


@pytest.mark.integration
def test_create_quiz_without_api_key(authenticated_client: TestClient) -> None:
    """Test that sample/fallback questions are used when no OpenAI API key."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    # Clear API key
    with patch.dict("os.environ", {}, clear=True):
        response = authenticated_client.post(
            f"/api/activities/{activity_id}/quizzes",
            json={"mode": "daily", "question_count": 5},
        )

        assert response.status_code == 201
        quiz_data = response.json()
        assert quiz_data["status"] == "in_progress"
        assert quiz_data["question_count"] == 5
        quiz_id = quiz_data["id"]

        # Retrieve questions
        response = authenticated_client.get(f"/api/quizzes/{quiz_id}")
        assert response.status_code == 200
        quiz_questions = response.json()
        assert len(quiz_questions["questions"]) == 5

        # Verify sample questions are used
        first_question = quiz_questions["questions"][0]
        assert "Sample question" in first_question["text"]


@pytest.mark.integration
def test_create_quiz_with_malformed_llm_response(authenticated_client: TestClient) -> None:
    """Test that malformed LLM response is handled gracefully."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    with patch("learnwithai.services.strive_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Return invalid JSON
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "invalid json not parseable"
        mock_client.chat.completions.create.return_value = mock_completion

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            response = authenticated_client.post(
                f"/api/activities/{activity_id}/quizzes",
                json={"mode": "daily", "question_count": 3},
            )

            # Should still return 201
            assert response.status_code == 201
            quiz_id = response.json()["id"]

            # Should not crash on retrieval
            response = authenticated_client.get(f"/api/quizzes/{quiz_id}")
            assert response.status_code == 200


@pytest.mark.integration
def test_submit_quiz_with_llm_questions(authenticated_client: TestClient, mock_llm_response: list[dict]) -> None:
    """Test submitting answers to an LLM-generated quiz."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    with patch("learnwithai.services.strive_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = json.dumps(mock_llm_response)
        mock_client.chat.completions.create.return_value = mock_completion

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            # Create quiz
            create_response = authenticated_client.post(
                f"/api/activities/{activity_id}/quizzes",
                json={
                    "mode": "module",
                    "module_name": "Python Functions",
                    "question_count": 3,
                },
            )
            quiz_id = create_response.json()["id"]

            # Submit answers
            submit_response = authenticated_client.post(
                f"/api/quizzes/{quiz_id}/submit",
                json={
                    "answers": [
                        {"question_id": 1, "selected_choice_id": 1},  # Correct
                        {"question_id": 2, "selected_choice_id": 2},  # Correct
                        {"question_id": 3, "selected_choice_id": 2},  # Correct
                    ]
                },
            )

            assert submit_response.status_code == 200
            submit_data = submit_response.json()
            assert submit_data["id"] == quiz_id
            assert len(submit_data["feedback"]) == 3

            # Verify feedback structure
            for feedback in submit_data["feedback"]:
                assert "question_id" in feedback
                assert "correct" in feedback
                assert "explanation" in feedback


@pytest.mark.integration
def test_enhanced_prompt_with_step_by_step_explanation(authenticated_client: TestClient) -> None:
    """Test that enhanced prompt generates questions with detailed step-by-step explanations."""
    r = authenticated_client.get("/api/courses")
    course_id = r.json()[0]["id"]

    r = authenticated_client.get(f"/api/courses/{course_id}/activities")
    activity_id = r.json()[0]["id"]

    # Create questions with detailed step-by-step explanations
    detailed_llm_response = [
        {
            "question": "What is the purpose of a function in Python?",
            "choices": [
                "To execute code once and discard it",
                "To organize reusable code into named blocks that can be called multiple times",
                "To create variables that store data",
                "To display output on the screen",
            ],
            "correct_choice_index": 1,
            "explanation": (
                "Step 1: A function is a named block of code. "
                "Step 2: Functions allow us to write code once and reuse it many times by calling the function name. "
                "Step 3: This promotes code organization, reduces duplication, and makes programs easier to maintain. "
                "Therefore, organizing reusable code into named blocks is the core purpose of functions."
            ),
        },
        {
            "question": "How do you define a function in Python?",
            "choices": ["Using the 'function' keyword", "Using the 'def' keyword followed by a colon", "Using parentheses only", "Functions cannot be defined"],
            "correct_choice_index": 1,
            "explanation": (
                "Step 1: Python uses the 'def' keyword to define functions. "
                "Step 2: The syntax is 'def function_name():' with a colon at the end. "
                "Step 3: The function body is indented below the def line. "
                "Therefore, the 'def' keyword followed by a colon is the correct Python syntax for function definition."
            ),
        },
    ]

    with patch("learnwithai.services.strive_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = json.dumps(detailed_llm_response)
        mock_client.chat.completions.create.return_value = mock_completion

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            # Create quiz with module and topic context
            response = authenticated_client.post(
                f"/api/activities/{activity_id}/quizzes",
                json={
                    "mode": "module",
                    "module_name": "Module 2: Python Basics",
                    "topic": "Functions",
                    "question_count": 2,
                },
            )

            assert response.status_code == 201
            quiz_id = response.json()["id"]

            # Verify enhanced prompt was used
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]

            # Verify enhanced prompt features
            assert "step-by-step" in prompt.lower()
            assert "learning objective" in prompt.lower() or "core concept" in prompt.lower()
            assert "misconception" in prompt.lower()
            assert "Module 2: Python Basics" in prompt
            assert "Functions" in prompt

            # Get questions
            questions_response = authenticated_client.get(f"/api/quizzes/{quiz_id}")
            assert questions_response.status_code == 200
            quiz_questions = questions_response.json()
            assert len(quiz_questions["questions"]) == 2

            # Submit answers to retrieve explanations and verify step-by-step content
            submit_response = authenticated_client.post(
                f"/api/quizzes/{quiz_id}/submit",
                json={
                    "answers": [
                        {"question_id": 1, "selected_choice_id": 2},  # Correct
                        {"question_id": 2, "selected_choice_id": 2},  # Correct
                    ]
                },
            )

            assert submit_response.status_code == 200
            feedback = submit_response.json()
            assert len(feedback["feedback"]) == 2

            # Verify step-by-step explanations are returned
            for fb in feedback["feedback"]:
                explanation = fb.get("explanation", "")
                assert "Step" in explanation, "Explanation should contain step-by-step content"
                assert len(explanation) > 100, "Explanation should be detailed (not just one-liner)"
