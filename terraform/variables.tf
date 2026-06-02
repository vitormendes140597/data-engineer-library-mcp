variable "subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "tenant_id" {
  type        = string
  description = "Azure AD tenant ID"
}

variable "location" {
  type        = string
  description = "Azure region for all resources"
  default     = "eastus2"
}

variable "environment" {
  type        = string
  description = "Deployment environment: dev, staging, or prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod"
  }
}

variable "postgres_admin_login" {
  type        = string
  description = "PostgreSQL Flexible Server administrator username"
  default     = "ragadmin"
}

variable "postgres_admin_password" {
  type        = string
  description = "PostgreSQL administrator password. Pass via TF_VAR_postgres_admin_password — do NOT store in .tfvars files."
  sensitive   = true
}
