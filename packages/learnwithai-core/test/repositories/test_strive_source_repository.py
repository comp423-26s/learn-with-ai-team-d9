from __future__ import annotations

from typing import Any, cast

from learnwithai.repositories.strive_source_repository import StriveSourceRepository
from learnwithai.tables.strive import StriveSource


class _ExecResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class DummySession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False
        self.refreshed: list[object] = []
        self._exec_result: list[Any] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def refresh(self, model: object) -> None:
        self.refreshed.append(model)

    def get(self, model_type: type, model_id: int) -> None:
        return None

    def exec(self, stmt: Any) -> _ExecResult:
        return _ExecResult(self._exec_result)


def test_model_type() -> None:
    repo = StriveSourceRepository(cast(Any, DummySession()))
    assert repo.model_type is StriveSource


def test_create_source() -> None:
    ds = DummySession()
    repo = StriveSourceRepository(cast(Any, ds))
    source = cast(StriveSource, object())
    result = repo.create_source(source)
    assert source in ds.added
    assert ds.flushed
    assert source in ds.refreshed
    assert result is source


def test_list_by_student_and_activity() -> None:
    ds = DummySession()
    fake = object()
    ds._exec_result = [fake]
    repo = StriveSourceRepository(cast(Any, ds))
    result = repo.list_by_student_and_activity(student_pid=1, activity_id=2)
    assert result == [fake]


def test_list_by_student() -> None:
    ds = DummySession()
    fake = object()
    ds._exec_result = [fake]
    repo = StriveSourceRepository(cast(Any, ds))
    result = repo.list_by_student(student_pid=1)
    assert result == [fake]
