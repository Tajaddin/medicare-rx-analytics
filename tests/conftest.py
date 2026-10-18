"""Shared fixtures: a fakesnow server per test session (real Snowflake connector over HTTP, DuckDB underneath)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from rx.config import SnowflakeSettings

PAGES = Path(__file__).parent / "fixtures" / "pages"


def fixture_rows(dataset: str, year: int) -> int:
    return sum(
        len(json.loads(p.read_text(encoding="utf-8"))) for p in (PAGES / dataset / str(year)).glob("page-*.json")
    )


@pytest.fixture(scope="session")
def sf() -> Iterator[SnowflakeSettings]:
    import fakesnow

    with fakesnow.server() as kw:
        yield SnowflakeSettings(host=kw["host"], port=kw["port"], protocol=kw.get("protocol", "http"))


@pytest.fixture
def conn(sf: SnowflakeSettings) -> Iterator[Any]:
    from rx.warehouse import bootstrap, connect

    with connect(sf) as c:
        bootstrap(c, sf.database)
        yield c
