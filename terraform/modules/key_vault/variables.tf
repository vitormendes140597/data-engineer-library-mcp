variable "name" {
  type        = string
  description = "Key Vault name"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "tenant_id" {
  type        = string
  description = "Azure AD tenant ID"
}

variable "postgresql_connection_string" {
  type        = string
  description = "Full PostgreSQL connection string (stored as secret)"
  sensitive   = true
}

variable "openai_endpoint" {
  type        = string
  description = "AI Foundry endpoint URL (stored as secret)"
}

variable "applicationinsights_connection_string" {
  type        = string
  description = "Application Insights connection string (stored as secret)"
  sensitive   = true
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
