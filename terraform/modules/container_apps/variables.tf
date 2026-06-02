variable "environment_name" {
  type        = string
  description = "Container Apps Environment name"
}

variable "app_name" {
  type        = string
  description = "Container App name"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "log_analytics_workspace_resource_id" {
  type        = string
  description = "ARM resource ID of the Log Analytics Workspace"
}

variable "acr_login_server" {
  type        = string
  description = "ACR login server (e.g. myacr.azurecr.io)"
}

variable "storage_account_name" {
  type        = string
  description = "Storage account name (used as env var for KEDA scaler)"
}

variable "postgresql_secret_versionless_id" {
  type        = string
  description = "Versionless Key Vault secret URI for PostgreSQL connection string"
}

variable "openai_secret_versionless_id" {
  type        = string
  description = "Versionless Key Vault secret URI for AI Foundry endpoint"
}

variable "appinsights_secret_versionless_id" {
  type        = string
  description = "Versionless Key Vault secret URI for App Insights connection string"
}

variable "image_tag" {
  type        = string
  description = "Container image tag to deploy"
  default     = "latest"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
