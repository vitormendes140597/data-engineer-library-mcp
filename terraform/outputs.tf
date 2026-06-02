output "resource_group_name" {
  value       = data.azurerm_resource_group.main.name
  description = "Resource group name"
}

output "storage_account_name" {
  value       = module.storage.name
  description = "Storage account name — used as BLOB_STORAGE_ACCOUNT_NAME env var in Container App"
}

output "acr_login_server" {
  value       = module.acr.login_server
  description = "ACR login server — used as image registry prefix for Container App"
}

output "ai_foundry_endpoint" {
  value       = module.ai_foundry.endpoint
  description = "AI Foundry endpoint URL"
}

output "postgres_fqdn" {
  value       = module.postgres.fqdn
  description = "PostgreSQL Flexible Server FQDN"
}

output "key_vault_uri" {
  value       = module.key_vault.uri
  description = "Key Vault URI"
}

output "container_app_name" {
  value       = module.container_apps.app_name
  description = "Container App name"
}

output "container_apps_env_id" {
  value       = module.container_apps.environment_id
  description = "Container Apps Environment resource ID"
}
