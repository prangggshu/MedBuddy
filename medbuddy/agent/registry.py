"""Maps tool names -> Tool instances, and exposes their schemas to the LLM."""
from __future__ import annotations

from medbuddy.tools import Tool, default_tools


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self.tools = tools if tools is not None else default_tools()
        self._by_name = {t.name: t for t in self.tools}

    def schemas(self) -> list[dict]:
        """Function-calling specs handed to the model on every turn."""
        return [t.schema() for t in self.tools]

    def get(self, name: str) -> Tool | None:
        return self._by_name.get(name)
