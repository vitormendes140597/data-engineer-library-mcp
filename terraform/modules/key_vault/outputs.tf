output "uri" {
  value       = azurerm_key_vault.this.vault_uri
  description = "Key Vault URI"
}

output "resource_id" {
  value       = azurerm_key_vault.this.id
  description = "Key Vault ARM resource ID"
}

output "postgresql_secret_versionless_id" {
  value       = "${azurerm_key_vault.this.vault_uri}secrets/postgresql-connection-string"
  description = "Versionless URI for the PostgreSQL connection string secret"
}

output "openai_secret_versionless_id" {
  value       = "${azurerm_key_vault.this.vault_uri}secrets/openai-endpoint"
  description = "Versionless URI for the AI Foundry endpoint secret"
}

output "appinsights_secret_versionless_id" {
  value       = "${azurerm_key_vault.this.vault_uri}secrets/applicationinsights-connection-string"
  description = "Versionless URI for the App Insights connection string secret"
}
