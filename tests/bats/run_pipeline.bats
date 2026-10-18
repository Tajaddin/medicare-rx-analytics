#!/usr/bin/env bats
# scripts/run_pipeline.sh with stub `rx` and `dbt` commands that record their calls, and the fake CMS API for the
# extract stage. Checks the stage order, the run report on success and on failure, and that metrics always run.

setup() {
  ROOT="$BATS_TEST_DIRNAME/../.."
  SCRIPT="$ROOT/scripts/run_pipeline.sh"
  STUBS="$BATS_TEST_TMPDIR/bin"
  export CALLS="$BATS_TEST_TMPDIR/calls"
  export RX_REPORTS_DIR="$BATS_TEST_TMPDIR/reports"
  export RX_RAW_DIR="$BATS_TEST_TMPDIR/raw"
  export RX_BIN="$STUBS/rx" DBT_BIN="$STUBS/dbt"
  export DBT_TARGET_PATH="$BATS_TEST_TMPDIR/dbt-target"
  export PAGE_SIZE=2 RETRY_DELAY=0 PAUSE=0 MAX_RETRIES=2
  mkdir -p "$STUBS"
  cat >"$STUBS/rx" <<'EOF'
#!/usr/bin/env bash
echo "rx $*" >>"$CALLS"
case $1 in
  plan)
    printf 'prescriber_drug\t2024\t9552739e-3d05-4c1b-8eff-ecabf391e2e5\tFL\n'
    printf 'spending_by_drug\t2024\t7e0b4365-fd63-4a29-8f5e-e0ac9f66a81b\t-\n'
    ;;
  load)
    echo '{"event": "loaded"}'
    echo "{\"dataset\": \"$3\", \"year\": $5, \"files\": 1, \"rows\": 5, \"seconds\": 0.1}"
    ;;
  export) exit "${EXPORT_EXIT:-0}" ;;
esac
EOF
  cat >"$STUBS/dbt" <<'EOF'
#!/usr/bin/env bash
echo "dbt $*" >>"$CALLS"
exit "${DBT_EXIT:-0}"
EOF
  chmod +x "$STUBS/rx" "$STUBS/dbt"
}

teardown() {
  [[ -n ${FAKE_PID:-} ]] && kill "$FAKE_PID" 2>/dev/null || true
}

report() {
  python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))" \
    "$RX_REPORTS_DIR/pipeline-run.json" "$1"
}

@test "runs the stages in order and writes a success report" {
  SKIP_EXTRACT=1 run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ "$(report 'r["status"]')" = "success" ]
  [ "$(report '",".join(s["name"] for s in r["stages"])')" = "bootstrap,load,dbt,export" ]
  [ "$(report '[(l["dataset"], l["rows"]) for l in r["loads"]]')" = "[('prescriber_drug', 5), ('spending_by_drug', 5)]" ]
  [ "$(grep -c '^rx load' "$CALLS")" -eq 2 ]
  grep -q '^dbt build$' "$CALLS"
  [ "$(tail -n 1 "$CALLS" | cut -d' ' -f1-2)" = "rx metrics" ]
}

@test "a failing stage stops the run, is named in the report and metrics still run" {
  SKIP_EXTRACT=1 DBT_EXIT=1 run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [ "$(report 'r["status"], r["failed_stage"], r["exit_code"]')" = "('failed', 'dbt', 1)" ]
  ! grep -q '^rx export' "$CALLS"
  grep -q '^rx metrics' "$CALLS"
}

@test "the exit status is the failing stage's" {
  SKIP_EXTRACT=1 EXPORT_EXIT=3 run bash "$SCRIPT"
  [ "$status" -eq 3 ]
  [ "$(report 'r["failed_stage"]')" = "export" ]
}

@test "extracts every planned dataset-year when SKIP_EXTRACT is not set" {
  PORT_FILE="$BATS_TEST_TMPDIR/port"
  python3 "$BATS_TEST_DIRNAME/fake_cms_api.py" 3 "" "$PORT_FILE" &
  FAKE_PID=$!
  for _ in $(seq 1 50); do [[ -s $PORT_FILE ]] && break; sleep 0.1; done
  export CMS_API_BASE="http://127.0.0.1:$(cat "$PORT_FILE")/data-api/v1/dataset"
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -s "$RX_RAW_DIR/prescriber_drug/2024/manifest.json" ]
  [ -s "$RX_RAW_DIR/spending_by_drug/2024/manifest.json" ]
  [ "$(report 'r["stages"][0]["name"]')" = "extract" ]
}
