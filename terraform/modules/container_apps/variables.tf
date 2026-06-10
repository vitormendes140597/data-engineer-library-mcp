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

variable "raw_pdf_container_name" {
  type        = string
  description = "Raw PDF container name"
}

variable "extracted_images_container_name" {
  type        = string
  description = "Extracted images container name"
}

variable "queue_name" {
  type        = string
  description = "Processing queue name"
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

variable "reprocessor_job_name" {
  type        = string
  description = "Container App Job name for reprocessing"
  default     = ""
}

variable "reprocessor_schedule" {
  type        = string
  description = "Cron schedule for reprocessor job (e.g., '0 23 * * *' for 11 PM UTC)"
  default     = "0 23 * * *"
}

variable "reprocessor_max_parallelism" {
  type        = number
  description = "Maximum number of parallel executions for reprocessor job"
  default     = 1
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
