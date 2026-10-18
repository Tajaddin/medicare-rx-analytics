#!/usr/bin/env bash
# Page through the CMS data API for one dataset, writing one JSON file per page. Resumable and verified.
#
#   scripts/extract_cms.sh DATASET_ID OUT_DIR [STATE]
#
# - Asks the API how many rows match (data/stats), then fetches pages of PAGE_SIZE rows.
# - A page that already exists and parses as a JSON array is skipped, so an interrupted run resumes.
# - Every request is retried with exponential backoff; a page that keeps failing stops the run.
# - At the end the row count on disk must equal the API's count, and manifest.json records both.
#
# Environment: CMS_API_BASE, PAGE_SIZE (5000), MAX_RETRIES (5), RETRY_DELAY (2, seconds, doubles each try),
# PAUSE (0.2 s between pages, to be polite to the API).
set -euo pipefail

usage() {
  echo "usage: $(basename "$0") DATASET_ID OUT_DIR [STATE]" >&2
  exit 2
}

[[ $# -ge 2 && $# -le 3 ]] || usage
dataset=$1
out=$2
state=${3:-}
[[ $dataset =~ ^[0-9a-f-]{36}$ ]] || { echo "invalid dataset id: $dataset" >&2; exit 2; }
[[ -z $state || $state =~ ^[A-Z]{2}$ ]] || { echo "invalid state: $state" >&2; exit 2; }

base=${CMS_API_BASE:-https://data.cms.gov/data-api/v1/dataset}
size=${PAGE_SIZE:-5000}
retries=${MAX_RETRIES:-5}
delay=${RETRY_DELAY:-2}
pause=${PAUSE:-0.2}
filter=""
[[ -n $state ]] && filter="filter[Prscrbr_State_Abrvtn]=$state&"

mkdir -p "$out"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

# fetch URL FILE: download with retries; the file appears only when the download completed.
fetch() {
  local url=$1 dest=$2 attempt wait=$delay
  for ((attempt = 1; attempt <= retries; attempt++)); do
    if curl -fsS -g --max-time 120 -o "$dest.part" "$url"; then
      mv "$dest.part" "$dest"
      return 0
    fi
    log "attempt $attempt/$retries failed: $url"
    ((attempt < retries)) && sleep "$wait"
    wait=$((wait * 2))
  done
  rm -f "$dest.part"
  return 1
}

# rows FILE: number of records in a JSON array page, or -1 if it is not one.
rows() {
  python3 -c 'import json,sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(len(d) if isinstance(d, list) else -1)
except Exception:
    print(-1)' "$1"
}

fetch "$base/$dataset/data/stats?${filter%&}" "$out/stats.json" || { echo "cannot reach the CMS API" >&2; exit 1; }
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["found_rows"])' "$out/stats.json")
pages=$(((expected + size - 1) / size))
log "dataset $dataset ${state:-all states}: $expected rows in $pages pages of $size"

total=0
for ((page = 0; page < pages; page++)); do
  file=$(printf '%s/page-%05d.json' "$out" "$page")
  if [[ -s $file ]] && [[ $(rows "$file") -ge 0 ]]; then
    total=$((total + $(rows "$file")))
    continue
  fi
  if ! fetch "$base/$dataset/data?${filter}size=$size&offset=$((page * size))" "$file"; then
    echo "page $page failed after $retries attempts; re-run to resume" >&2
    exit 1
  fi
  n=$(rows "$file")
  if ((n < 0)); then
    rm -f "$file"
    echo "page $page is not a JSON array; re-run to resume" >&2
    exit 1
  fi
  total=$((total + n))
  ((page % 50 == 0)) && log "page $page/$pages, $total rows so far"
  sleep "$pause"
done

if ((total != expected)); then
  echo "row count mismatch: API says $expected, pages hold $total" >&2
  exit 1
fi
printf '{"dataset": "%s", "state": "%s", "expected_rows": %d, "rows": %d, "pages": %d, "page_size": %d}\n' \
  "$dataset" "$state" "$expected" "$total" "$pages" "$size" >"$out/manifest.json"
log "done: $total rows verified"
