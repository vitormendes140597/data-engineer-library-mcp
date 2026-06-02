variable "container_app_principal_id" {
  type        = string
  description = "System-assigned MI principal ID of the Container App"
}

variable "event_grid_principal_id" {
  type        = string
  description = "System-assigned MI principal ID of the Event Grid System Topic"
}

variable "storage_account_resource_id" {
  type        = string
  description = "Storage account ARM resource ID"
}

variable "acr_resource_id" {
  type        = string
  description = "ACR ARM resource ID"
}

variable "ai_foundry_resource_id" {
  type        = string
  description = "AI Foundry (Cognitive Services) ARM resource ID"
}

variable "key_vault_resource_id" {
  type        = string
  description = "Key Vault ARM resource ID"
}
