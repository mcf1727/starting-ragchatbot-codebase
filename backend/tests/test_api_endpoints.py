"""
API endpoint tests for the FastAPI app.

Uses the api_client and mock_rag fixtures from conftest.py. The module-level
app import in conftest patches out StaticFiles (no ../frontend needed) and the
RAGSystem dependencies (no ChromaDB / Anthropic client needed).
"""

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------


def test_query_returns_200(api_client):
    response = api_client.post("/api/query", json={"query": "What is RAG?"})
    assert response.status_code == 200


def test_query_response_contains_answer(api_client):
    response = api_client.post("/api/query", json={"query": "What is RAG?"})
    assert response.json()["answer"] == "Test answer about RAG."


def test_query_response_contains_session_id(api_client):
    response = api_client.post("/api/query", json={"query": "What is RAG?"})
    assert "session_id" in response.json()
    assert response.json()["session_id"]  # non-empty


def test_query_response_sources_is_list(api_client):
    response = api_client.post("/api/query", json={"query": "What is RAG?"})
    assert isinstance(response.json()["sources"], list)


def test_query_without_session_id_creates_new_session(api_client, mock_rag):
    api_client.post("/api/query", json={"query": "What is RAG?"})
    mock_rag.session_manager.create_session.assert_called_once()


def test_query_without_session_id_uses_created_session_id(api_client, mock_rag):
    response = api_client.post("/api/query", json={"query": "What is RAG?"})
    # The session_id in the response must equal the one create_session returned
    assert response.json()["session_id"] == "sess-abc123"


def test_query_with_session_id_skips_session_creation(api_client, mock_rag):
    api_client.post(
        "/api/query", json={"query": "Follow-up?", "session_id": "existing-session"}
    )
    mock_rag.session_manager.create_session.assert_not_called()


def test_query_with_session_id_passes_it_to_rag(api_client, mock_rag):
    api_client.post(
        "/api/query", json={"query": "Follow-up?", "session_id": "existing-session"}
    )
    mock_rag.query.assert_called_once_with("Follow-up?", "existing-session")


def test_query_response_includes_sources_from_rag(api_client, mock_rag, sample_source):
    mock_rag.query.return_value = ("Answer with sources.", [sample_source])
    response = api_client.post("/api/query", json={"query": "Tell me about Lesson 1"})
    assert response.json()["sources"] == [sample_source]


def test_query_rag_exception_returns_500(api_client, mock_rag):
    mock_rag.query.side_effect = RuntimeError("Simulated internal error")
    response = api_client.post("/api/query", json={"query": "What is RAG?"})
    assert response.status_code == 500


def test_query_missing_body_returns_422(api_client):
    """FastAPI validates the request body; missing required field → 422."""
    response = api_client.post("/api/query", json={})
    assert response.status_code == 422


def test_query_calls_rag_with_correct_query_text(api_client, mock_rag):
    api_client.post("/api/query", json={"query": "Explain embeddings"})
    call_args = mock_rag.query.call_args
    assert call_args[0][0] == "Explain embeddings"


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------


def test_courses_returns_200(api_client):
    response = api_client.get("/api/courses")
    assert response.status_code == 200


def test_courses_response_contains_total_courses(api_client):
    response = api_client.get("/api/courses")
    assert response.json()["total_courses"] == 2


def test_courses_response_contains_course_titles(api_client):
    response = api_client.get("/api/courses")
    assert response.json()["course_titles"] == ["RAG Fundamentals", "MCP Course"]


def test_courses_reflects_analytics_from_rag(api_client, mock_rag):
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 5,
        "course_titles": ["A", "B", "C", "D", "E"],
    }
    response = api_client.get("/api/courses")
    assert response.json()["total_courses"] == 5
    assert len(response.json()["course_titles"]) == 5


def test_courses_calls_get_course_analytics(api_client, mock_rag):
    api_client.get("/api/courses")
    mock_rag.get_course_analytics.assert_called_once()


def test_courses_rag_exception_returns_500(api_client, mock_rag):
    mock_rag.get_course_analytics.side_effect = RuntimeError("DB unavailable")
    response = api_client.get("/api/courses")
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------


def test_delete_session_returns_200(api_client):
    response = api_client.delete("/api/session/sess-to-delete")
    assert response.status_code == 200


def test_delete_session_returns_cleared_status(api_client):
    response = api_client.delete("/api/session/sess-to-delete")
    assert response.json() == {"status": "cleared"}


def test_delete_session_calls_clear_with_correct_id(api_client, mock_rag):
    api_client.delete("/api/session/my-session-id")
    mock_rag.session_manager.clear_session.assert_called_once_with("my-session-id")


# ---------------------------------------------------------------------------
# GET / (static file stub)
# ---------------------------------------------------------------------------


def test_root_does_not_return_server_error(api_client):
    """The / route is served by _StubStaticFiles; must not return a 5xx."""
    response = api_client.get("/")
    assert response.status_code < 500
