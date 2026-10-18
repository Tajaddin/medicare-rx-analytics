# Compute and storage: one extra-small warehouse behind a resource monitor, one database, two schemas.
# The stage and the raw tables are created by `rx bootstrap` as RX_PIPELINE, so the loader owns what it writes.

resource "snowflake_resource_monitor" "rx" {
  name            = "RX_MONTHLY"
  credit_quota    = var.monthly_credit_quota
  frequency       = "MONTHLY"
  start_timestamp = "IMMEDIATELY"

  notify_triggers           = [75, 90]
  suspend_trigger           = 100
  suspend_immediate_trigger = 110
  notify_users              = var.monitor_notify_users
}

resource "snowflake_warehouse" "rx" {
  name                = var.warehouse
  warehouse_size      = var.warehouse_size
  auto_suspend        = 60
  auto_resume         = "true"
  initially_suspended = true
  resource_monitor    = snowflake_resource_monitor.rx.fully_qualified_name
  comment             = "medicare-rx-analytics: load, dbt and BI"
}

resource "snowflake_database" "rx" {
  name                        = var.database
  data_retention_time_in_days = 1
  comment                     = "Medicare Part D prescribing: raw CMS JSON and dbt marts"
}

resource "snowflake_schema" "raw" {
  database                    = snowflake_database.rx.name
  name                        = "RAW"
  with_managed_access         = "true"
  data_retention_time_in_days = 1
  comment                     = "CMS data API pages as VARIANT, loaded by rx load"
}

resource "snowflake_schema" "analytics" {
  database                    = snowflake_database.rx.name
  name                        = "ANALYTICS"
  with_managed_access         = "true"
  data_retention_time_in_days = 1
  comment                     = "dbt staging views, intermediate views and mart tables"
}
