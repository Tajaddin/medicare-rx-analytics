output "warehouse" {
  value = snowflake_warehouse.rx.name
}

output "database" {
  value = snowflake_database.rx.name
}

output "roles" {
  value = [for r in snowflake_account_role.rx : r.name]
}

output "pipeline_user" {
  description = "Empty until pipeline_user_public_key is set."
  value       = one(snowflake_service_user.pipeline[*].name)
}
