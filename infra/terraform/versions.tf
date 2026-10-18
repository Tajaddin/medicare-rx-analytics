terraform {
  required_version = ">= 1.9"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.21.0"
    }
  }
}

# Credentials come from the environment (SNOWFLAKE_ORGANIZATION_NAME, SNOWFLAKE_ACCOUNT_NAME, SNOWFLAKE_USER,
# SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT, SNOWFLAKE_PRIVATE_KEY), never from variables or state.
# Resource monitors and account-level grants need ACCOUNTADMIN.
provider "snowflake" {
  role = var.admin_role
}
