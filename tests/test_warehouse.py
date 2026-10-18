"""Bootstrap and load against the emulator, with the committed sample of real CMS pages."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from rx.warehouse import RAW_TABLES, bootstrap, load_year
from tests.conftest import PAGES, fixture_rows


def count(conn: Any, sql: str) -> int:
    cur = conn.cursor()
    cur.execute(sql)
    return int(cur.fetchone()[0])


def test_bootstrap_is_idempotent(conn: Any) -> None:
    bootstrap(conn, "RX")
    for table in RAW_TABLES.values():
        assert count(conn, f"select count(*) from RX.{table}") >= 0


def test_load_counts_rows_and_records_lineage(conn: Any) -> None:
    result = load_year(conn, "RX", "prescriber_drug", 2024, PAGES / "prescriber_drug" / "2024")
    expected = fixture_rows("prescriber_drug", 2024)
    assert result.rows == expected
    assert result.files == len(list((PAGES / "prescriber_drug" / "2024").glob("page-*.json")))
    cur = conn.cursor()
    cur.execute(
        "select data_year, source_file, count(*), count(loaded_at) from RX.RAW.PARTD_PRESCRIBER_DRUG "
        "where data_year = 2024 group by 1, 2"
    )
    assert cur.fetchall() == [(2024, "prescriber_drug/2024", expected, expected)]


def test_variant_fields_are_queryable(conn: Any) -> None:
    load_year(conn, "RX", "prescriber_drug", 2023, PAGES / "prescriber_drug" / "2023")
    cur = conn.cursor()
    cur.execute(
        "select count(*), count(distinct record:Prscrbr_NPI::string) from RX.RAW.PARTD_PRESCRIBER_DRUG "
        "where data_year = 2023 and record:Prscrbr_State_Abrvtn::string = 'FL'"
    )
    rows, npis = cur.fetchone()
    assert rows == fixture_rows("prescriber_drug", 2023)
    assert npis > 25  # 25 sampled prescribers plus the pinned edge-case products


def test_reloading_a_year_replaces_it_and_leaves_other_years(conn: Any) -> None:
    load_year(conn, "RX", "prescriber_drug", 2022, PAGES / "prescriber_drug" / "2022")
    load_year(conn, "RX", "prescriber_drug", 2023, PAGES / "prescriber_drug" / "2023")
    load_year(conn, "RX", "prescriber_drug", 2022, PAGES / "prescriber_drug" / "2022")
    table = "RX.RAW.PARTD_PRESCRIBER_DRUG"
    assert count(conn, f"select count(*) from {table} where data_year = 2022") == fixture_rows("prescriber_drug", 2022)
    assert count(conn, f"select count(*) from {table} where data_year = 2023") == fixture_rows("prescriber_drug", 2023)


def test_landing_table_is_dropped(conn: Any) -> None:
    load_year(conn, "RX", "spending_by_drug", 2024, PAGES / "spending_by_drug" / "2024")
    cur = conn.cursor()
    cur.execute("select count(*) from RX.information_schema.tables where table_name ilike 'LANDING_%'")
    assert cur.fetchone()[0] == 0


def test_page_paths_with_spaces_load(conn: Any, tmp_path: Path) -> None:
    pages = tmp_path / "with space" / "2024"
    shutil.copytree(PAGES / "spending_by_drug" / "2024", pages)
    result = load_year(conn, "RX", "spending_by_drug", 2024, pages)
    assert result.rows == fixture_rows("spending_by_drug", 2024)


@pytest.mark.parametrize(
    ("dataset", "year", "message"),
    [("prescribers; drop table x", 2024, "unknown dataset"), ("prescriber_drug", 1999, "implausible data year")],
)
def test_rejects_bad_arguments(conn: Any, dataset: str, year: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_year(conn, "RX", dataset, year, PAGES / "prescriber_drug" / "2024")


def test_rejects_a_folder_without_pages(conn: Any, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_year(conn, "RX", "prescriber_drug", 2024, tmp_path)


def test_rejects_quotes_in_page_paths(conn: Any, tmp_path: Path) -> None:
    pages = tmp_path / "it's" / "2024"
    shutil.copytree(PAGES / "spending_by_drug" / "2024", pages)
    with pytest.raises(ValueError, match="quote"):
        load_year(conn, "RX", "spending_by_drug", 2024, pages)


def test_fetch_mart_types_come_from_snowflake_metadata(conn: Any, tmp_path: Path) -> None:
    from rx.exports import fetch_mart, verify_hyper, write_files, write_hyper

    cur = conn.cursor()
    cur.execute(
        "create or replace table RX.ANALYTICS.TYPES_PROBE (n number(10, 0), price number(12, 4), ratio float, "
        "flag boolean, name varchar)"
    )
    cur.execute(
        "insert into RX.ANALYTICS.TYPES_PROBE values (1, 2.5000, 0.25, true, 'a'), (null, null, null, null, null)"
    )
    df = fetch_mart(conn, "RX", "TYPES_PROBE")
    assert [str(t) for t in df.dtypes] == ["Int64", "float64", "float64", "boolean", "object"]
    results = write_files({"TYPES_PROBE": df}, tmp_path)
    assert results[0].numeric_sums == {"n": 1.0, "price": 2.5, "ratio": 0.25}
    write_hyper({"TYPES_PROBE": df}, tmp_path / "probe.hyper")
    assert verify_hyper(tmp_path / "probe.hyper", results)["ok"]


def test_bootstrap_on_a_real_account_leaves_containers_to_terraform() -> None:
    executed: list[str] = []

    class Cursor:
        def execute(self, sql: str) -> None:
            executed.append(sql)

    class Conn:
        def cursor(self) -> Cursor:
            return Cursor()

    bootstrap(Conn(), "RX", create_containers=False)
    assert not any(sql.startswith(("create database", "create schema")) for sql in executed)
    assert any(sql.startswith("create stage") for sql in executed)
