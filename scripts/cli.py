"""Local REPL to talk to MedBuddy in the terminal.

    python -m scripts.cli

Type messages as the "patient". To attach a prescription image, send a line like:
    img:D:\\MedBud\\data\\sample_prescriptions\\rx1.jpg

Requires LLM provider keys in .env (the agent model actually runs). For offline checks of
the deterministic tools, run the test suite instead (pytest).
"""
from __future__ import annotations

import sys

from medbuddy.agent import Agent
from medbuddy.channels import FakeChannel, IncomingMessage
from medbuddy.datasets.loaders import load_datasets
from medbuddy.db import SessionLocal, init_db
from medbuddy.llm import LLMClient
from medbuddy.scheduler.clock import RealClock


def main() -> None:
    # Windows consoles default to cp1252, which can't print the emoji in MedBuddy's replies.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    init_db()
    agent = Agent(LLMClient())
    channel = FakeChannel(echo=True)  # prints MedBuddy's replies
    datasets = load_datasets()
    clock = RealClock()
    sender = "cli:local"

    print("MedBuddy CLI — FakeChannel. Ctrl-C or 'quit' to exit.")
    print("Attach an image with:  img:<path-to-file>   |   /reset clears the chat\n")
    print("Proof-of-concept, not for clinical use.\n")

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in {"quit", "exit"}:
            break
        if line.lower() == "/reset":
            agent.reset(sender)
            print("(conversation cleared — saved meds/reminders are kept)\n")
            continue

        text: str | None = line
        media: bytes | None = None
        if line.startswith("img:"):
            path = line[4:].strip()
            try:
                with open(path, "rb") as f:
                    media = f.read()
            except OSError as err:
                print(f"! couldn't read {path}: {err}")
                continue
            text = "(the patient sent a prescription image)"

        incoming = IncomingMessage(sender=sender, text=text, media_bytes=media)
        with SessionLocal() as session:
            agent.handle(
                incoming, session=session, datasets=datasets, channel=channel, clock=clock
            )


if __name__ == "__main__":
    main()
