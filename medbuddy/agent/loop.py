"""The agent loop — MedBuddy's fully-agentic core implemented with LangGraph."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from medbuddy.agent.registry import ToolRegistry
from medbuddy.agent.system_prompt import SYSTEM_PROMPT
from medbuddy.channels import IncomingMessage
from medbuddy.config import get_settings
from medbuddy.tools.base import ToolContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from medbuddy.channels import MessagingChannel
    from medbuddy.datasets.loaders import Datasets
    from medbuddy.llm import LLMClient
    from medbuddy.scheduler.clock import Clock

MAX_ITERS = 8


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    sender: str
    pending_image: bytes | None


def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last = messages[-1] if messages else None
    tool_calls = (
        last.get("tool_calls")
        if isinstance(last, dict)
        else getattr(last, "tool_calls", None)
    ) or []
    return "tool_node" if tool_calls else END


class Agent:
    def __init__(self, llm: "LLMClient", registry: ToolRegistry | None = None) -> None:
        self.llm = llm
        self.registry = registry or ToolRegistry()
        self._graph = None
        self._graph_db_key: str | None = None
        self._ctx_map: dict[str, ToolContext] = {}
        self._checkpoint_connections: dict[str, sqlite3.Connection] = {}

    def reset(self, sender: str) -> None:
        """Compatibility no-op; state is now checkpointed by LangGraph."""
        return None

    def _build_graph(self, checkpointer=None):
        graph = StateGraph(AgentState)
        graph.add_node("agent_node", self.agent_node)
        graph.add_node("tool_node", self.tool_node)
        graph.set_entry_point("agent_node")
        graph.add_conditional_edges(
            "agent_node",
            should_continue,
            {"tool_node": "tool_node", END: END},
        )
        graph.add_edge("tool_node", "agent_node")
        return graph.compile(checkpointer=checkpointer)

    def agent_node(self, state: AgentState) -> AgentState:
        self._ctx_map[state["sender"]]
        llm_messages: list[dict] = []
        for message in state["messages"]:
            if isinstance(message, dict):
                llm_messages.append(message)
                continue
            role = {
                "system": "system",
                "human": "user",
                "ai": "assistant",
                "tool": "tool",
            }.get(getattr(message, "type", ""), "user")
            converted = {"role": role, "content": getattr(message, "content", "")}
            if role == "assistant" and getattr(message, "tool_calls", None):
                converted["tool_calls"] = [
                    {
                        "id": call.get("id"),
                        "type": "function",
                        "function": {
                            "name": call.get("name"),
                            "arguments": json.dumps(call.get("args", {})),
                        },
                    }
                    for call in message.tool_calls
                ]
            if role == "tool":
                converted["tool_call_id"] = getattr(message, "tool_call_id", None)
                converted["name"] = getattr(message, "name", None)
            llm_messages.append(converted)
        response = self.llm.complete(
            llm_messages,
            role="agent",
            tools=self.registry.schemas(),
        )
        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        assistant_entry: dict = {"role": "assistant", "content": msg.content}
        if tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in tool_calls
            ]
        return {
            "messages": [assistant_entry],
            "sender": state["sender"],
            "pending_image": state["pending_image"],
        }

    def tool_node(self, state: AgentState) -> AgentState:
        ctx = self._ctx_map[state["sender"]]
        last_message = state["messages"][-1]
        tool_calls = (
            last_message.get("tool_calls")
            if isinstance(last_message, dict)
            else getattr(last_message, "tool_calls", None)
        ) or []
        new_messages: list[dict] = []

        for call in tool_calls:
            if isinstance(call, dict):
                function = call.get("function")
                if isinstance(function, dict):
                    name = function["name"]
                    arguments = function.get("arguments") or "{}"
                else:
                    name = call["name"]
                    arguments = call.get("args") or "{}"
                    if isinstance(arguments, dict):
                        arguments = json.dumps(arguments)
                call_id = call.get("id")
            else:
                name = call.function.name
                arguments = call.function.arguments or "{}"
                call_id = getattr(call, "id", None)
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError:
                args = {}

            if name in {"schedule_reminder", "log_adherence"}:
                confirmation = interrupt({"tool": name, "args": args})
                if isinstance(confirmation, str):
                    answer = confirmation.strip().lower()
                    if answer not in {"yes", "confirm", "ok"}:
                        new_messages.append(
                            {
                                "role": "assistant",
                                "content": "Cancelled. No reminder or adherence change was saved.",
                            }
                        )
                        return {
                            "messages": new_messages,
                            "sender": state["sender"],
                            "pending_image": state["pending_image"],
                        }
                    args = {**args, "confirm": True}
                else:
                    args = {**args, "confirm": True}

            tool = self.registry.get(name)
            result = tool.run(args, ctx) if tool else {"error": f"unknown tool '{name}'"}
            new_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": json.dumps(result, default=str),
                }
            )

        return {
            "messages": new_messages,
            "sender": state["sender"],
            "pending_image": state["pending_image"],
        }

    def handle(
        self,
        incoming: IncomingMessage,
        *,
        session: "Session",
        datasets: "Datasets",
        channel: "MessagingChannel",
        clock: "Clock",
        max_iters: int = MAX_ITERS,
        checkpointer=None,
    ) -> str:
        """Process one inbound message end-to-end and send the final reply."""
        ctx = ToolContext(
            sender=incoming.sender,
            session=session,
            llm=self.llm,
            datasets=datasets,
            clock=clock,
            channel=channel,
            pending_image=incoming.media_bytes,
        )
        self._ctx_map[incoming.sender] = ctx

        user_text = incoming.text or ""
        if incoming.has_image:
            user_text = (
                f"{user_text}\n[The patient sent a prescription image. Use run_ocr / "
                "extract_medications to read it.]"
            ).strip()

        initial_state: AgentState = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            "sender": incoming.sender,
            "pending_image": incoming.media_bytes,
        }

        try:
            if checkpointer is None:
                try:
                    db_url = str(session.get_bind().url)
                except Exception:
                    db_url = get_settings().database_url
                if db_url in ("sqlite://", "sqlite:///"):
                    conn_string = ":memory:"
                elif db_url.startswith("sqlite:///"):
                    conn_string = db_url[len("sqlite:///"):]
                else:
                    raise ValueError("LangGraph SQLite checkpointer requires a SQLite database URL")
                if conn_string not in self._checkpoint_connections:
                    self._checkpoint_connections[conn_string] = sqlite3.connect(
                        conn_string,
                        check_same_thread=False,
                    )
                checkpointer = SqliteSaver(self._checkpoint_connections[conn_string])
                cache_key = conn_string
            else:
                cache_key = str(checkpointer)

            if self._graph is None or self._graph_db_key != cache_key:
                self._graph = self._build_graph(checkpointer=checkpointer)
                self._graph_db_key = cache_key

            result = self._graph.invoke(
                initial_state,
                config={
                    "configurable": {"thread_id": incoming.sender},
                    "recursion_limit": max_iters,
                },
            )
            final_messages = result["messages"]
            reply = ""
            for message in reversed(final_messages):
                if isinstance(message, dict):
                    if message.get("role") == "assistant":
                        reply = message.get("content") or ""
                        break
                elif getattr(message, "type", None) == "ai":
                    reply = message.content or ""
                    break
            if not reply:
                reply = "Sorry — I couldn't finish that just now. Could you try again?"

            channel.send_text(incoming.sender, reply)
            return reply
        except Exception:
            fallback = "Sorry — I couldn't finish that just now. Could you try again?"
            channel.send_text(incoming.sender, fallback)
            return fallback
        finally:
            self._ctx_map.pop(incoming.sender, None)
