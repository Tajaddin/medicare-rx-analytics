"""Publish the marts for BI: Parquet and CSV for Power BI, a Tableau .hyper extract built with the Hyper API.

Both are written from the same query results, and `verify_hyper` reads the extract back and compares row counts
and column sums with the marts, so the BI layer cannot silently drift from the warehouse.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

log = structlog.get_logger(__name__)

# Marts the BI tools read, in the order a report needs them.
MARTS = (
    "MART_DRUG_SPEND_TREND",
    "MART_SPECIALTY_CLASS_YEAR",
    "MART_GENERIC_OPPORTUNITY",
    "MART_OPIOID_BY_CITY",
    "MART_GLP1_GROWTH",
    "DIM_DRUG",
)


@dataclass
class ExportResult:
    mart: str
    rows: int
    numeric_sums: dict[str, float]


def fetch_mart(conn: Any, database: str, mart: str) -> pd.DataFrame:
    """One mart as a DataFrame with types from Snowflake's metadata, not from the Python values: the connector
    returns NUMBER(p, s>0) as Decimal objects, which would otherwise become text columns in the extract."""
    from snowflake.connector.constants import FIELD_ID_TO_NAME

    cur = conn.cursor()
    cur.execute(f"select * from {database}.ANALYTICS.{mart}")
    df = pd.DataFrame(cur.fetchall(), columns=[d.name.lower() for d in cur.description])
    for col, d in zip(df.columns, cur.description, strict=True):
        kind = FIELD_ID_TO_NAME[d.type_code]
        if kind == "FIXED" and not d.scale:
            df[col] = pd.array([None if pd.isna(v) else int(v) for v in df[col]], dtype="Int64")
        elif kind in ("FIXED", "REAL"):
            df[col] = pd.to_numeric(df[col]).astype("float64")
        elif kind == "BOOLEAN":
            df[col] = df[col].astype("boolean")
    return df


def _sums(df: pd.DataFrame) -> dict[str, float]:
    out = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
            out[col] = float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    return out


def write_files(frames: dict[str, pd.DataFrame], out_dir: Path) -> list[ExportResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for mart, df in frames.items():
        name = mart.lower()
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
        df.to_csv(out_dir / f"{name}.csv", index=False)
        results.append(ExportResult(mart, len(df), _sums(df)))
    (out_dir / "manifest.json").write_text(json.dumps([asdict(r) for r in results], indent=2) + "\n", encoding="utf-8")
    return results


def _hyper_type(series: pd.Series) -> Any:
    from tableauhyperapi import SqlType

    if pd.api.types.is_integer_dtype(series):
        return SqlType.big_int()
    if pd.api.types.is_float_dtype(series):
        return SqlType.double()
    if pd.api.types.is_bool_dtype(series):
        return SqlType.bool()
    return SqlType.text()


def _hyper_params(path: Path) -> dict[str, str]:
    """Hyper writes hyperd.log to the working directory unless told otherwise; keep it next to the extract."""
    return {"log_dir": str(path.parent.resolve())}


def _plain(value: Any) -> Any:
    """Python value the Hyper inserter accepts: None for every kind of missing, built-ins for numpy scalars."""
    if value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value)):
        return None
    return value.item() if hasattr(value, "item") else value


def write_hyper(frames: dict[str, pd.DataFrame], path: Path) -> None:
    """One .hyper file with one table per mart in schema Extract (what Tableau opens by default)."""
    from tableauhyperapi import (
        Connection,
        CreateMode,
        HyperProcess,
        Inserter,
        TableDefinition,
        TableName,
        Telemetry,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters=_hyper_params(path)) as hyper,
        Connection(hyper.endpoint, str(path), CreateMode.CREATE_AND_REPLACE) as conn,
    ):
        conn.catalog.create_schema_if_not_exists("Extract")
        for mart, df in frames.items():
            table = TableDefinition(
                TableName("Extract", mart.lower()),
                [TableDefinition.Column(c, _hyper_type(df[c])) for c in df.columns],
            )
            conn.catalog.create_table(table)
            rows = [[_plain(v) for v in r] for r in df.astype(object).itertuples(index=False, name=None)]
            with Inserter(conn, table) as inserter:
                inserter.add_rows(rows)
                inserter.execute()
    log.info("hyper_written", path=str(path), tables=len(frames))


def verify_hyper(path: Path, expected: list[ExportResult]) -> dict[str, Any]:
    """Read the extract back: same row count and the same column sums (to 1e-6 relative) for every mart."""
    from tableauhyperapi import Connection, HyperProcess, TableName, Telemetry

    report: dict[str, Any] = {"path": str(path.name), "tables": {}, "ok": True}
    with (
        HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters=_hyper_params(path)) as hyper,
        Connection(hyper.endpoint, str(path)) as conn,
    ):
        for exp in expected:
            table = TableName("Extract", exp.mart.lower())
            rows = int(conn.execute_scalar_query(f"SELECT COUNT(*) FROM {table}"))
            mismatches = []
            for col, want in exp.numeric_sums.items():
                got = conn.execute_scalar_query(f'SELECT SUM("{col}") FROM {table}')
                got = float(got or 0.0)
                if not math.isclose(got, want, rel_tol=1e-6, abs_tol=1e-6):
                    mismatches.append({"column": col, "mart": want, "hyper": got})
            ok = rows == exp.rows and not mismatches
            report["tables"][exp.mart] = {"rows": rows, "expected_rows": exp.rows, "mismatches": mismatches, "ok": ok}
            report["ok"] = report["ok"] and ok
    return report
