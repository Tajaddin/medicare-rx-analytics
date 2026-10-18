#!/usr/bin/env bash
# The whole batch, timed per stage: extract -> bootstrap -> load -> dbt build -> export -> metrics.
#
#   scripts/run_pipeline.sh                  extract from the CMS API into $RX_RAW_DIR, then the rest
#   SKIP_EXTRACT=1 scripts/run_pipeline.sh   use the pages already in $RX_RAW_DIR (e.g. tests/fixtures/pages)
#
# What runs comes from `rx plan` (dataset, year, CMS id, state). reports/pipeline-run.json is written even when
# a stage fails (status, the failing stage, seconds per stage, rows loaded per dataset-year) and is published
# with `rx metrics`, to the Pushgateway when RX_PUSHGATEWAY is set. The exit status is the failing stage's.
#
# Environment: RX_RAW_DIR (data/raw), RX_REPORTS_DIR (reports), SKIP_EXTRACT (0), RX_BIN (rx), DBT_BIN (dbt),
# DBT_TARGET_PATH (dbt/target).
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
raw=${RX_RAW_DIR:-$root/data/raw}
reports=${RX_REPORTS_DIR:-$root/reports}
rx=${RX_BIN:-rx}
dbt=${DBT_BIN:-dbt}
skip_extract=${SKIP_EXTRACT:-0}
export DBT_TARGET_PATH=${DBT_TARGET_PATH:-$root/dbt/target}

stages=()
loads=()
current=none
started=$(date +%s.%N)
cd "$root"
mkdir -p "$reports"
# Results of an earlier run must not be published as this run's.
rm -f "$reports/exports.json" "$reports/dbt-build.json" "$DBT_TARGET_PATH/run_results.json"

log() { printf '%s run_pipeline %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
join() { local IFS=,; printf '%s' "$*"; }
seconds_since() { awk -v a="$1" -v b="$(date +%s.%N)" 'BEGIN { printf "%.2f", b - a }'; }

finish() {
  local code=$? status=success failed_stage=null
  if ((code != 0)); then
    status=failed
    failed_stage="\"$current\""
  fi
  printf '{"status": "%s", "failed_stage": %s, "exit_code": %d, "started_at_epoch": %.0f, "finished_at_epoch": %s, "seconds": %s, "stages": [%s], "loads": [%s]}\n' \
    "$status" "$failed_stage" "$code" "$started" "$(date +%s)" "$(seconds_since "$started")" \
    "$(join "${stages[@]}")" "$(join "${loads[@]}")" >"$reports/pipeline-run.json"
  "$rx" metrics --run-report "$reports/pipeline-run.json" --dbt-results "$DBT_TARGET_PATH/run_results.json" \
    --exports-report "$reports/exports.json" --dbt-report "$reports/dbt-build.json" >/dev/null ||
    log "metrics were not published"
  log "$status in $(seconds_since "$started") s; report: $reports/pipeline-run.json"
  exit "$code"
}
trap finish EXIT

# stage NAME COMMAND...: run one timed stage; a failure ends the run through the EXIT trap.
stage() {
  current=$1
  shift
  local t0
  t0=$(date +%s.%N)
  log "stage $current"
  "$@"
  stages+=("{\"name\": \"$current\", \"seconds\": $(seconds_since "$t0")}")
}

extract_all() {
  local dataset year id state
  while IFS=$'\t' read -r dataset year id state; do
    [[ $state == - ]] && state=""
    bash "$root/scripts/extract_cms.sh" "$id" "$raw/$dataset/$year" ${state:+"$state"}
  done <<<"$plan"
}

load_all() {
  local dataset year id state result
  while IFS=$'\t' read -r dataset year id state; do
    result=$("$rx" load --dataset "$dataset" --year "$year" --pages "$raw/$dataset/$year" | tail -n 1)
    loads+=("$result")
  done <<<"$plan"
}

dbt_build() {
  (cd "$root/dbt" && DBT_PROFILES_DIR=${DBT_PROFILES_DIR:-.} "$dbt" build)
}

plan=$("$rx" plan)
if [[ $skip_extract != 1 ]]; then
  stage extract extract_all
fi
stage bootstrap "$rx" bootstrap
stage load load_all
stage dbt dbt_build
stage export "$rx" export
current="finished"
