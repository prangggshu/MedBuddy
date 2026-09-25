from __future__ import annotations

from typing import Any

from medbuddy.tools.base import Tool, ToolContext


class RunOcrTool(Tool):
    name = "run_ocr"
    description = "Extract raw text from a prescription image using vision AI. Call this when the patient sends a photo."
    parameters = {"type": "object", "properties": {}}

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if ctx.pending_image is None:
            return {"error": "no image provided"}
        result = run_ocr(ctx.pending_image, ctx=ctx)
        return {"text": result}


def run_ocr(image_bytes: bytes, mime: str = "image/png", *, ctx: ToolContext) -> str:
    """Use the vision-capable LLM to transcribe a prescription image as raw text."""
    if ctx.llm is None:
        raise ValueError("ctx.llm is required to run OCR")

    prompt = (
        "You are a prescription transcriber. Extract all text exactly as printed. "
        "Do not correct spelling, do not interpret, do not add commentary. "
        "Return only the raw text."
    )
    message = ctx.llm.image_message(
        prompt,
        image_bytes=image_bytes,
        mime=mime,
    )
    response = ctx.llm.complete([message], role="vision")
    return response.choices[0].message.content.strip()
