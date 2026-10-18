# Running it on real accounts

Everything here needs an account that only its owner can create. Section 1 was run on 2026-10-18 (results in
`reports/snowflake/`); the local emulator stays the default for development and CI (ADR 0002).

## 1. Snowflake trial (free, 30 days)

1. Sign up at https://signup.snowflake.com (Enterprise edition; this run used AWS us-east-2).
2. Create a key pair for Terraform and one for the pipeline, outside the repo:

   ```bash
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/rx_pipeline.p8 -nocrypt
   openssl rsa -in ~/.snowflake/rx_pipeline.p8 -pubout -out ~/.snowflake/rx_pipeline.pub
   ```

   Do the same for an admin key, and attach it to your own user in a Snowsight worksheet:
   `ALTER USER <you> SET RSA_PUBLIC_KEY='<body of the admin .pub without the BEGIN/END lines>';`
   Check the user's name first (`select current_user()`): an account created with "Sign up with Google" can have
   a lower-case name, which needs double quotes (`ALTER USER "name" ...`), and a login name that is the e-mail
   address. Terraform's `SNOWFLAKE_USER` is the login name.
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

   To reuse pages already extracted and keep the emulator's reports, as on 2026-10-18:
   `SKIP_EXTRACT=1 RX_REPORTS_DIR=reports/snowflake RX_EXPORTS_DIR=<elsewhere> make pipeline RAW=<pages>`.
5. Record `reports/snowflake/pipeline-run.json` and `dbt-build.json` from that run, and the credits used
   (`rx.information_schema.warehouse_metering_history` for RX_WH, queried from another warehouse so the check
   does not bill RX_WH). Those are the numbers to quote for Snowflake; the emulator's timings are not.

## 2. Power BI Desktop (free)

1. `make pipeline` (or `make demo`) so `bi/exports/` holds the Parquet files.
2. Open `bi/powerbi/MedicareRx.pbip`, choose Transform data > Edit parameters, set **ExportsFolder** to the
   absolute path of `bi/exports`, then Refresh.
3. On Snowflake instead: replace each partition's source with `Snowflake.Databases("<account>.snowflakecomputing.com",
   "RX_WH"){[Name="RX"]}[Data]...` and sign in as a user with RX_REPORTER. Publishing to the Power BI service needs
   a Microsoft work account.

## 3. Tableau Public (free account)

The published dashboard was built in the browser (Tableau Public's web editor reads CSV, not `.hyper`):

1. `python scripts/make_tableau_public.py` writes three tidy CSVs from the marts to `bi/tableau-public/`: GLP-1
   claims by drug and year, opioid share of claims in the 15 largest cities (2024), and the top 10 drugs by 2024
   cost.
2. In Tableau Public, Create > Web Authoring, upload each CSV as its own data source (Data > New Data Source >
   Files), one sheet each, then a dashboard with the three sheets and the source line under the title.
3. Publish As..., and add the link to the README.

With the desktop app instead, connect to **More... > Other files**, pick `bi/exports/rx_marts.hyper` (schema
`Extract`, six tables) and build from the marts directly.

## 4. GitHub Projects board

The sprints are milestones with issues; a board needs a token with the `project` scope:

```bash
gh auth refresh -s project
python scripts/agile/sync_backlog.py --board
```
