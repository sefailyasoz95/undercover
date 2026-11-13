import pytest
from fastapi.testclient import TestClient

from agent import main
from backend import db
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    db.seed()
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return TestClient(app)
