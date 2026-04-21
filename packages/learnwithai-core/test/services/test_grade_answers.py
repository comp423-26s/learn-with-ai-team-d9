from learnwithai.services.strive_service import grade_answers


def make_questions(n: int):
    return [{"question_id": i + 1, "correct_choice_id": 1} for i in range(n)]


def make_answers(correct_count: int, total: int):
    answers = []
    for i in range(total):
        selected = 1 if i < correct_count else 2
        answers.append({"question_id": i + 1, "selected_choice_id": selected})
    return answers


def test_all_correct():
    questions = make_questions(5)
    answers = make_answers(5, 5)
    res = grade_answers(questions, answers, mode="daily")
    assert res["correct_count"] == 5
    assert res["total_count"] == 5
    assert res["score"] == 100.0
    assert res["accuracy"] == 100.0


def test_partial_correct():
    questions = make_questions(4)
    answers = make_answers(1, 4)
    res = grade_answers(questions, answers, mode="module")
    assert res["correct_count"] == 1
    assert res["total_count"] == 4
    assert res["score"] == 25.0
    assert res["accuracy"] == 25.0


def test_no_questions():
    questions = []
    answers = []
    res = grade_answers(questions, answers)
    assert res["correct_count"] == 0
    assert res["total_count"] == 0
    assert res["score"] == 0.0
    assert res["accuracy"] == 0.0
