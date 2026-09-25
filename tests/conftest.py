"""Shared fixtures: real datasets, an in-memory DB, a frozen clock, and a tool context."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from medbuddy.channels import FakeChannel
from medbuddy.datasets.loaders import load_datasets
from medbuddy.db.models import Base
from medbuddy.scheduler.clock import FakeClock
from medbuddy.tools.base import ToolContext


@pytest.fixture(scope="session")
def datasets():
    return load_datasets()  # reads the repo's data/ dir


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection => the in-memory DB persists for the test
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with Session() as s:
        yield s


@pytest.fixture
def clock():
    return FakeClock(datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))


@pytest.fixture
def channel():
    return FakeChannel()


@pytest.fixture
def ctx(session, datasets, clock, channel):
    # llm is None: the deterministic tools under test don't call it.
    return ToolContext(
        sender="test:+10000000000",
        session=session,
        llm=None,  # type: ignore[arg-type]
        datasets=datasets,
        clock=clock,
        channel=channel,
    )
