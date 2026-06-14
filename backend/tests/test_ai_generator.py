import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator


def make_generator():
    gen = AIGenerator(api_key="fake-key", model="claude-haiku-4-5-20251001")
    gen.client = MagicMock()
    return gen


def make_text_response(text="Answer text", stop_reason="end_turn"):
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = [block]
    return resp


def make_tool_use_response(tool_name="search_course_content", tool_input=None, tool_id="toolu_001"):
    if tool_input is None:
        tool_input = {"query": "what is RAG"}
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = tool_input
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


# ---------------------------------------------------------------------------
# Direct (no-tool) response path
# ---------------------------------------------------------------------------

def test_end_turn_returns_text_directly():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response("Direct answer")

    result = gen.generate_response("What is Python?")

    assert result == "Direct answer"
    gen.client.messages.create.assert_called_once()


def test_end_turn_makes_exactly_one_api_call():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response()

    gen.generate_response("simple question")

    assert gen.client.messages.create.call_count == 1


def test_conversation_history_appended_to_system_prompt():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response()

    gen.generate_response("question", conversation_history="User: hi\nAssistant: hello")

    call_kwargs = gen.client.messages.create.call_args[1]
    assert "Previous conversation" in call_kwargs["system"]
    assert "User: hi" in call_kwargs["system"]


def test_no_history_uses_base_system_prompt():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response()

    gen.generate_response("question")

    call_kwargs = gen.client.messages.create.call_args[1]
    # Should not contain conversation history placeholder
    assert "Previous conversation" not in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Tool-use path: routing
# ---------------------------------------------------------------------------

def test_tool_use_stop_reason_triggers_second_api_call():
    gen = make_generator()
    first = make_tool_use_response()
    second = make_text_response("Final answer after tool")
    gen.client.messages.create.side_effect = [first, second]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "Search results here"

    gen.generate_response("content query", tools=[{"name": "search_course_content"}], tool_manager=mock_tm)

    assert gen.client.messages.create.call_count == 2


def test_execute_tool_called_with_correct_name_and_args():
    gen = make_generator()
    first = make_tool_use_response(tool_name="search_course_content", tool_input={"query": "what is RAG"})
    second = make_text_response("Answer")
    gen.client.messages.create.side_effect = [first, second]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "results"

    gen.generate_response("query", tools=[{}], tool_manager=mock_tm)

    mock_tm.execute_tool.assert_called_once_with("search_course_content", query="what is RAG")


def test_final_text_returned_after_tool_execution():
    gen = make_generator()
    first = make_tool_use_response()
    second = make_text_response("Final synthesized answer")
    gen.client.messages.create.side_effect = [first, second]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "tool output"

    result = gen.generate_response("query", tools=[{}], tool_manager=mock_tm)

    assert result == "Final synthesized answer"


# ---------------------------------------------------------------------------
# Tool-use path: message structure sent to Claude
# ---------------------------------------------------------------------------

def test_second_api_call_includes_assistant_message_with_tool_use():
    gen = make_generator()
    first = make_tool_use_response(tool_id="toolu_abc")
    second = make_text_response()
    gen.client.messages.create.side_effect = [first, second]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "result"

    gen.generate_response("query", tools=[{}], tool_manager=mock_tm)

    second_call_kwargs = gen.client.messages.create.call_args_list[1][1]
    messages = second_call_kwargs["messages"]
    roles = [m["role"] for m in messages]
    assert "assistant" in roles


def test_second_api_call_includes_tool_result_message():
    gen = make_generator()
    first = make_tool_use_response(tool_id="toolu_xyz", tool_input={"query": "RAG"})
    second = make_text_response()
    gen.client.messages.create.side_effect = [first, second]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "Tool output content"

    gen.generate_response("query", tools=[{}], tool_manager=mock_tm)

    second_call_kwargs = gen.client.messages.create.call_args_list[1][1]
    messages = second_call_kwargs["messages"]

    tool_result = None
    for msg in messages:
        if msg["role"] == "user" and isinstance(msg["content"], list):
            for item in msg["content"]:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    tool_result = item
                    break

    assert tool_result is not None, "No tool_result message found in second API call"
    assert tool_result["tool_use_id"] == "toolu_xyz"
    assert tool_result["content"] == "Tool output content"


def test_intermediate_round_two_call_includes_tools_param():
    """
    In the 1-round early-exit flow the second API call is the round-2 intermediate
    call and MUST include tools — Claude needs them available in case it wants to chain.
    If Claude returns end_turn here, we return immediately (no separate synthesis call).
    """
    gen = make_generator()
    first = make_tool_use_response()
    second = make_text_response()  # Claude decides to stop → early return
    gen.client.messages.create.side_effect = [first, second]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "result"

    gen.generate_response("query", tools=[{"name": "search_course_content"}], tool_manager=mock_tm)

    second_call_kwargs = gen.client.messages.create.call_args_list[1][1]
    assert "tools" in second_call_kwargs, (
        "Round-2 intermediate call must include tools so Claude can chain if needed"
    )


# ---------------------------------------------------------------------------
# Edge cases that reveal missing guards
# ---------------------------------------------------------------------------

def test_empty_content_list_raises_value_error():
    """
    _extract_text raises ValueError with a descriptive message when content is empty,
    instead of an opaque IndexError.
    """
    gen = make_generator()
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = []  # empty!
    gen.client.messages.create.return_value = resp

    with pytest.raises(ValueError, match="No text block"):
        gen.generate_response("question")


def test_no_tool_manager_but_tool_use_stop_reason_raises_value_error():
    """
    If Claude returns tool_use but no tool_manager is provided, code falls through
    to _extract_text which raises a descriptive ValueError (no .text on a ToolUseBlock).
    """
    gen = make_generator()
    block = MagicMock(spec=[])  # spec=[] means no attributes at all → hasattr(block, 'text') is False
    block.type = "tool_use"

    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    gen.client.messages.create.return_value = resp

    with pytest.raises(ValueError, match="No text block"):
        gen.generate_response("question")  # no tool_manager kwarg


def test_final_response_empty_content_raises_value_error():
    """
    _extract_text raises ValueError (not opaque IndexError) for empty final response.
    """
    gen = make_generator()
    first = make_tool_use_response()
    second = MagicMock()
    second.content = []  # empty final response
    gen.client.messages.create.side_effect = [first, second]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "result"

    with pytest.raises(ValueError, match="No text block"):
        gen.generate_response("query", tools=[{}], tool_manager=mock_tm)


# ---------------------------------------------------------------------------
# Sequential tool calling — 2-round happy path
# ---------------------------------------------------------------------------

def _tools_param():
    return [{"name": "search_course_content", "description": "...", "input_schema": {}}]


def test_two_tool_rounds_make_three_api_calls():
    gen = make_generator()
    first = make_tool_use_response(tool_name="get_course_outline", tool_input={"course_name": "MCP"}, tool_id="t1")
    second = make_tool_use_response(tool_name="search_course_content", tool_input={"query": "RAG"}, tool_id="t2")
    third = make_text_response("Final synthesized answer")
    gen.client.messages.create.side_effect = [first, second, third]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "tool output"

    gen.generate_response("complex query", tools=_tools_param(), tool_manager=mock_tm)

    assert gen.client.messages.create.call_count == 3


def test_both_tools_executed_in_two_round_sequence():
    gen = make_generator()
    first = make_tool_use_response(tool_name="get_course_outline", tool_input={"course_name": "MCP"}, tool_id="t1")
    second = make_tool_use_response(tool_name="search_course_content", tool_input={"query": "RAG"}, tool_id="t2")
    gen.client.messages.create.side_effect = [first, second, make_text_response()]

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "tool output"

    gen.generate_response("complex query", tools=_tools_param(), tool_manager=mock_tm)

    assert mock_tm.execute_tool.call_count == 2
    calls = mock_tm.execute_tool.call_args_list
    assert calls[0][0][0] == "get_course_outline"
    assert calls[1][0][0] == "search_course_content"


def test_final_text_returned_after_two_rounds():
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_tool_use_response(tool_id="t2"),
        make_text_response("Two-round answer"),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "output"

    result = gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    assert result == "Two-round answer"


def test_round_two_api_call_includes_tools_param():
    """The intermediate (round-2) call must keep tools so Claude can chain."""
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_tool_use_response(tool_id="t2"),
        make_text_response(),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "output"

    gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    round_two_kwargs = gen.client.messages.create.call_args_list[1][1]
    assert "tools" in round_two_kwargs, "Round-2 API call must include tools"
    assert "tool_choice" in round_two_kwargs


def test_synthesis_call_after_two_rounds_excludes_tools():
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_tool_use_response(tool_id="t2"),
        make_text_response(),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "output"

    gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    synthesis_kwargs = gen.client.messages.create.call_args_list[2][1]
    assert "tools" not in synthesis_kwargs
    assert "tool_choice" not in synthesis_kwargs


def test_round_two_messages_include_round_one_results():
    """The synthesis call's message list must have 5 turns: user, asst1, result1, asst2, result2."""
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_tool_use_response(tool_id="t2"),
        make_text_response(),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "output"

    gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    synthesis_messages = gen.client.messages.create.call_args_list[2][1]["messages"]
    assert len(synthesis_messages) == 5  # user, asst1, tool_result1, asst2, tool_result2


# ---------------------------------------------------------------------------
# Sequential tool calling — cap enforcement
# ---------------------------------------------------------------------------

def test_cap_at_two_rounds_even_if_claude_keeps_requesting():
    """Claude returns tool_use three times but only 2 rounds are allowed."""
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_tool_use_response(tool_id="t2"),
        make_tool_use_response(tool_id="t3"),  # would be round 3 — must not be reached
        make_text_response(),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "output"

    gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    assert gen.client.messages.create.call_count == 3  # round1 + round2-intermediate + synthesis


# ---------------------------------------------------------------------------
# Sequential tool calling — early termination
# ---------------------------------------------------------------------------

def test_early_stop_when_round_two_returns_no_tool_use():
    """If the intermediate call returns end_turn, return immediately without a synthesis call."""
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_text_response("Early answer"),  # round-2 intermediate returns text → stop
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "output"

    result = gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    assert gen.client.messages.create.call_count == 2
    assert result == "Early answer"


# ---------------------------------------------------------------------------
# Sequential tool calling — tool error resilience
# ---------------------------------------------------------------------------

def test_tool_error_in_round_one_continues_to_synthesis():
    """An error in round-1 tool execution is caught; pipeline continues to synthesis."""
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_text_response("Answer despite error"),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.side_effect = Exception("DB unavailable")

    result = gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    assert gen.client.messages.create.call_count == 2
    assert result == "Answer despite error"


def test_tool_error_in_round_two_continues_to_synthesis():
    """An error in round-2 tool execution is caught; pipeline still reaches synthesis."""
    gen = make_generator()
    gen.client.messages.create.side_effect = [
        make_tool_use_response(tool_id="t1"),
        make_tool_use_response(tool_id="t2"),
        make_text_response("Answer after two rounds with error"),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.side_effect = [
        "round 1 result",       # round 1 succeeds
        Exception("timeout"),   # round 2 fails
    ]

    result = gen.generate_response("query", tools=_tools_param(), tool_manager=mock_tm)

    assert gen.client.messages.create.call_count == 3
    assert result == "Answer after two rounds with error"
