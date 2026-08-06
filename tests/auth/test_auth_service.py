from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

import app.services.auth_service as auth_module
from app.services.auth_service import AuthService, AuthServiceDatabaseError


class DummySession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_authenticate_wraps_database_errors_and_closes_session(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(auth_module, "SessionLocal", lambda: session)

    class BrokenRepository:
        def get_by_username(self, username: str):
            raise OperationalError("SELECT 1", {"usuario": username}, TimeoutError("timed out"))

    service = AuthService()
    monkeypatch.setattr(service, "_repo", lambda db: BrokenRepository())

    with pytest.raises(AuthServiceDatabaseError):
        service.authenticate("mati", "1234")

    assert session.closed is True


def test_authenticate_returns_none_for_missing_user_and_closes_session(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(auth_module, "SessionLocal", lambda: session)

    class EmptyRepository:
        def get_by_username(self, username: str):
            return None

    service = AuthService()
    monkeypatch.setattr(service, "_repo", lambda db: EmptyRepository())

    assert service.authenticate("mati", "1234") is None
    assert session.closed is True
