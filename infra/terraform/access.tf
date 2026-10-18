# Least privilege by function:
#   RX_LOADER       writes RAW (stage, raw tables)
#   RX_TRANSFORMER  reads RAW, builds ANALYTICS (dbt owns what it creates)
#   RX_REPORTER     reads ANALYTICS (Power BI, Tableau, analysts)
#   RX_PIPELINE     LOADER + TRANSFORMER, the role of the RX_PIPELINE service user
# Every custom role rolls up to SYSADMIN, as Snowflake recommends.

locals {
  functional_roles = {
    RX_LOADER      = "Writes the raw layer"
    RX_TRANSFORMER = "Runs dbt: reads RAW, builds ANALYTICS"
    RX_REPORTER    = "Reads the marts for BI"
    RX_PIPELINE    = "The batch pipeline (loader + transformer)"
  }
  raw       = "\"${snowflake_database.rx.name}\".\"${snowflake_schema.raw.name}\""
  analytics = "\"${snowflake_database.rx.name}\".\"${snowflake_schema.analytics.name}\""
}

resource "snowflake_account_role" "rx" {
  for_each = local.functional_roles
  name     = each.key
  comment  = each.value
}

resource "snowflake_grant_account_role" "to_sysadmin" {
  for_each         = snowflake_account_role.rx
  role_name        = each.value.name
  parent_role_name = "SYSADMIN"
}

resource "snowflake_grant_account_role" "pipeline_inherits" {
  for_each         = toset(["RX_LOADER", "RX_TRANSFORMER"])
  role_name        = snowflake_account_role.rx[each.key].name
  parent_role_name = snowflake_account_role.rx["RX_PIPELINE"].name
}

# Warehouse and database: usage for every functional role.
resource "snowflake_grant_privileges_to_account_role" "warehouse_usage" {
  for_each          = toset(["RX_LOADER", "RX_TRANSFORMER", "RX_REPORTER"])
  account_role_name = snowflake_account_role.rx[each.key].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.rx.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "database_usage" {
  for_each          = toset(["RX_LOADER", "RX_TRANSFORMER", "RX_REPORTER"])
  account_role_name = snowflake_account_role.rx[each.key].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.rx.name
  }
}

# RAW: the loader creates the stage and tables; the transformer reads them.
resource "snowflake_grant_privileges_to_account_role" "raw_loader" {
  account_role_name = snowflake_account_role.rx["RX_LOADER"].name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE STAGE"]
  on_schema {
    schema_name = local.raw
  }
}

resource "snowflake_grant_privileges_to_account_role" "raw_transformer_usage" {
  account_role_name = snowflake_account_role.rx["RX_TRANSFORMER"].name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = local.raw
  }
}

resource "snowflake_grant_privileges_to_account_role" "raw_transformer_read" {
  for_each          = toset(["all", "future"])
  account_role_name = snowflake_account_role.rx["RX_TRANSFORMER"].name
  privileges        = ["SELECT"]
  on_schema_object {
    dynamic "all" {
      for_each = each.key == "all" ? [1] : []
      content {
        object_type_plural = "TABLES"
        in_schema          = local.raw
      }
    }
    dynamic "future" {
      for_each = each.key == "future" ? [1] : []
      content {
        object_type_plural = "TABLES"
        in_schema          = local.raw
      }
    }
  }
}

# ANALYTICS: dbt creates views and tables; BI reads them.
resource "snowflake_grant_privileges_to_account_role" "analytics_transformer" {
  account_role_name = snowflake_account_role.rx["RX_TRANSFORMER"].name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
  on_schema {
    schema_name = local.analytics
  }
}

resource "snowflake_grant_privileges_to_account_role" "analytics_reporter_usage" {
  account_role_name = snowflake_account_role.rx["RX_REPORTER"].name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = local.analytics
  }
}

resource "snowflake_grant_privileges_to_account_role" "analytics_reporter_read" {
  for_each          = toset(["TABLES", "VIEWS"])
  account_role_name = snowflake_account_role.rx["RX_REPORTER"].name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = each.key
      in_schema          = local.analytics
    }
  }
}

# The pipeline signs in with a key pair only: a service user has no password and cannot use the web UI.
resource "snowflake_service_user" "pipeline" {
  count             = var.pipeline_user_public_key == "" ? 0 : 1
  name              = "RX_PIPELINE"
  default_role      = snowflake_account_role.rx["RX_PIPELINE"].name
  default_warehouse = snowflake_warehouse.rx.name
  rsa_public_key    = var.pipeline_user_public_key
  comment           = "medicare-rx-analytics batch pipeline"
}

resource "snowflake_grant_account_role" "pipeline_user" {
  count     = length(snowflake_service_user.pipeline)
  role_name = snowflake_account_role.rx["RX_PIPELINE"].name
  user_name = snowflake_service_user.pipeline[0].name
}
