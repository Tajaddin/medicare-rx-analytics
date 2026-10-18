"""BI exports (Parquet/CSV and the Tableau Hyper extract with read-back) and the Prometheus metrics of a run."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from rx.exports import ExportResult, verify_hyper, write_files, write_hyper
from rx.metrics import build_registry, dbt_summary, publish


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


RUN = {
    "status": "success",
    "failed_stage": None,
    "finished_at_epoch": 1_760_000_000,
    "stages": [{"name": "load", "seconds": 160.9}, {"name": "dbt", "seconds": 74.2}],
    "loads": [{"dataset": "prescriber_drug", "year": 2024, "rows": 2048452}],
}
DBT = {
    "elapsed_time": 73.4,
    "results": [
        {"unique_id": "model.rx.dim_drug", "status": "success"},
        {"unique_id": "test.rx.unique_x", "status": "pass"},
        {"unique_id": "test.rx.between_y", "status": "fail"},
    ],
}


def sample(reg, name: str, **labels: str) -> float | None:  # type: ignore[no-untyped-def]
    return reg.get_sample_value(name, labels or None)


def test_dbt_summary_counts_by_type_and_status() -> None:
    assert dbt_summary(DBT) == {"model_success": 1, "test_pass": 1, "test_fail": 1}


def test_registry_from_a_successful_run() -> None:
    reg = build_registry(RUN, DBT, {"marts": {"DIM_DRUG": 12}, "hyper": {"ok": True}})
    assert sample(reg, "rx_pipeline_last_run_success") == 1
    assert sample(reg, "rx_pipeline_last_success_timestamp_seconds") == 1_760_000_000
    assert sample(reg, "rx_pipeline_stage_seconds", stage="dbt") == 74.2
    assert sample(reg, "rx_raw_rows", dataset="prescriber_drug", year="2024") == 2048452
    assert sample(reg, "rx_dbt_failures") == 1
    assert sample(reg, "rx_dbt_tests") == 2
    assert sample(reg, "rx_export_rows", mart="dim_drug") == 12
    assert sample(reg, "rx_hyper_verified") == 1


def test_a_failed_run_has_no_success_timestamp() -> None:
    reg = build_registry({**RUN, "status": "failed", "failed_stage": "dbt"}, None, None)
    assert sample(reg, "rx_pipeline_last_run_success") == 0
    assert sample(reg, "rx_pipeline_last_success_timestamp_seconds") is None


def test_publish_writes_a_textfile(tmp_path: Path) -> None:
    run = tmp_path / "run.json"
    run.write_text(json.dumps(RUN), encoding="utf-8")
    out = tmp_path / "textfile" / "rx.prom"
    publish(run, tmp_path / "missing.json", None, pushgateway=None, textfile=out)
    text = out.read_text(encoding="utf-8")
    assert 'rx_pipeline_stage_seconds{stage="load"} 160.9' in text
    assert "rx_dbt_failures" not in text  # no dbt results, no dbt metrics


def test_publish_writes_the_dbt_report(tmp_path: Path) -> None:
    run, dbt = tmp_path / "run.json", tmp_path / "run_results.json"
    run.write_text(json.dumps(RUN), encoding="utf-8")
    dbt.write_text(json.dumps({**DBT, "metadata": {"dbt_version": "1.12.6"}}), encoding="utf-8")
    publish(run, dbt, None, pushgateway=None, textfile=None, dbt_report_path=tmp_path / "dbt-build.json")
    report = json.loads((tmp_path / "dbt-build.json").read_text(encoding="utf-8"))
    assert report["counts"] == {"model_success": 1, "test_pass": 1, "test_fail": 1}
    assert report["dbt_version"] == "1.12.6"
    assert report["nodes"][0]["node"] == "model.rx.dim_drug"


def test_publish_needs_the_run_report(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        publish(tmp_path / "none.json", None, None, pushgateway=None, textfile=None)
