variable "name" {
  type        = string
  description = "PostgreSQL Flexible Server name"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "administrator_login" {
  type        = string
  description = "PostgreSQL administrator username"
}

variable "administrator_password" {
  type        = string
  description = "PostgreSQL administrator password"
  sensitive   = true
}

variable "sku_name" {
  type        = string
  description = "PostgreSQL SKU (Burstable tier for dev/staging; GeneralPurpose for prod)"
  default     = "B_Standard_B1ms"
}

variable "storage_mb" {
  type        = number
  description = "Storage in megabytes"
  default     = 32768
}

variable "postgres_version" {
  type        = string
  description = "PostgreSQL major version"
  default     = "16"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
