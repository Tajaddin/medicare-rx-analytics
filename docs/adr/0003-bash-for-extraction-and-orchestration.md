# 0003. Bash for extraction and orchestration, tested with bats

Date: 2026-10-18. Status: accepted.

## Context

The batch has five steps that run in a line once a week at most: extract, load, build, export, publish
metrics. Extraction is network-bound paging (1,179 pages for three Florida years) where the failure that
matters is a dropped connection halfway through.

## Decision

- `scripts/extract_cms.sh`: one file per page, written only when the download completed and parsed as a JSON
  array; existing valid pages are skipped, so a re-run resumes; retries with exponential backoff; at the end the
  rows on disk must equal the API's own count, recorded in `manifest.json`.
- `scripts/run_pipeline.sh`: runs the stages listed by `rx plan`, times each, and writes
  `reports/pipeline-run.json` from an `EXIT` trap, so a failed run still reports which stage failed and still
  publishes metrics. The same script runs on a laptop, in the Docker image and in CI.
- Both scripts are `set -euo pipefail`, shellcheck-clean, and tested with bats against a fake CMS API and stub
  `rx`/`dbt` commands.

## Consequences

- No scheduler to run or secure for a weekly job; cron, a CI schedule or a Snowflake task can call one script.
- If the batch grows branches (per-state runs, backfills), an orchestrator such as Airflow or Dagster would earn
  its keep; the stage boundaries here are where its tasks would go.
