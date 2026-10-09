"""The agent loop — MedBuddy's hybrid core implemented with LangGraph.

Graph:
  START -> prescription_node -> END     when the patient sent a photo (fixed pipeline,
                                         see agent/prescription.py — 1 LLM call)
  START -> agent_node <-> tool_node     everything else (LLM picks tools until it replies)

State-changing tools (schedule_reminder, log_adherence) are gated by `interrupt()`: the
graph pauses, the patient is asked to confirm on the next message, and `handle()` resumes
the paused graph with their reply via `Command(resume=...)`. Conversation state is
checkpointed per patient (thread_id = sender) in a dedicated SQLite file.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt

from medbuddy.agent.prescription import prescription_reply
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

STATE_CHANGING_TOOLS = {"schedule_reminder", "log_adherence"}
YES_WORDS = {"yes", "y", "confirm", "ok", "okay", "haan", "ha", "sure"}
FALLBACK_REPLY = "Sorry — I couldn't finish that just now. Could you try again?"


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    sender: str
    pending_image: bytes | None


def route_entry(state: AgentState) -> str:
    """Photos take the deterministic pipeline; text goes to the agent."""
    return "prescription_node" if state.get("pending_image") else "agent_node"


def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last = messages[-1] if messages else None
    return "tool_node" if _tool_calls_of(last) else END


def _tool_calls_of(message: Any) -> list:
    if message is None:
        return []
    if isinstance(message, dict):
        return message.get("tool_calls") or []
    return getattr(message, "tool_calls", None) or []


def _parse_call(call: Any) -> tuple[str, dict, str | None]:
    """(name, args, id) from either an OpenAI-style dict or a LangChain tool_call."""
    if isinstance(call, dict):
        function = call.get("function")
        if isinstance(function, dict):
            name, arguments = function["name"], function.get("arguments") or "{}"
        else:
            name, arguments = call["name"], call.get("args") or {}
        call_id = call.get("id")
    else:
        name, arguments = call.function.name, call.function.arguments or "{}"
        call_id = getattr(call, "id", None)
    if isinstance(arguments, dict):
        return name, arguments, call_id
    try:
        return name, json.loads(arguments), call_id
    except json.JSONDecodeError:
        return name, {}, call_id


def _describe_action(name: str, args: dict) -> str:
    """Human-readable line for the confirmation prompt."""
    if name == "schedule_reminder":
        times = ", ".join(args.get("times") or []) or "(no times given)"
        return f"• Daily reminders for {args.get('medication', 'your medicine')} at {times}"
    if name == "log_adherence":
        verb = {"taken": "took", "missed": "missed"}.get(args.get("response"), "?")
        return f"• Log that you {verb} your dose"
    return f"• {name}"


def _is_yes(reply: Any) -> bool:
    if isinstance(reply, bool):
        return reply
    words = str(reply or "").strip().lower().strip(".!").split()
    return bool(words) and words[0] in YES_WORDS


class Agent:
    def __init__(self, llm: "LLMClient", registry: ToolRegistry | None = None) -> None:
        self.llm = llm
        self.registry = registry or ToolRegistry()
        self._graph = None
        self._graph_db_key: str | None = None
        self._ctx_map: dict[str, ToolContext] = {}
        self._checkpoint_connections: dict[str, sqlite3.Connection] = {}

    def reset(self, sender: str) -> None:
        """Forget a patient's conversation (checkpointed chat state only, not DB records)."""
        if self._graph is not None and self._graph.checkpointer is not None:
            self._graph.checkpointer.delete_thread(sender)
            return
        conn = sqlite3.connect(get_settings().checkpoint_db, check_same_thread=False)
        try:
            SqliteSaver(conn).delete_thread(sender)
        finally:
            conn.close()

    def _build_graph(self, checkpointer=None):
        graph = StateGraph(AgentState)
        graph.add_node("agent_node", self.agent_node)
        graph.add_node("tool_node", self.tool_node)
        graph.add_node("prescription_node", self.prescription_node)
        graph.add_conditional_edges(
            START,
            route_entry,
            {"prescription_node": "prescription_node", "agent_node": "agent_node"},
        )
        graph.add_edge("prescription_node", END)
        graph.add_conditional_edges(
            "agent_node",
            should_continue,
            {"tool_node": "tool_node", END: END},
        )
        graph.add_edge("tool_node", "agent_node")
        return graph.compile(checkpointer=checkpointer)

    def agent_node(self, state: AgentState) -> AgentState:
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

        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
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

    def prescription_node(self, state: AgentState) -> AgentState:
        """Fixed photo pipeline. Its reply lands in history so the agent has context next turn."""
        ctx = self._ctx_map[state["sender"]]
        reply = prescription_reply(ctx)
        return {
            "messages": [{"role": "assistant", "content": reply}],
            "sender": state["sender"],
            "pending_image": None,
        }

    def tool_node(self, state: AgentState) -> AgentState:
        ctx = self._ctx_map[state["sender"]]
        calls = [_parse_call(c) for c in _tool_calls_of(state["messages"][-1])]

        # Ask for confirmation BEFORE running anything: on resume LangGraph re-executes this
        # node from the top, so tools must not have run yet when interrupt() fires. All
        # state-changing calls in this turn share one confirmation prompt.
        gated = [(name, args) for name, args, _ in calls if name in STATE_CHANGING_TOOLS]
        approved = True
        if gated:
            lines = "\n".join(_describe_action(name, args) for name, args in gated)
            reply = interrupt(
                {
                    "prompt": f"Please confirm:\n{lines}\n\nReply YES to confirm or NO to cancel.",
                    "actions": [{"tool": name, "args": args} for name, args in gated],
                }
            )
            approved = _is_yes(reply)

        new_messages: list[dict] = []
        for name, args, call_id in calls:
            if name in STATE_CHANGING_TOOLS:
                if approved:
                    args = {**args, "confirm": True}
                else:
                    result = {"status": "cancelled", "message": "Patient declined. Nothing saved."}
                    new_messages.append(self._tool_message(call_id, name, result))
                    continue
            tool = self.registry.get(name)
            try:
                result = tool.run(args, ctx) if tool else {"error": f"unknown tool '{name}'"}
            except Exception as err:  # noqa: BLE001 - a tool crash must not kill the turn
                result = {"error": f"{name} failed: {err}"}
            new_messages.append(self._tool_message(call_id, name, result))

        return {
            "messages": new_messages,
            "sender": state["sender"],
            "pending_image": state["pending_image"],
        }

    @staticmethod
    def _tool_message(call_id: str | None, name: str, result: dict) -> dict:
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": json.dumps(result, default=str),
        }

    def _ensure_graph(self, session: "Session", checkpointer=None) -> None:
        if checkpointer is None:
            try:
                db_url = str(session.get_bind().url)
            except Exception:
                db_url = get_settings().database_url
            # In-memory app DB (tests) -> in-memory checkpoints; otherwise a dedicated file.
            if db_url in ("sqlite://", "sqlite:///", "sqlite:///:memory:"):
                conn_string = ":memory:"
            else:
                conn_string = get_settings().checkpoint_db
            if conn_string not in self._checkpoint_connections:
                self._checkpoint_connections[conn_string] = sqlite3.connect(
                    conn_string,
                    check_same_thread=False,
                )
            checkpointer = SqliteSaver(self._checkpoint_connections[conn_string])
            cache_key = conn_string
        else:
            cache_key = str(id(checkpointer))

        if self._graph is None or self._graph_db_key != cache_key:
            self._graph = self._build_graph(checkpointer=checkpointer)
            self._graph_db_key = cache_key

    def handle(
        self,
        incoming: IncomingMessage,
        *,
        session: "Session",
        datasets: "Datasets",
        channel: "MessagingChannel",
        clock: "Clock",
        max_iters: int | None = None,
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
        config = {
            "configurable": {"thread_id": incoming.sender},
            "recursion_limit": max_iters or get_settings().agent_recursion_limit,
        }

        try:
            self._ensure_graph(session, checkpointer)
            snapshot = self._graph.get_state(config)

            if snapshot.interrupts:
                # The patient is answering a confirmation prompt -> resume the paused graph.
                graph_input: Any = Command(resume=incoming.text or "")
            else:
                user_text = incoming.text or ""
                if incoming.has_image:
                    user_text = f"{user_text}\n[The patient sent a prescription image.]".strip()
                new_messages: list[dict] = []
                if not snapshot.values.get("messages"):
                    new_messages.append({"role": "system", "content": SYSTEM_PROMPT})
                new_messages.append({"role": "user", "content": user_text})
                graph_input = {
                    "messages": new_messages,
                    "sender": incoming.sender,
                    "pending_image": incoming.media_bytes,
                }

            result = self._graph.invoke(graph_input, config=config)
            reply = self._reply_from(result)
        except Exception:
            import traceback

            traceback.print_exc()
            self._discard_dangling_tool_calls(config)
            reply = FALLBACK_REPLY
        finally:
            self._ctx_map.pop(incoming.sender, None)

        channel.send_text(incoming.sender, reply)
        return reply

    @staticmethod
    def _reply_from(result: dict) -> str:
        interrupts = result.get("__interrupt__") or []
        if interrupts:
            value = interrupts[0].value
            return value.get("prompt", str(value)) if isinstance(value, dict) else str(value)
        for message in reversed(result["messages"]):
            if isinstance(message, dict):
                if message.get("role") == "assistant" and message.get("content"):
                    return message["content"]
            elif getattr(message, "type", None) == "ai" and message.content:
                content = message.content
                if isinstance(content, list):  # some providers return content parts
                    content = " ".join(
                        p.get("text", "") if isinstance(p, dict) else str(p) for p in content
                    )
                return content
            elif getattr(message, "type", None) == "human":
                break
        return FALLBACK_REPLY

    def _discard_dangling_tool_calls(self, config: dict) -> None:
        """After a failed turn, make sure history doesn't end in unanswered tool calls.

        Providers reject a conversation where an assistant tool call has no tool response,
        which would poison every later turn for this patient. Answer them with an error.
        """
        if self._graph is None:
            return
        try:
            snapshot = self._graph.get_state(config)
            messages = snapshot.values.get("messages") or []
            if snapshot.interrupts or not messages:
                return
            calls = _tool_calls_of(messages[-1])
            if not calls:
                return
            fixes = [
                self._tool_message(call_id, name, {"error": "turn aborted; not executed"})
                for name, _, call_id in (_parse_call(c) for c in calls)
            ]
            self._graph.update_state(config, {"messages": fixes}, as_node="tool_node")
        except Exception:  # noqa: BLE001 - best effort cleanup
            pass
