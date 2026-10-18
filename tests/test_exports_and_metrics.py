"""BI exports: Parquet/CSV and the Tableau Hyper extract with its read-back check."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from rx.exports import ExportResult, verify_hyper, write_files, write_hyper


@pytest.fixture
def frames() -> dict[str, pd.DataFrame]:
    return {
        "MART_DRUG_SPEND_TREND": pd.DataFrame(
            {
                "generic_name": ["Semaglutide", "Semaglutide", "Apixaban"],
                "data_year": [2023, 2024, 2024],
                "claims": [100, 150, 80],
                "drug_cost": [95000.5, 140000.25, 40000.0],
                "cost_growth_yoy": [float("nan"), 0.47, float("nan")],
            }
        ),
        "DIM_DRUG": pd.DataFrame({"brand_name": ["Ozempic"], "is_brand": [True], "fl_claims_all_years": [250]}),
    }


def test_files_and_manifest(frames: dict[str, pd.DataFrame], tmp_path: Path) -> None:
    results = write_files(frames, tmp_path)
    assert [r.rows for r in results] == [3, 1]
    assert pq.read_table(tmp_path / "mart_drug_spend_trend.parquet").num_rows == 3
    assert (tmp_path / "dim_drug.csv").read_text(encoding="utf-8").splitlines()[
        0
    ] == "brand_name,is_brand,fl_claims_all_years"
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["numeric_sums"]["claims"] == 330


def test_hyper_extract_reads_back_equal(frames: dict[str, pd.DataFrame], tmp_path: Path) -> None:
    results = write_files(frames, tmp_path)
    path = tmp_path / "rx.hyper"
    write_hyper(frames, path)
    report = verify_hyper(path, results)
    assert report["ok"], report
    assert report["tables"]["MART_DRUG_SPEND_TREND"]["rows"] == 3


def test_hyper_check_catches_a_difference(frames: dict[str, pd.DataFrame], tmp_path: Path) -> None:
    results = write_files(frames, tmp_path)
    path = tmp_path / "rx.hyper"
    write_hyper(frames, path)
    wrong = [ExportResult(r.mart, r.rows + (1 if r.mart == "DIM_DRUG" else 0), r.numeric_sums) for r in results]
    wrong[0].numeric_sums["drug_cost"] += 1.0
    report = verify_hyper(path, wrong)
    assert not report["ok"]
    assert report["tables"]["MART_DRUG_SPEND_TREND"]["mismatches"][0]["column"] == "drug_cost"
    assert not report["tables"]["DIM_DRUG"]["ok"]
