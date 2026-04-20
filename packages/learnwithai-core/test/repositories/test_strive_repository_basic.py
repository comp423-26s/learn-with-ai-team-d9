from __future__ import annotations

from typing import Any, cast

from learnwithai.repositories.strive_repository import StriveRepository
from learnwithai.tables.strive import QuizAnswer, QuizQuestion, QuizSubmission


class DummySession:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False
        self.refreshed = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def refresh(self, model: object) -> None:
        self.refreshed.append(model)

    def get(self, model_type: type, model_id: int):
        return None


def test_strive_repository_basic_calls() -> None:
    ds = DummySession()
    repo = StriveRepository(cast(Any, ds))

    # model_type property
    assert repo.model_type is QuizSubmission

    # get by id should call into our dummy get and return None
    assert repo.get_submission_with_questions(1) is None

    # add_questions and bulk_create_answers should call session.add and flush
    repo.add_questions(1, cast(list[QuizQuestion], [object(), object()]))
    assert len(ds.added) == 2
    assert ds.flushed is True

    ds.added.clear()
    ds.flushed = False
    repo.bulk_create_answers(cast(list[QuizAnswer], [object()]))
    assert len(ds.added) == 1
    assert ds.flushed is True

    # create_submission and update_submission should call through to session methods
    ds.added.clear()
    ds.flushed = False
    ds.refreshed.clear()
    repo.create_submission(cast(QuizSubmission, object()))
    assert ds.flushed is True
    assert len(ds.refreshed) == 1

    ds.refreshed.clear()
    repo.update_submission(cast(QuizSubmission, object()))
    assert ds.flushed is True
    assert len(ds.refreshed) == 1
