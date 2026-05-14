"""LangChain ReAct agent wiring all three tools together."""
from __future__ import annotations
import os
import re
import time
from types import SimpleNamespace
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from backend.tools.sql_tool import sql_query
from backend.tools.mongo_tool import mongo_query
from backend.tools.rag_tool import handbook_search

TOOLS = [sql_query, mongo_query, handbook_search]
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}

TOOL_ROUTING_HINT = """
You are a helpful assistant for SkyNova Airlines. You have three tools:

1. sql_query       — use for questions about flights, passengers, and bookings (structured data in PostgreSQL).
2. mongo_query     — use for questions about support tickets, flight reviews, and user activity logs (MongoDB).
3. handbook_search — use for questions about airline policies, rules, refunds, baggage, check-in, frequent flyer program, or any procedural/policy information.

Always use the most specific tool. If a question spans multiple sources, call each relevant tool in turn.

Final answer formatting:
- Write a user-friendly final answer for a business user.
- Start with the direct answer, then add concise bullet points or a compact table-style list when helpful.
- Do not expose raw JSON, database rows, internal tool names, or implementation details in the final answer unless the user asks for them.
- If tool output is empty, say what was checked and that no matching records were found.
"""

ROUTING_KEYWORDS = {
    "sql_query": (
        "aircraft",
        "arrival",
        "base price",
        "booking",
        "bookings",
        "cabin",
        "cancelled flight",
        "confirmed",
        "delayed flight",
        "departure",
        "destination",
        "flight number",
        "flight status",
        "flights",
        "origin",
        "passenger",
        "passengers",
        "scheduled flight",
        "seat",
        "tier",
        "upcoming flight",
    ),
    "mongo_query": (
        "activity",
        "activity log",
        "customer_id",
        "device",
        "flight review",
        "food rating",
        "high priority",
        "low rating",
        "mobile",
        "priority",
        "review",
        "reviews",
        "support",
        "support ticket",
        "ticket",
        "tickets",
        "user activity",
        "web",
    ),
    "handbook_search": (
        "baggage",
        "boarding",
        "check-in policy",
        "check in policy",
        "compensation",
        "fee",
        "fees",
        "frequent flyer program",
        "handbook",
        "policy",
        "procedure",
        "procedures",
        "refund",
        "refunds",
        "rule",
        "rules",
    ),
}


def route_question_to_tool_names(question: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()
    matched_tools = []

    for tool_name, keywords in ROUTING_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            matched_tools.append(tool_name)

    return matched_tools or list(TOOLS_BY_NAME)


def _message_content_as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def stream_events_from_result(result: dict[str, Any], elapsed_ms: int) -> list[dict[str, Any]]:
    events = []
    for action, observation in result.get("intermediate_steps", []):
        events.append(
            {
                "type": "action",
                "tool": action.tool,
                "input": action.tool_input,
            }
        )
        events.append(
            {
                "type": "observation",
                "tool": action.tool,
                "output": str(observation),
            }
        )

    events.append({"type": "answer", "answer": result["output"]})
    events.append({"type": "done", "elapsed_ms": elapsed_ms})
    return events


class AgentExecutorAdapter:
    """Preserve the response shape expected by the FastAPI endpoint."""

    def __init__(self, agents_by_route: dict[tuple[str, ...], Any]):
        self._agents_by_route = agents_by_route

    def invoke(self, inputs: dict[str, Any]) -> dict[str, Any]:
        question = inputs["input"]
        tool_names = tuple(route_question_to_tool_names(question))
        agent = self._agents_by_route.get(tool_names, self._agents_by_route[tuple(TOOLS_BY_NAME)])
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        messages = result.get("messages", [])

        tool_outputs = {
            message.tool_call_id: _message_content_as_text(message.content)
            for message in messages
            if isinstance(message, ToolMessage)
        }

        intermediate_steps = []
        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            for tool_call in message.tool_calls:
                action = SimpleNamespace(
                    tool=tool_call["name"],
                    tool_input=tool_call.get("args", {}),
                )
                observation = tool_outputs.get(tool_call.get("id"), "")
                intermediate_steps.append((action, observation))

        final_messages = [
            message
            for message in messages
            if isinstance(message, AIMessage) and not message.tool_calls
        ]
        output_message = final_messages[-1] if final_messages else messages[-1]

        return {
            "output": _message_content_as_text(output_message.content),
            "intermediate_steps": intermediate_steps,
        }

    def stream(self, inputs: dict[str, Any]):
        start = time.monotonic()
        question = inputs["input"]
        tool_names = route_question_to_tool_names(question)

        yield {
            "type": "thinking",
            "message": "Routing question and preparing the agent.",
            "tools_available": tool_names,
        }

        result = self.invoke(inputs)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        yield from stream_events_from_result(result, elapsed_ms)


def build_agent() -> AgentExecutorAdapter:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0,
    )

    route_tool_names = {
        tuple(TOOLS_BY_NAME),
        ("sql_query",),
        ("mongo_query",),
        ("handbook_search",),
        ("sql_query", "mongo_query"),
        ("sql_query", "handbook_search"),
        ("mongo_query", "handbook_search"),
        ("sql_query", "mongo_query", "handbook_search"),
    }
    agents_by_route = {
        tool_names: create_agent(
            model=llm,
            tools=[TOOLS_BY_NAME[name] for name in tool_names],
            system_prompt=TOOL_ROUTING_HINT,
        )
        for tool_names in route_tool_names
    }
    return AgentExecutorAdapter(agents_by_route)
