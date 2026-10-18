variable "admin_role" {
  description = "Role Terraform runs as; resource monitors need ACCOUNTADMIN."
  type        = string
  default     = "ACCOUNTADMIN"
}

variable "database" {
  description = "Database for the raw layer and the dbt marts."
  type        = string
  default     = "RX"
}

variable "warehouse" {
  description = "Warehouse the loader, dbt and BI share."
  type        = string
  default     = "RX_WH"
}

variable "warehouse_size" {
  description = "XSMALL is 1 credit an hour while running; the full pipeline needs minutes a week."
  type        = string
  default     = "XSMALL"

  validation {
    condition     = contains(["XSMALL", "SMALL", "MEDIUM"], var.warehouse_size)
    error_message = "Keep the warehouse at MEDIUM or below; nothing here needs more."
  }
}

variable "monthly_credit_quota" {
  description = "Credits per month before the resource monitor suspends the warehouse."
  type        = number
  default     = 10

  validation {
    condition     = var.monthly_credit_quota > 0 && var.monthly_credit_quota <= 100
    error_message = "Quota must be between 1 and 100 credits a month."
  }
}

variable "monitor_notify_users" {
  description = "Snowflake users e-mailed at 75% and 90% of the quota (must have verified e-mail addresses)."
  type        = list(string)
  default     = []
}

variable "pipeline_user_public_key" {
  description = "RSA public key (PEM body without header lines) for the RX_PIPELINE service user. Not a secret."
  type        = string
  default     = ""
}
