import sys
import os

# Add the backend directory to sys.path so all modules resolve without manual inserts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


class _StubStaticFiles:
    """
    Stand-in for fastapi.staticfiles.StaticFiles.
    Avoids the directory-existence check that fires when app.py is imported
    and the ../frontend path doesn't exist in the test environment.
    Returns a minimal HTML response so TestClient requests to / don't hang.
    """

    def __init__(self, *args, **kwargs):
        pass

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"text/html; charset=utf-8"]],
                }
            )
            await send({"type": "http.response.body", "body": b"<html>stub</html>"})


def _import_app_with_patches():
    """
    Import backend/app.py with its two module-level side-effects neutralised:
      1. RAGSystem(config) — VectorStore / AIGenerator / DocumentProcessor are mocked
         so no ChromaDB init or Anthropic client is created.
      2. StaticFiles(directory="../frontend") — replaced with _StubStaticFiles so the
         missing frontend directory does not raise an error.

    Returns the imported app module.
    """
    # Drop stale cached copies so the patches apply to a fresh import
    for key in list(sys.modules.keys()):
        if key in ("app", "rag_system"):
            del sys.modules[key]

    with (
        patch("fastapi.staticfiles.StaticFiles", _StubStaticFiles),
        patch("rag_system.VectorStore"),
        patch("rag_system.AIGenerator"),
        patch("rag_system.DocumentProcessor"),
    ):
        import app as _mod

    return _mod


# Import once when conftest is loaded; all test files in this package share it.
_app_module = _import_app_with_patches()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_rag():
    """Fresh MagicMock RAGSystem with sensible defaults for each test."""
    m = MagicMock()
    m.query.return_value = ("Test answer about RAG.", [])
    m.session_manager.create_session.return_value = "sess-abc123"
    m.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["RAG Fundamentals", "MCP Course"],
    }
    return m


@pytest.fixture
def api_client(mock_rag, monkeypatch):
    """
    TestClient backed by the real FastAPI app, with app.rag_system replaced
    by the mock_rag fixture for the duration of each test.
    monkeypatch restores the original value automatically after the test.
    """
    monkeypatch.setattr(_app_module, "rag_system", mock_rag)
    return TestClient(_app_module.app, raise_server_exceptions=False)


@pytest.fixture
def sample_source():
    return {"label": "RAG Fundamentals - Lesson 1", "url": "http://example.com/lesson1"}
