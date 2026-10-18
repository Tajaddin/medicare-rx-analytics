"""Write the Grafana dashboard for the batch pipeline (observability/grafana/dashboards/rx-pipeline.json).

    python scripts/make_dashboard.py

Every panel reads a metric `rx metrics` pushes after a run; generating the JSON keeps the panels consistent.
"""

from __future__ import annotations

import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}
OUT = Path(__file__).resolve().parents[1] / "observability/grafana/dashboards/rx-pipeline.json"
GREEN = {"mode": "absolute", "steps": [{"color": "green", "value": None}]}
OK_IS_ONE = {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}
STATUS = [
    {"type": "value", "options": {"0": {"text": "failed", "color": "red"}, "1": {"text": "ok", "color": "green"}}}
]
BARS = {"orientation": "horizontal", "displayMode": "basic"}


def red_above(limit: float) -> dict:
    return {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": limit}]}


def panel(pid: int, title: str, kind: str, expr: str, pos: tuple[int, int, int, int], **opts: object) -> dict:
    """pos = (x, y, width, height) on Grafana's 24-column grid."""
    x, y, w, h = pos
    defaults: dict = {"unit": opts.pop("unit", "short"), "thresholds": opts.pop("thresholds", GREEN)}
    if "mappings" in opts:
        defaults["mappings"] = opts.pop("mappings")
    if "decimals" in opts:
        defaults["decimals"] = opts.pop("decimals")
    legend = opts.pop("legend", "")
    return {
        "id": pid,
        "title": title,
        "type": kind,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"refId": "A", "datasource": DS, "expr": expr, "legendFormat": legend}],
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": opts.pop("options", {}),
    }


panels = [
    panel(1, "Last run", "stat", "rx_pipeline_last_run_success", (0, 0, 6, 4), mappings=STATUS, thresholds=OK_IS_ONE),
    panel(
        2,
        "Hours since the last successful run",
        "stat",
        "(time() - rx_pipeline_last_success_timestamp_seconds) / 3600",
        (6, 0, 6, 4),
        unit="h",
        decimals=1,
        thresholds=red_above(192),
    ),
    panel(3, "dbt failures in the last run", "stat", "rx_dbt_failures", (12, 0, 6, 4), thresholds=red_above(1)),
    panel(
        4,
        "Tableau extract matches the marts",
        "stat",
        "rx_hyper_verified",
        (18, 0, 6, 4),
        mappings=STATUS,
        thresholds=OK_IS_ONE,
    ),
    panel(
        5,
        "Seconds per stage",
        "bargauge",
        "rx_pipeline_stage_seconds",
        (0, 4, 12, 8),
        unit="s",
        legend="{{stage}}",
        options=BARS,
    ),
    panel(
        6, "Raw rows per dataset and year", "timeseries", "rx_raw_rows", (12, 4, 12, 8), legend="{{dataset}} {{year}}"
    ),
    panel(7, "Rows exported per mart", "bargauge", "rx_export_rows", (0, 12, 12, 8), legend="{{mart}}", options=BARS),
    panel(8, "dbt tests run and build time", "timeseries", "rx_dbt_tests", (12, 12, 12, 8), legend="tests"),
]
panels[-1]["targets"].append(
    {"refId": "B", "datasource": DS, "expr": "rx_dbt_elapsed_seconds", "legendFormat": "build seconds"}
)

dashboard = {
    "uid": "rx-pipeline",
    "title": "Medicare Rx: batch pipeline",
    "schemaVersion": 41,
    "version": 1,
    "refresh": "1m",
    "time": {"from": "now-30d", "to": "now"},
    "tags": ["rx"],
    "timezone": "utc",
    "panels": panels,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(dashboard, indent=1) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {OUT.name}: {len(panels)} panels")
