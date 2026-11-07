#!/usr/bin/env bash
# Page through the CMS data API for one dataset, writing one JSON file per page. Resumable and verified.
#
#   scripts/extract_cms.sh DATASET_ID OUT_DIR [STATE]
#
# - Asks the API how many rows match (data/stats) and which source file it serves (data-viewer: the CSV's name,
#   SHA-1 and modification time), then fetches pages of PAGE_SIZE rows.
# - manifest.json records that source before any page is fetched. When the source, the row count or the page size
#   differ from the manifest on disk, CMS has re-published the data: every page is fetched again.
# - Otherwise a page that already exists and parses as a JSON array is skipped, so an interrupted run resumes.
# - Every request is retried with exponential backoff; a page that keeps failing stops the run.
# - At the end the row count on disk must equal the API's count; only then does the manifest get its `rows`.
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

# manifest ROWS: manifest.json for the source the API serves now; ROWS is null until the pages are verified.
manifest() {
  python3 - "$out/stats.json" "$out/source.json" "$dataset" "$state" "$size" "$1" <<'EOF'
import json, sys
from datetime import UTC, datetime

stats, source, dataset, state, size, rows = sys.argv[1:]
meta = json.load(open(source, encoding="utf-8"))["meta"]
file_meta = meta.get("data_file_meta_data") or {}
modified = file_meta.get("csvFileModifiedTime")
expected = json.load(open(stats, encoding="utf-8"))["found_rows"]
print(json.dumps({
    "dataset": dataset,
    "state": state,
    "source_file": meta.get("data_file_name"),
    "source_sha1": file_meta.get("csvFileSHA1"),
    "source_modified": modified and datetime.fromtimestamp(modified, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expected_rows": expected,
    "rows": json.loads(rows),
    "pages": -(-expected // int(size)),
    "page_size": int(size),
}))
EOF
}

# same_source OLD_FILE NEW_JSON: the pages OLD_FILE describes were fetched from the same source, count and paging.
same_source() {
  python3 -c 'import json, sys
old, new = json.load(open(sys.argv[1], encoding="utf-8")), json.loads(sys.argv[2])
sys.exit(any(old.get(k) != v for k, v in new.items() if k != "rows"))' "$1" "$2" 2>/dev/null
}

fetch "$base/$dataset/data/stats?${filter%&}" "$out/stats.json" || { echo "cannot reach the CMS API" >&2; exit 1; }
fetch "$base/$dataset/data-viewer?size=0" "$out/source.json" || { echo "cannot reach the CMS API" >&2; exit 1; }
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["found_rows"])' "$out/stats.json")
pages=$(((expected + size - 1) / size))
log "dataset $dataset ${state:-all states}: $expected rows in $pages pages of $size"

current=$(manifest null)
if ! { [[ -s $out/manifest.json ]] && same_source "$out/manifest.json" "$current"; }; then
  if compgen -G "$out/page-*.json" >/dev/null; then
    log "the pages on disk are not from the source the API serves now; fetching every page again"
    rm -f "$out"/page-*.json
  fi
fi
printf '%s\n' "$current" >"$out/manifest.json"

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
manifest "$total" >"$out/manifest.json"
log "done: $total rows verified"
