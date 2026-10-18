# Runbook

Every alert in `observability/alert_rules.yml` links to a section here. Metrics come from `rx metrics`, which
`scripts/run_pipeline.sh` calls at the end of every run, failed or not.

## RxPipelineFailed

The last run stopped at a stage. `reports/pipeline-run.json` has `failed_stage` and `exit_code`; the run's
console log has the error.

| Stage | Usual cause | What to do |
|---|---|---|
| extract | CMS API down or slow (the script retries 5 times with backoff) | re-run; finished pages are kept, so it resumes |
| extract | "row count mismatch" | CMS changed the data during the run; delete that dataset-year folder and re-run it |
| load | warehouse unreachable, or credentials | check `SNOWFLAKE_*`; on the emulator, check it is running |
| dbt | a test failed (see RxDataTestsFailing) | read `reports/dbt-build.json` for the failing node |
| export | Tableau extract does not read back equal | see RxTableauExtractMismatch |

## RxPipelineStale

No successful run for 8 days. Check the scheduler first (did it run at all?), then RxPipelineFailed.

## RxDataTestsFailing

`rx_dbt_failures > 0`. The marts may be wrong; hold BI refreshes.

1. `reports/dbt-build.json` lists every node with its status.
2. `cd dbt && dbt test --select <test> --store-failures` keeps the failing rows in a table to look at.
3. Typical causes: CMS added or renamed a column (the `numbers_parse` and `raw_rows_reach_staging` tests fire),
   a new product broke a grain test, or a pinned drug-class edge case moved (a seed edit).

## RxTableauExtractMismatch

The `.hyper` file did not read back with the same row counts and column sums as the marts.
`reports/exports.json` lists the table and column. Re-run `rx export`; if it repeats, compare the column's type
in `fetch_mart` (Snowflake metadata) with the extract's column type.

## RxRawRowsDropped

A data year has over 1% fewer raw rows than a week ago. CMS sometimes revises a release; compare the new
`manifest.json` with the one in `reports/extract/`. If the API itself reports fewer rows, the revision is
real; record it. If the API count is unchanged, the extract was incomplete: re-run that dataset-year.

## Yearly: new CMS release

1. Find the new dataset id at https://data.cms.gov/data.json and add it to `PRESCRIBER_DRUG_DATASETS` in
   `src/rx/config.py`; add the year to `RX_YEARS`, `accepted_values` in `dbt/models/sources.yml` and
   `spending_years` in `dbt/dbt_project.yml` when the spending release adds a year.
2. Run the pipeline, then review every product each drug class matched and add rules or pins for anything new:
   `select drug_class, brand_name, generic_name from ANALYTICS.int_drug_class order by 1, 3, 2`.

## The local emulator

fakesnow keeps everything in memory. A full three-year run peaked at 9.3 GB in the emulator; a second full
reload in the same process doubles that. Restart it (`make emulator`, or `docker compose restart emulator`)
before reloading every year.
