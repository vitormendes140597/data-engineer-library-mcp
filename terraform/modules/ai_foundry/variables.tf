variable "name" {
  type        = string
  description = "AI Foundry (Cognitive Services AIServices) account name"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "custom_subdomain_name" {
  type        = string
  description = "Custom subdomain for the AI Foundry endpoint (must be globally unique)"
}

variable "sku_name" {
  type        = string
  description = "SKU name"
  default     = "S0"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
