"""`rx <command>`: emulator, plan, bootstrap, load."""

from __future__ import annotations

import json
import logging
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import structlog
import typer

from rx.config import get_settings, get_snowflake

app = typer.Typer(no_args_is_help=True, add_completion=False)


class Dataset(StrEnum):
    prescriber_drug = "prescriber_drug"
    spending_by_drug = "spending_by_drug"


@app.callback()
def main(log_level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, level=log_level, format="%(message)s")
    for noisy in ("snowflake", "urllib3", "botocore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level)),
    )


@app.command()
def emulator(port: int = 8085, host: str = "127.0.0.1") -> None:
    """Run the local Snowflake emulator (fakesnow, DuckDB underneath) until stopped.

    Everything lives in memory: fakesnow's server mode ignores its -d option. Three Florida years take about
    as much memory as noted in docs/RUNBOOK.md; restart the emulator before reloading every year."""
    import subprocess

    raise typer.Exit(subprocess.call(["fakesnow", "-s", "-p", str(port), "--host", host]))


@app.command()
def plan() -> None:
    """Print what the pipeline extracts and loads, one tab-separated line per dataset-year:
    dataset, data year, CMS dataset id, state filter ("-" for national data)."""
    from rx.config import PRESCRIBER_DRUG_DATASETS, SPENDING_BY_DRUG_DATASET, SPENDING_RELEASE_YEAR

    settings = get_settings()
    for year in settings.year_list():
        if year not in PRESCRIBER_DRUG_DATASETS:
            raise typer.BadParameter(f"no CMS dataset id for {year}; known: {sorted(PRESCRIBER_DRUG_DATASETS)}")
        typer.echo(f"prescriber_drug	{year}	{PRESCRIBER_DRUG_DATASETS[year]}	{settings.state}")
    typer.echo(f"spending_by_drug	{SPENDING_RELEASE_YEAR}	{SPENDING_BY_DRUG_DATASET}	-")


@app.command()
def bootstrap() -> None:
    """Create the stage and raw tables, plus the database and schemas on the emulator (idempotent).
    On a real account Terraform creates the database and schemas and grants the pipeline role what it needs."""
    from rx.warehouse import bootstrap as run
    from rx.warehouse import connect

    sf = get_snowflake()
    with connect(sf) as conn:
        run(conn, sf.database, create_containers=sf.is_emulator)
    typer.echo(f"bootstrapped {sf.database} on {'the emulator' if sf.is_emulator else sf.account}")


@app.command()
def load(
    dataset: Annotated[Dataset, typer.Option(help="which CMS dataset the pages hold")],
    year: Annotated[int, typer.Option(min=2013, max=2100, help="data year the pages belong to")],
    pages: Annotated[
        Path, typer.Option(exists=True, file_okay=False, help="folder with page-*.json from extract_cms.sh")
    ],
) -> None:
    """Load one dataset-year of extracted pages into RAW (replaces that year)."""
    from rx.warehouse import connect, load_year

    sf = get_snowflake()
    with connect(sf) as conn:
        result = load_year(conn, sf.database, dataset.value, year, pages)
    typer.echo(json.dumps(result.__dict__))


if __name__ == "__main__":
    app()
