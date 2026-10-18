"""Snowflake: connections, the raw layer, and loading extracted JSON pages.

Raw layer: one table per CMS dataset, one VARIANT `record` per row plus load metadata. Loading is
PUT (to an internal stage) -> COPY INTO a transient landing table -> INSERT into raw with the data year and the
file name, inside one transaction per year. Re-loading a year deletes that year first, so a load is idempotent.

The same statements run on a Snowflake account and on the local emulator (fakesnow), which does not support
COPY INTO with a transform or REMOVE; the landing-table step is what keeps one code path for both.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from rx.config import SnowflakeSettings

log = structlog.get_logger(__name__)

RAW_TABLES = {
    "prescriber_drug": "RAW.PARTD_PRESCRIBER_DRUG",
    "spending_by_drug": "RAW.PARTD_SPENDING_BY_DRUG",
}

# On a real account Terraform owns the database and schemas (infra/terraform); on the emulator bootstrap makes them.
CONTAINERS = [
    "create database if not exists {db}",
    "create schema if not exists {db}.RAW",
    "create schema if not exists {db}.ANALYTICS",
]
BOOTSTRAP = [
    "create stage if not exists {db}.RAW.LANDING file_format = (type = json strip_outer_array = true)",
    *[
        f"create table if not exists {{db}}.{table} (record variant, data_year number(4), source_file varchar, "
        "loaded_at timestamp_ntz)"
        for table in RAW_TABLES.values()
    ],
]


def connect(settings: SnowflakeSettings) -> Any:
    import snowflake.connector

    return snowflake.connector.connect(**settings.connect_kwargs())


def bootstrap(conn: Any, database: str, create_containers: bool = True) -> None:
    cur = conn.cursor()
    for sql in (CONTAINERS if create_containers else []) + BOOTSTRAP:
        cur.execute(sql.format(db=database))


@dataclass
class LoadResult:
    dataset: str
    year: int
    files: int
    rows: int
    seconds: float


def _file_uri(page: Path) -> str:
    """Quoted file URI for PUT (paths may contain spaces); a quote in the path itself is refused."""
    path = page.resolve().as_posix()
    if "'" in path:
        raise ValueError(f"page path contains a quote: {path}")
    return f"'file://{path}'"


def load_year(conn: Any, database: str, dataset: str, year: int, page_dir: Path) -> LoadResult:
    """Load every page-*.json of one dataset-year; replaces what was loaded for that year before."""
    if dataset not in RAW_TABLES:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {sorted(RAW_TABLES)}")
    if not 2000 <= year <= 2100:
        raise ValueError(f"implausible data year {year}")
    table = f"{database}.{RAW_TABLES[dataset]}"
    landing = f"{database}.RAW.LANDING_{dataset.upper()}_{year}"
    pages = sorted(page_dir.glob("page-*.json"))
    if not pages:
        raise FileNotFoundError(f"no pages in {page_dir}")
    start = time.perf_counter()
    cur = conn.cursor()
    cur.execute(f"create or replace transient table {landing} (record variant)")
    stage_dir = f"@{database}.RAW.LANDING/{dataset}/{year}"
    for page in pages:
        cur.execute(f"put {_file_uri(page)} {stage_dir} auto_compress = true overwrite = true")
    cur.execute(f"copy into {landing} from {stage_dir} file_format = (type = json strip_outer_array = true)")
    copied = sum(int(row[2]) for row in cur.fetchall())
    cur.execute("begin")
    try:
        cur.execute(f"delete from {table} where data_year = {int(year)}")
        cur.execute(
            f"insert into {table} (record, data_year, source_file, loaded_at) "
            f"select record, {int(year)}, '{dataset}/{year}', current_timestamp() from {landing}"
        )
        cur.execute("commit")
    except Exception:
        cur.execute("rollback")
        raise
    cur.execute(f"drop table if exists {landing}")
    cur.execute(f"select count(*) from {table} where data_year = {int(year)}")
    rows = int(cur.fetchone()[0])
    if rows != copied:
        raise RuntimeError(f"{dataset} {year}: copied {copied} rows but raw holds {rows}")
    result = LoadResult(dataset, year, len(pages), rows, round(time.perf_counter() - start, 2))
    log.info("loaded", **result.__dict__)
    return result
