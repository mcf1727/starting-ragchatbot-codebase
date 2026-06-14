import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock
from search_tools import CourseSearchTool
from vector_store import SearchResults


def make_tool():
    mock_store = MagicMock()
    tool = CourseSearchTool(mock_store)
    return tool, mock_store


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_successful_search_returns_formatted_text():
    tool, store = make_tool()
    store.search.return_value = SearchResults(
        documents=["RAG retrieves relevant chunks before generation."],
        metadata=[{"course_title": "RAG Course", "lesson_number": 2}],
        distances=[0.4],
    )
    store.get_lesson_link.return_value = "http://example.com/lesson2"

    result = tool.execute("what is RAG")

    assert "RAG Course" in result
    assert "Lesson 2" in result
    assert "RAG retrieves relevant chunks" in result


def test_multiple_results_all_appear_in_output():
    tool, store = make_tool()
    store.search.return_value = SearchResults(
        documents=["Content A", "Content B"],
        metadata=[
            {"course_title": "Course A", "lesson_number": 1},
            {"course_title": "Course B", "lesson_number": 3},
        ],
        distances=[0.2, 0.6],
    )
    store.get_lesson_link.return_value = None

    result = tool.execute("test query")

    assert "Content A" in result
    assert "Content B" in result
    assert "Course A" in result
    assert "Course B" in result


# ---------------------------------------------------------------------------
# Empty / error results
# ---------------------------------------------------------------------------

def test_empty_results_returns_no_content_message():
    tool, store = make_tool()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    result = tool.execute("obscure query")

    assert "No relevant content found" in result


def test_empty_results_with_course_filter_includes_filter_in_message():
    tool, store = make_tool()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    result = tool.execute("obscure query", course_name="MCP")

    assert "No relevant content found" in result
    assert "MCP" in result


def test_empty_results_with_lesson_filter_includes_filter_in_message():
    tool, store = make_tool()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    result = tool.execute("obscure query", lesson_number=5)

    assert "No relevant content found" in result
    assert "5" in result


def test_error_result_returns_error_string_not_exception():
    tool, store = make_tool()
    store.search.return_value = SearchResults(
        documents=[], metadata=[], distances=[],
        error="Search error: connection refused"
    )

    result = tool.execute("test query")

    # Must return the error string, NOT raise an exception
    assert "Search error" in result
    assert "connection refused" in result


# ---------------------------------------------------------------------------
# Filter forwarding
# ---------------------------------------------------------------------------

def test_course_name_filter_forwarded_to_store():
    tool, store = make_tool()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool.execute("what is MCP", course_name="MCP Course")

    store.search.assert_called_once_with(
        query="what is MCP",
        course_name="MCP Course",
        lesson_number=None,
    )


def test_lesson_number_filter_forwarded_to_store():
    tool, store = make_tool()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool.execute("lesson content", lesson_number=4)

    store.search.assert_called_once_with(
        query="lesson content",
        course_name=None,
        lesson_number=4,
    )


def test_no_filters_calls_store_with_none_values():
    tool, store = make_tool()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool.execute("general query")

    store.search.assert_called_once_with(
        query="general query",
        course_name=None,
        lesson_number=None,
    )


# ---------------------------------------------------------------------------
# Source tracking
# ---------------------------------------------------------------------------

def test_last_sources_populated_after_successful_search():
    tool, store = make_tool()
    store.search.return_value = SearchResults(
        documents=["content"],
        metadata=[{"course_title": "Test Course", "lesson_number": 2}],
        distances=[0.3],
    )
    store.get_lesson_link.return_value = "http://example.com/lesson2"

    tool.execute("test query")

    assert len(tool.last_sources) == 1
    assert tool.last_sources[0]["label"] == "Test Course - Lesson 2"
    assert tool.last_sources[0]["url"] == "http://example.com/lesson2"


def test_last_sources_empty_when_no_results():
    tool, store = make_tool()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool.execute("test query")

    assert tool.last_sources == []


def test_last_sources_none_url_when_no_lesson_link():
    tool, store = make_tool()
    store.search.return_value = SearchResults(
        documents=["content"],
        metadata=[{"course_title": "Course", "lesson_number": 1}],
        distances=[0.5],
    )
    store.get_lesson_link.return_value = None

    tool.execute("test query")

    assert tool.last_sources[0]["url"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_metadata_without_lesson_number_does_not_crash():
    tool, store = make_tool()
    store.search.return_value = SearchResults(
        documents=["content without lesson"],
        metadata=[{"course_title": "Course Without Lessons"}],  # no lesson_number key
        distances=[0.5],
    )

    result = tool.execute("test query")

    assert "Course Without Lessons" in result
    # Header should not contain a lesson number like "Lesson 3"
    import re
    assert not re.search(r"Lesson \d+", result)
