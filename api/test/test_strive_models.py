from datetime import datetime, timezone

from api.models.strive import (
    ChoiceDTO,
    QuizAnswerDTO,
    QuizCreateRequest,
    QuizCreateResponse,
    QuizFeedbackDTO,
    QuizQuestionDTO,
    QuizQuestionsResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)


def test_quiz_create_and_response_models_roundtrip():
    req = QuizCreateRequest(mode="daily", question_count=3)
    assert req.mode == "daily"
    assert req.question_count == 3

    resp = QuizCreateResponse(
        id=101,
        activity_id=42,
        student_pid=730611076,
        status="in_progress",
        started_at=datetime.now(timezone.utc),
        question_count=3,
        mode="daily",
    )
    assert resp.id == 101
    assert resp.mode == "daily"


def test_questions_and_submit_models_serialization():
    choices = [ChoiceDTO(id=1, text="a"), ChoiceDTO(id=2, text="b")]
    qdto = QuizQuestionDTO(question_id=1, text="Which?", choices=choices)

    questions_resp = QuizQuestionsResponse(
        id=101,
        activity_id=42,
        student_pid=730611076,
        status="in_progress",
        mode="daily",
        questions=[qdto],
    )
    assert questions_resp.questions[0].choices[1].text == "b"

    answer = QuizAnswerDTO(question_id=1, selected_choice_id=2)
    submit_req = QuizSubmitRequest(answers=[answer])
    assert submit_req.answers[0].selected_choice_id == 2

    feedback = QuizFeedbackDTO(question_id=1, correct=True, correct_choice_id=2, explanation="Because.")
    submit_resp = QuizSubmitResponse(
        id=101,
        score=100.0,
        correct_count=1,
        total_count=1,
        feedback=[feedback],
        finished_at=datetime.now(timezone.utc),
    )
    assert submit_resp.feedback[0].correct is True
