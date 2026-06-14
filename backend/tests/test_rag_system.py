import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch
from rag_system import RAGSystem
from vector_store import SearchResults


def make_rag():
    """Build a RAGSystem with mocked VectorStore and AIGenerator but real ToolManager/SessionManager."""
    cfg = MagicMock()
    cfg.CHUNK_SIZE = 800
    cfg.CHUNK_OVERLAP = 100
    cfg.CHROMA_PATH = "/tmp/test_chroma"
    cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    cfg.MAX_RESULTS = 5
    cfg.MAX_HISTORY = 2
    cfg.ANTHROPIC_API_KEY = "fake-key"
    cfg.ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

    with patch("rag_system.VectorStore"), \
         patch("rag_system.AIGenerator"), \
         patch("rag_system.DocumentProcessor"):
        rag = RAGSystem(cfg)

    # Return real ToolManager / SessionManager, mock AI + VectorStore
    return rag


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def test_both_tools_registered():
    rag = make_rag()
    assert "search_course_content" in rag.tool_manager.tools
    assert "get_course_outline" in rag.tool_manager.tools


def test_two_tool_definitions_sent_to_generator():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "answer"

    rag.query("What is RAG?")

    call_kwargs = rag.ai_generator.generate_response.call_args[1]
    tools = call_kwargs["tools"]
    assert len(tools) == 2


def test_tool_definitions_include_search_course_content():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "answer"

    rag.query("What is RAG?")

    call_kwargs = rag.ai_generator.generate_response.call_args[1]
    tool_names = [t["name"] for t in call_kwargs["tools"]]
    assert "search_course_content" in tool_names


def test_tool_definitions_include_get_course_outline():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "answer"

    rag.query("What is the outline?")

    call_kwargs = rag.ai_generator.generate_response.call_args[1]
    tool_names = [t["name"] for t in call_kwargs["tools"]]
    assert "get_course_outline" in tool_names


# ---------------------------------------------------------------------------
# Content query pipeline
# ---------------------------------------------------------------------------

def test_content_query_returns_ai_response():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "RAG stands for Retrieval Augmented Generation."

    response, sources = rag.query("What is RAG?")

    assert response == "RAG stands for Retrieval Augmented Generation."


def test_content_query_returns_empty_sources_when_no_tool_called():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "Some answer"

    _, sources = rag.query("What is RAG?")

    assert sources == []


def test_tool_manager_passed_to_generator():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "answer"

    rag.query("What is RAG?")

    call_kwargs = rag.ai_generator.generate_response.call_args[1]
    assert call_kwargs["tool_manager"] is rag.tool_manager


# ---------------------------------------------------------------------------
# Error propagation — reveals the "query failed" root cause
# ---------------------------------------------------------------------------

def test_exception_from_generator_returns_error_string():
    """
    rag_system.query() now wraps ai_generator calls in try/except.
    Any exception is caught and returned as a user-friendly string instead of
    propagating to app.py → 500 → 'Query Failed'.
    """
    rag = make_rag()
    rag.ai_generator.generate_response.side_effect = Exception("Anthropic API error")

    response, sources = rag.query("What is RAG?")

    assert "error" in response.lower()
    assert sources == []


def test_api_authentication_error_returns_error_string():
    """Simulates an Anthropic AuthenticationError — must NOT cause a 500."""
    import anthropic
    rag = make_rag()
    rag.ai_generator.generate_response.side_effect = anthropic.AuthenticationError(
        message="Invalid API key",
        response=MagicMock(status_code=401, headers={}),
        body={"error": {"message": "Invalid API key"}},
    )

    response, sources = rag.query("What is RAG?")

    assert "error" in response.lower()
    assert sources == []


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def test_session_history_passed_to_generator():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "answer"
    session_id = rag.session_manager.create_session()

    # Prime the session with a previous exchange
    rag.session_manager.add_exchange(session_id, "hi", "hello")

    rag.query("follow-up question", session_id=session_id)

    call_kwargs = rag.ai_generator.generate_response.call_args[1]
    assert call_kwargs.get("conversation_history") is not None


def test_session_updated_after_query():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "My answer"
    session_id = rag.session_manager.create_session()

    rag.query("What is RAG?", session_id=session_id)

    history = rag.session_manager.get_conversation_history(session_id)
    assert history is not None


def test_sources_cleared_between_queries():
    rag = make_rag()
    rag.ai_generator.generate_response.return_value = "answer"

    # Manually inject a stale source into the search tool
    rag.search_tool.last_sources = [{"label": "stale source", "url": None}]

    # First query should consume and clear sources
    _, sources1 = rag.query("query 1")

    # Second query starts with no stale sources
    _, sources2 = rag.query("query 2")

    assert sources2 == []


# ---------------------------------------------------------------------------
# Full pipeline integration (mocked Anthropic client, real tool manager)
# ---------------------------------------------------------------------------

def test_full_pipeline_with_tool_call_does_not_raise():
    """
    End-to-end: simulates Claude choosing search_course_content, the tool running,
    and Claude synthesizing a final answer. Uses mocked Anthropic client + real
    ToolManager + CourseSearchTool (with mocked VectorStore).
    """
    rag = make_rag()

    # Mock the VectorStore to return real search results
    rag.vector_store.search.return_value = SearchResults(
        documents=["RAG retrieves context before generation."],
        metadata=[{"course_title": "RAG Course", "lesson_number": 1}],
        distances=[0.3],
    )
    rag.vector_store.get_lesson_link.return_value = None

    # Build mocked Anthropic client responses
    mock_client = MagicMock()

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_pipeline_test"
    tool_block.name = "search_course_content"
    tool_block.input = {"query": "what is RAG", "course_name": None, "lesson_number": None}

    first_response = MagicMock()
    first_response.stop_reason = "tool_use"
    first_response.content = [tool_block]

    text_block = MagicMock()
    text_block.text = "RAG stands for Retrieval Augmented Generation."
    final_response = MagicMock()
    final_response.content = [text_block]

    mock_client.messages.create.side_effect = [first_response, final_response]

    # Patch the Anthropic client inside the real AIGenerator
    rag.ai_generator.client = mock_client

    # Re-wire: use the REAL generate_response (not the mock)
    from ai_generator import AIGenerator
    real_gen = AIGenerator.__new__(AIGenerator)
    real_gen.client = mock_client
    real_gen.model = "claude-haiku-4-5-20251001"
    real_gen.base_params = {"model": real_gen.model, "temperature": 0, "max_tokens": 800}
    rag.ai_generator = real_gen

    response, sources = rag.query("What is RAG?")

    assert response == "RAG stands for Retrieval Augmented Generation."
    assert mock_client.messages.create.call_count == 2
