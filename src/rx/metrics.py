"""Turn one pipeline run into Prometheus metrics: pushed to a Pushgateway, or written for node_exporter's textfile
collector. Inputs are the files the run already writes, so the metrics cannot disagree with the reports.

- reports/pipeline-run.json   stage timings and status (scripts/run_pipeline.sh)
- dbt/target/run_results.json  dbt's own results: every model and test with its status
- reports/exports.json         rows per mart and the Hyper read-back check (`rx export`)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prometheus_client import CollectorRegistry, Gauge

JOB = "rx_pipeline"


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def dbt_summary(run_results: dict[str, Any]) -> dict[str, int]:
    """Counts by resource type and status, e.g. {"test_pass": 36, "test_fail": 0, "model_success": 11}."""
    out: dict[str, int] = {}
    for r in run_results.get("results", []):
        kind = r["unique_id"].split(".", 1)[0]
        key = f"{kind}_{r['status']}"
        out[key] = out.get(key, 0) + 1
    return out


def dbt_report(run_results: dict[str, Any]) -> dict[str, Any]:
    """What a reviewer needs from dbt's run_results.json: totals and the status and time of every node."""
    nodes = [
        {"node": r["unique_id"], "status": r["status"], "seconds": round(float(r.get("execution_time", 0.0)), 2)}
        for r in run_results.get("results", [])
    ]
    return {
        "generated_at": run_results.get("metadata", {}).get("generated_at"),
        "dbt_version": run_results.get("metadata", {}).get("dbt_version"),
        "elapsed_seconds": round(float(run_results.get("elapsed_time", 0.0)), 2),
        "counts": dbt_summary(run_results),
        "nodes": sorted(nodes, key=lambda n: n["node"]),
    }


def build_registry(
    run: dict[str, Any], dbt: dict[str, Any] | None, exports: dict[str, Any] | None
) -> CollectorRegistry:
    reg = CollectorRegistry()
    ok = run.get("status") == "success"
    Gauge("rx_pipeline_last_run_success", "1 if the last run finished, 0 if a stage failed", registry=reg).set(int(ok))
    Gauge("rx_pipeline_last_run_timestamp_seconds", "When the last run ended", registry=reg).set(
        run["finished_at_epoch"]
    )
    if ok:
        Gauge("rx_pipeline_last_success_timestamp_seconds", "When the last successful run ended", registry=reg).set(
            run["finished_at_epoch"]
        )
    stage = Gauge("rx_pipeline_stage_seconds", "Wall time per stage of the last run", ["stage"], registry=reg)
    for s in run.get("stages", []):
        stage.labels(s["name"]).set(s["seconds"])
    raw = Gauge(
        "rx_raw_rows",
        "Rows in the raw layer per dataset and year after the last load",
        ["dataset", "year"],
        registry=reg,
    )
    for load in run.get("loads", []):
        raw.labels(load["dataset"], str(load["year"])).set(load["rows"])

    if dbt is not None:
        summary = dbt_summary(dbt)
        failed = sum(v for k, v in summary.items() if k.endswith(("_fail", "_error")))
        Gauge("rx_dbt_failures", "dbt models and tests that failed or errored", registry=reg).set(failed)
        Gauge("rx_dbt_tests", "dbt tests run", registry=reg).set(
            sum(v for k, v in summary.items() if k.startswith("test_"))
        )
        Gauge("rx_dbt_elapsed_seconds", "dbt build wall time", registry=reg).set(dbt.get("elapsed_time", 0.0))

    if exports is not None:
        rows = Gauge("rx_export_rows", "Rows exported per mart", ["mart"], registry=reg)
        for mart, n in exports.get("marts", {}).items():
            rows.labels(mart.lower()).set(n)
        if "hyper" in exports:
            Gauge("rx_hyper_verified", "1 if the Tableau extract read back equal to the marts", registry=reg).set(
                int(bool(exports["hyper"].get("ok")))
            )
    return reg


def publish(
    run_report: Path,
    dbt_results: Path | None,
    exports_report: Path | None,
    *,
    pushgateway: str | None,
    textfile: Path | None,
    dbt_report_path: Path | None = None,
) -> CollectorRegistry:
    run = _load(run_report)
    if run is None:
        raise FileNotFoundError(run_report)
    dbt = _load(dbt_results)
    reg = build_registry(run, dbt, _load(exports_report))
    if dbt is not None and dbt_report_path is not None:
        dbt_report_path.parent.mkdir(parents=True, exist_ok=True)
        dbt_report_path.write_text(json.dumps(dbt_report(dbt), indent=2) + "\n", encoding="utf-8")
    if pushgateway:
        from prometheus_client import push_to_gateway

        push_to_gateway(pushgateway, job=JOB, registry=reg, timeout=10)
    if textfile:
        from prometheus_client import write_to_textfile

        textfile.parent.mkdir(parents=True, exist_ok=True)
        write_to_textfile(str(textfile), reg)
    return reg
