# Running it on real accounts

Everything here needs an account that only its owner can create. Nothing below has been run yet; the local
emulator stands in for Snowflake until it is (ADR 0002).

## 1. Snowflake trial (free, 30 days)

1. Sign up at https://signup.snowflake.com (Enterprise edition, AWS us-east-1 is fine).
2. Create a key pair for Terraform and one for the pipeline, outside the repo:

   ```bash
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/rx_pipeline.p8 -nocrypt
   openssl rsa -in ~/.snowflake/rx_pipeline.p8 -pubout -out ~/.snowflake/rx_pipeline.pub
   ```

   Do the same for an admin key, and attach it to your own user in a Snowsight worksheet:
   `ALTER USER <you> SET RSA_PUBLIC_KEY='<body of the admin .pub without the BEGIN/END lines>';`
3. Apply the Terraform (credentials from the environment, never from files in the repo):

   ```bash
   export SNOWFLAKE_ORGANIZATION_NAME=<org> SNOWFLAKE_ACCOUNT_NAME=<account> SNOWFLAKE_USER=<you>
   export SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT SNOWFLAKE_PRIVATE_KEY="$(cat ~/.snowflake/admin.p8)"
   terraform -chdir=infra/terraform init
   terraform -chdir=infra/terraform apply -var "pipeline_user_public_key=$(sed '1d;$d' ~/.snowflake/rx_pipeline.pub | tr -d '\n')"
   ```

   This creates RX_WH (XSMALL, 60 s auto-suspend, 10-credit monthly cap), database RX, schemas RAW and
   ANALYTICS, the four roles and the RX_PIPELINE service user.
4. Run the pipeline against it:

   ```bash
   export SNOWFLAKE_ACCOUNT=<org>-<account> SNOWFLAKE_USER=RX_PIPELINE SNOWFLAKE_ROLE=RX_PIPELINE \
          SNOWFLAKE_PRIVATE_KEY_FILE=~/.snowflake/rx_pipeline.p8 DBT_TARGET=snowflake
   unset SNOWFLAKE_HOST SNOWFLAKE_PORT
   make pipeline
   ```

5. Record `reports/pipeline-run.json` and `reports/dbt-build.json` from that run, and the credits used
   (`select * from snowflake.account_usage.warehouse_metering_history where warehouse_name = 'RX_WH'`). Those are
   the numbers to quote for Snowflake; the emulator's timings are not.

## 2. Power BI Desktop (free)

1. `make pipeline` (or `make demo`) so `bi/exports/` holds the Parquet files.
2. Open `bi/powerbi/MedicareRx.pbip`, choose Transform data > Edit parameters, set **ExportsFolder** to the
   absolute path of `bi/exports`, then Refresh.
3. On Snowflake instead: replace each partition's source with `Snowflake.Databases("<account>.snowflakecomputing.com",
   "RX_WH"){[Name="RX"]}[Data]...` and sign in as a user with RX_REPORTER. Publishing to the Power BI service needs
   a Microsoft work account.

## 3. Tableau Public (free account)

1. Open Tableau Public (desktop app), connect to **More... > Other files**, pick `bi/exports/rx_marts.hyper`
   (schema `Extract`, six tables).
2. Sheets the extract was built for: drug cost by year and class (`mart_drug_spend_trend`), GLP-1 claims by
   product and year (`mart_glp1_growth`), opioid share of claims by city (`mart_opioid_by_city`, a map on city
   name with State = Florida), and brand spend above generic cost (`mart_generic_opportunity`).
3. Save to Tableau Public and add the link to the README.

## 4. GitHub Projects board

The sprints are milestones with issues; a board needs a token with the `project` scope:

```bash
gh auth refresh -s project
python scripts/agile/sync_backlog.py --board
```
