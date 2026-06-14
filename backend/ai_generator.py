import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Tool Usage:
- Use `search_course_content` for questions about specific lesson content or detailed educational materials
- Use `get_course_outline` for outline, structure, or syllabus queries — returns course title, link, and full lesson list with numbers and titles
- You may make up to 2 sequential tool calls per query when needed (e.g. fetch an outline first, then search based on what you found). You will see each tool's result before deciding whether to make another call.
- After your final tool call, synthesize all results into one complete answer.
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._run_tool_loop(response, api_params, tool_manager)
        
        # Return direct response
        return self._extract_text(response)
    
    def _extract_text(self, response) -> str:
        """Extract the first text block from a Claude response."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        raise ValueError(
            f"No text block in Claude response (stop_reason={response.stop_reason}, "
            f"content types={[type(b).__name__ for b in response.content]})"
        )

    def _run_tool_loop(self, initial_response, base_params: Dict[str, Any], tool_manager) -> str:
        """
        Execute up to MAX_TOOL_ROUNDS of tool calls, keeping tools available between
        rounds so Claude can chain searches. Falls through to a final synthesis call
        (no tools) once rounds are exhausted or Claude stops requesting tools.
        """
        messages = base_params["messages"].copy()
        current_response = initial_response

        for round_num in range(self.MAX_TOOL_ROUNDS):
            # Append assistant's tool-use turn
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute every tool_use block; catch errors per-call
            tool_results = []
            for block in current_response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Tool execution error: {e}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # If a round remains, call Claude again with tools so it can chain
            if round_num < self.MAX_TOOL_ROUNDS - 1:
                next_response = self.client.messages.create(
                    **self.base_params,
                    messages=messages,
                    system=base_params["system"],
                    tools=base_params["tools"],
                    tool_choice={"type": "auto"},
                )
                if next_response.stop_reason != "tool_use":
                    return self._extract_text(next_response)
                current_response = next_response
            # rounds exhausted → fall through to synthesis

        return self._synthesis_call(messages, base_params["system"])

    def _synthesis_call(self, messages: List[Dict], system: str) -> str:
        """Final API call without tools — Claude synthesises all tool results."""
        response = self.client.messages.create(
            **self.base_params,
            messages=messages,
            system=system,
        )
        return self._extract_text(response)