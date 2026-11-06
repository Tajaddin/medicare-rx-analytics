"""Snowflake: connections, the raw layer, and loading extracted JSON pages.

Raw layer: one table per CMS dataset, one VARIANT `record` per row plus load metadata. Loading is
PUT (to an internal stage) -> COPY INTO a transient landing table -> INSERT into raw with the data year and the
file name, inside one transaction per year. Re-loading a year deletes that year first, so a load is idempotent.
Each load stages its pages in a folder of its own and COPY purges them once loaded, so no file an earlier load left
on the stage (more pages, or a load that failed) can be copied again.

The same statements run on a Snowflake account and on the local emulator (fakesnow), which does not support
COPY INTO with a transform, FILES on an internal stage, or REMOVE; the landing-table step and the per-load folder
are what keep one code path for both.
"""

from __future__ import annotations

import json
import time
import uuid
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


def _pages(page_dir: Path) -> tuple[list[Path], int | None]:
    """The pages to load and the rows they hold. With the manifest.json extract_cms.sh writes, exactly the pages it
    lists (any other page-*.json is left over from an older extract); without one, every page-*.json."""
    manifest = page_dir / "manifest.json"
    if not manifest.exists():
        return sorted(page_dir.glob("page-*.json")), None
    extract = json.loads(manifest.read_text(encoding="utf-8"))
    if extract.get("rows") is None:
        raise RuntimeError(f"the extract in {page_dir} is not finished; run extract_cms.sh again")
    pages = [page_dir / f"page-{i:05d}.json" for i in range(int(extract["pages"]))]
    missing = [p.name for p in pages if not p.exists()]
    if missing:
        raise FileNotFoundError(f"{page_dir}: manifest.json lists {len(missing)} missing pages, e.g. {missing[0]}")
    return pages, int(extract["rows"])


def load_year(conn: Any, database: str, dataset: str, year: int, page_dir: Path) -> LoadResult:
    """Load the pages of one dataset-year (see `_pages`); replaces what was loaded for that year before."""
    if dataset not in RAW_TABLES:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {sorted(RAW_TABLES)}")
    if not 2000 <= year <= 2100:
        raise ValueError(f"implausible data year {year}")
    table = f"{database}.{RAW_TABLES[dataset]}"
    landing = f"{database}.RAW.LANDING_{dataset.upper()}_{year}"
    pages, extracted = _pages(page_dir)
    if not pages:
        raise FileNotFoundError(f"no pages in {page_dir}")
    start = time.perf_counter()
    cur = conn.cursor()
    cur.execute(f"create or replace transient table {landing} (record variant)")
    try:
        stage_dir = f"@{database}.RAW.LANDING/{dataset}/{year}/{uuid.uuid4().hex}/"
        for page in pages:
            cur.execute(f"put {_file_uri(page)} {stage_dir} auto_compress = true overwrite = true")
        cur.execute(
            f"copy into {landing} from {stage_dir} file_format = (type = json strip_outer_array = true) purge = true"
        )
        copied = sum(int(row[2]) for row in cur.fetchall())
        if extracted is not None and copied != extracted:
            raise RuntimeError(f"{dataset} {year}: copied {copied} rows but the extract holds {extracted}")
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
    finally:
        cur.execute(f"drop table if exists {landing}")
    cur.execute(f"select count(*) from {table} where data_year = {int(year)}")
    rows = int(cur.fetchone()[0])
    if rows != copied:
        raise RuntimeError(f"{dataset} {year}: copied {copied} rows but raw holds {rows}")
    result = LoadResult(dataset, year, len(pages), rows, round(time.perf_counter() - start, 2))
    log.info("loaded", **result.__dict__)
    return result
