# 0006. Snowflake as code: least-privilege roles, a key-pair service user, a credit cap

Date: 2026-10-18. Status: accepted (Terraform validated, not applied: needs an account).

## Context

The first thing that goes wrong on a new Snowflake account is cost (a warehouse left running) and the second
is access (everything done as ACCOUNTADMIN). Snowflake also no longer lets service users sign in with a password.

## Decision

- Terraform (`snowflakedb/snowflake` 2.21) creates an extra-small warehouse that suspends after 60 s, behind a
  monthly resource monitor (notify at 75% and 90%, suspend at 100%, suspend immediately at 110%; 10 credits by
  default), the database and the RAW and ANALYTICS schemas with managed access.
- Roles by function: RX_LOADER writes RAW, RX_TRANSFORMER reads RAW and builds ANALYTICS, RX_REPORTER reads
  ANALYTICS; RX_PIPELINE inherits loader and transformer; all roll up to SYSADMIN. Future-object grants keep BI
  working after each dbt run.
- The pipeline signs in as a `SERVICE` user with an RSA key pair (`SNOWFLAKE_PRIVATE_KEY_FILE`); the public key
  is a Terraform variable, the private key never leaves the machine that runs the pipeline. Terraform's own
  credentials come from environment variables, never from variables or state.
- CI runs `terraform fmt`, `validate`, tflint and trivy on every push.

## Consequences

- On a real account Terraform owns the database and schemas; `rx bootstrap` only creates the stage and raw
  tables there (it creates everything on the emulator).
- Power BI's Snowflake connector does not support key-pair sign-in; BI users sign in as people (SSO) and get
  RX_REPORTER.
