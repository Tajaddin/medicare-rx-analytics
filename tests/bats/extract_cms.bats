#!/usr/bin/env bats
# scripts/extract_cms.sh against a local fake of the CMS data API (python http.server on a random port).

DATASET=9552739e-3d05-4c1b-8eff-ecabf391e2e5

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../../scripts/extract_cms.sh"
  OUT="$BATS_TEST_TMPDIR/out"
  export PAGE_SIZE=2 RETRY_DELAY=0 PAUSE=0 MAX_RETRIES=2
  FAKE_ROWS=${FAKE_ROWS:-5}
}

start_fake() {
  # $1 = total rows, $2 = "flaky" to fail every first request for a page; FAKE_REVISION re-publishes the source
  PORT_FILE="$BATS_TEST_TMPDIR/port"
  rm -f "$PORT_FILE"
  python3 "$BATS_TEST_DIRNAME/fake_cms_api.py" "$1" "${2:-}" "$PORT_FILE" &
  FAKE_PID=$!
  for _ in $(seq 1 50); do [[ -s $PORT_FILE ]] && break; sleep 0.1; done
  export CMS_API_BASE="http://127.0.0.1:$(cat "$PORT_FILE")/data-api/v1/dataset"
}

stop_fake() {
  kill "$FAKE_PID" 2>/dev/null || true
  wait "$FAKE_PID" 2>/dev/null || true
}

manifest() {
  python3 -c "import json,sys; m=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))" "$OUT/manifest.json" "$1"
}

teardown() {
  [[ -n ${FAKE_PID:-} ]] && kill "$FAKE_PID" 2>/dev/null || true
}

@test "usage and argument validation" {
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  run bash "$SCRIPT" not-a-uuid "$OUT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"invalid dataset id"* ]]
  run bash "$SCRIPT" "$DATASET" "$OUT" Florida
  [ "$status" -eq 2 ]
  [[ "$output" == *"invalid state"* ]]
}

@test "pages through every row and writes a verified manifest" {
  start_fake 5
  run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  [ -s "$OUT/page-00000.json" ] && [ -s "$OUT/page-00002.json" ] && [ ! -e "$OUT/page-00003.json" ]
  run python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); print(m["rows"], m["expected_rows"], m["pages"])' "$OUT/manifest.json"
  [ "$output" = "5 5 3" ]
}

@test "resumes: existing valid pages are not downloaded again" {
  start_fake 5
  bash "$SCRIPT" "$DATASET" "$OUT" FL
  before=$(stat -c %Y "$OUT/page-00000.json")
  rm "$OUT/page-00002.json"
  sleep 1
  run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  [ "$(stat -c %Y "$OUT/page-00000.json")" = "$before" ]
  [ -s "$OUT/page-00002.json" ]
}

@test "retries a page that fails once" {
  start_fake 4 flaky
  run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  [[ "$output" == *"attempt 1/2 failed"* ]]
}

@test "a corrupt page on disk is fetched again" {
  start_fake 4
  bash "$SCRIPT" "$DATASET" "$OUT" FL
  echo "{not json" >"$OUT/page-00001.json"
  run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  run python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$OUT/page-00001.json"
  [ "$output" = "2" ]
}

@test "the manifest names the source file and has no row count until the pages are verified" {
  start_fake 5 flaky
  MAX_RETRIES=1 run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 1 ]
  [ "$(manifest 'm["rows"], m["expected_rows"], m["source_file"]')" = "(None, 5, 'rows-5-revision-1.csv')" ]
  MAX_RETRIES=2 run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  [ "$(manifest 'm["rows"], m["source_modified"], len(m["source_sha1"])')" = "(5, '2026-05-05T16:53:21Z', 40)" ]
}

@test "a source re-published with the same row count is fetched again" {
  start_fake 5
  bash "$SCRIPT" "$DATASET" "$OUT" FL
  before=$(cat "$OUT/page-00000.json")
  sha1=$(manifest 'm["source_sha1"]')
  stop_fake
  FAKE_REVISION=2 start_fake 5
  run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  [[ "$output" == *"fetching every page again"* ]]
  [ "$(cat "$OUT/page-00000.json")" != "$before" ]
  [ "$(manifest 'm["source_sha1"]')" != "$sha1" ]
  [ "$(manifest 'm["rows"]')" = "5" ]
}

@test "a source re-published with fewer rows replaces the pages instead of failing" {
  start_fake 5
  bash "$SCRIPT" "$DATASET" "$OUT" FL
  stop_fake
  start_fake 3
  run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  [ -s "$OUT/page-00001.json" ] && [ ! -e "$OUT/page-00002.json" ]
  [ "$(manifest 'm["rows"], m["expected_rows"], m["pages"]')" = "(3, 3, 2)" ]
}

@test "pages fetched with another page size are fetched again" {
  start_fake 5
  bash "$SCRIPT" "$DATASET" "$OUT" FL
  PAGE_SIZE=5 run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 0 ]
  [ ! -e "$OUT/page-00001.json" ]
  [ "$(manifest 'm["rows"], m["pages"], m["page_size"]')" = "(5, 1, 5)" ]
}

@test "fails when the API cannot be reached" {
  export CMS_API_BASE="http://127.0.0.1:9/data-api/v1/dataset"
  run bash "$SCRIPT" "$DATASET" "$OUT" FL
  [ "$status" -eq 1 ]
  [[ "$output" == *"cannot reach the CMS API"* ]]
}
