# Research notes

What was read before building, and what it changed. Links checked 2026-10-18.

## The data

- **CMS, Medicare Part D Prescribers by Provider and Drug**
  ([dataset](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug),
  [methodology, RY26](https://data.cms.gov/sites/default/files/2026-05/MUP_DPR_RY26_20260421_Methodology_508.pdf),
  [data dictionary](https://data.cms.gov/sites/default/files/2022-07/MUP_DPR_RY22_20220715_DD_PRV_Drug.pdf)).
  Built from 100% of final-action Part D prescription drug event records. Rows with fewer than 11 claims are not
  published and counts below 11 are blank. → Blanks stay NULL in every model and a test checks that every
  published claim count is at least 11.
- **CMS, Medicare Part D Spending by Drug**
  ([dataset](https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug),
  [methodology](https://data.cms.gov/sites/default/files/2024-03/DSD_PTD_RY24_20240212_Methodology_WDDSE_508.pdf)).
  One wide row per brand, generic and manufacturer with five years of columns; spending is gross and excludes
  manufacturer rebates, which CMS may not disclose. → The staging model unpivots the years and keeps the
  "Overall" rows; every cost in the README is labelled gross.
- **GAO, Medicare Part D: CMS Should Monitor Effects of Rebates on Drug Coverage and Spending**
  ([GAO-23-107056](https://www.gao.gov/products/gao-23-107056)). Plan sponsors received $48.6 billion in rebates
  in 2021. → The data card says how far gross is from net.
- **CMS data API** ([docs](https://data.cms.gov/api-docs)). `/data` pages with `size` and `offset` (5,000 rows
  a page), `/data/stats` returns the matching row count, `filter[column]=value` filters server-side. → The
  extractor filters to Florida on the server and checks its row total against `/stats`.

## Drug classes

- **CDC, U.S. Opioid Dispensing Rate Maps**
  ([methodology](https://www.cdc.gov/overdose-prevention/data-research/facts-stats/opioid-dispensing-rate-maps.html)).
  Counts buprenorphine formulations prescribed for pain (Belbuca, Butrans) as opioid prescriptions; methadone
  from treatment programmes is not in the data. PolicyMap's description of the same CDC data
  ([source](https://policymap.com/data/sources/centers-for-disease-control-and-prevention-cdc-drug-overdose))
  adds that cough and cold formulations and buprenorphine for opioid use disorder are excluded. → The drug-class
  rules follow this (ADR 0004): a separate antitussive class, Butrans and Belbuca as analgesics, Sublocade,
  Brixadi, Suboxone and generic sublingual buprenorphine as OUD treatment.

## Snowflake and the emulator

- **fakesnow** ([repo](https://github.com/tekumara/fakesnow)): a Snowflake connector fake backed by DuckDB, with
  a server mode for clients that speak HTTP. Read the server code to find that `-d` is ignored in server mode
  (persistence is a per-session `FAKESNOW_DB_PATH` parameter), which explained the memory profile (ADR 0002).
- **Snowflake: user management** ([docs](https://docs.snowflake.com/en/user-guide/admin-user-management)):
  `TYPE = SERVICE` users "cannot log in using a password". → Key-pair sign-in for the pipeline
  ([key-pair auth](https://docs.snowflake.com/en/user-guide/key-pair-auth)), a service user in Terraform.
- **Snowflake: COPY INTO, VARIANT, resource monitors**
  ([COPY INTO](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table),
  [resource monitors](https://docs.snowflake.com/en/user-guide/resource-monitors)). → Landing-table load (ADR
  0001) and a monthly credit cap that suspends the warehouse.
- **Terraform provider snowflakedb/snowflake**
  ([registry](https://registry.terraform.io/providers/snowflakedb/snowflake/latest/docs)): 2.22.0 was published
  2026-10-13; pinned to the 2.21 line, which had been out longer.
- **dbt-snowflake** ([setup](https://docs.getdbt.com/docs/core/connect-data-platform/snowflake-setup)): key-pair
  fields (`private_key_path`) for the production profile.

## BI

- **Power BI Desktop projects** ([PBIP](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview),
  [TMDL](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview),
  [PBIR](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report)) and Microsoft's
  published JSON schemas ([fabric/item/report](https://github.com/microsoft/json-schemas/tree/main/fabric/item/report)).
  → The project is plain text, generated, validated against these schemas in CI, and opened in Desktop.
- **Tableau Hyper API** ([docs](https://tableau.github.io/hyper-db/docs/)): writes `.hyper` files Tableau opens
  directly; queried back with SQL to verify the extract.
