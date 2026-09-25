"""Orchestration (layer-2) test: the loop executes tool calls and sends a grounded reply.

Uses a scripted fake LLM so it runs offline with zero credits. This is the pattern the
report's 'orchestration success' metric is built on: given an inbound message, did the agent
call the right tool and surface the finding?
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from medbuddy.agent import Agent
from medbuddy.channels import IncomingMessage


def _tool_call(call_id: str, name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _response(content=None, tool_calls=None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class ScriptedLLM:
    """Returns pre-baked responses in order; records every messages payload it saw."""

    def __init__(self, script: list[SimpleNamespace]) -> None:
        self._script = list(script)
        self.turns: list[list[dict]] = []

    def complete(self, messages, *, role="agent", tools=None, **kwargs):
        self.turns.append(messages)
        return self._script.pop(0)


def test_agent_runs_tool_then_replies(session, datasets, clock, channel):
    # Turn 1: model asks to check an interaction. Turn 2: model writes the final reply.
    llm = ScriptedLLM(
        [
            _response(tool_calls=[_tool_call("c1", "check_interactions",
                                             {"drugs": ["aspirin", "ibuprofen"]})]),
            _response(content="Heads up: aspirin + ibuprofen is a moderate interaction. "
                              "(Proof-of-concept, not for clinical use.)"),
        ]
    )
    agent = Agent(llm)  # type: ignore[arg-type]

    incoming = IncomingMessage(sender="test:+1", text="I take aspirin and ibuprofen, ok?")
    reply = agent.handle(
        incoming, session=session, datasets=datasets, channel=channel, clock=clock
    )

    assert "moderate" in reply.lower()
    assert channel.last().text == reply  # it was actually sent over the channel
    assert len(llm.turns) == 2  # a full tool round-trip happened

    # The second model turn must have received the tool's result as a 'tool' message.
    second_turn = llm.turns[1]
    tool_msgs = [m for m in second_turn if m.get("role") == "tool"]
    assert tool_msgs and "moderate" in tool_msgs[0]["content"].lower()
