# Sprint 4 retro: release

Dates: 2026-10-18. Milestone: [Sprint 4 - Release](https://github.com/Tajaddin/medicare-rx-analytics/milestone/4).

**Goal:** Terraform for Snowflake, one command for the batch, monitoring, measured run times and the docs a new
reader needs. **Met**, except applying the Terraform (no account).

## Delivered

| Issue | Points | Result |
|---|---|---|
| #10 Terraform | 3 | warehouse behind a credit cap, database and schemas, four least-privilege roles, a key-pair service user; validated, tflint and trivy clean |
| #16 orchestration | 3 | `run_pipeline.sh`: timed stages, a run report even on failure, 4 bats tests |
| #17 observability | 3 | run metrics to a Pushgateway, 5 alert rules with promtool tests and runbook entries, a provisioned Grafana dashboard |
| #18 Docker | 2 | pipeline and emulator images; `make up`; CI runs the stack end to end and checks Prometheus |
| #11 measured run and docs | 3 | README, architecture, data card, data dictionary, runbook, deploy guide, research notes |

14 of 14 points done.

## Measured (`reports/`)

- Full run on the 2022-2024 data against a fresh emulator: **257 s** (bootstrap 3 s, load 165 s, dbt 83 s,
  export 5 s); 49 of 49 dbt nodes pass; the Tableau extract matches the marts.
- In Docker on the sample: 15.9 s, and Prometheus showed `rx_pipeline_last_run_success 1`, 37 dbt tests, 0
  failures and `rx_hyper_verified 1`; all five alert rules loaded and inactive.

## What went well

- The run report is written from an `EXIT` trap, so the one real failure this sprint (below) still produced a
  report naming the failed stage and still pushed metrics.

## What did not

- **The emulator is in memory.** A second full run hung in the load stage: fakesnow had grown to 8.1 GB and the
  WSL VM's swap was full. Reading fakesnow's server code showed that `-d` (persistence) is ignored in server mode,
  so every row lives in DuckDB's memory and deleted rows are not given back. A fresh emulator peaked at 9.3 GB for
  the full run. The CLI and compose no longer pretend to persist, and the runbook says to restart before a full
  reload. On Snowflake this does not apply.
- The first image was 3.0 GB: `chown -R` after installing the environment copied 1 GB into a second layer.
  Only the output folders are chowned now (1.64 GB).
- The sample run and `make demo` wrote into `reports/` and would have overwritten the full run's results; they
  now write to `.demo/` or a temporary folder.

## Still open (Backlog)

- #12 run on a Snowflake trial: the only way to get Snowflake timings and credit use.
- #13 publish the Tableau dashboard; #14 the GitHub Projects board (needs a token with the `project` scope).
