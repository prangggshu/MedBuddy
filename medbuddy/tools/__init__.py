"""The MedBuddy tool catalog.

Every capability the agent can invoke is registered here. `default_tools()` is the single
source of truth consumed by the agent registry.
"""
from __future__ import annotations

from medbuddy.tools.adherence import LogAdherenceTool
from medbuddy.tools.base import Tool, ToolContext
from medbuddy.tools.drug_info import LookupDrugInfoTool
from medbuddy.tools.extract import ExtractMedicationsTool
from medbuddy.tools.interactions import CheckInteractionsTool
from medbuddy.tools.normalize import NormalizeDrugTool
from medbuddy.tools.ocr import RunOcrTool
from medbuddy.tools.patient import GetMyMedsTool, RegisterPatientTool
from medbuddy.tools.reminders import ScheduleReminderTool


def default_tools() -> list[Tool]:
    return [
        RunOcrTool(),
        ExtractMedicationsTool(),
        NormalizeDrugTool(),
        CheckInteractionsTool(),
        LookupDrugInfoTool(),
        ScheduleReminderTool(),
        LogAdherenceTool(),
        RegisterPatientTool(),
        GetMyMedsTool(),
    ]


__all__ = ["Tool", "ToolContext", "default_tools"]
