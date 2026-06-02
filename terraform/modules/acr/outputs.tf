output "login_server" {
  value       = azurerm_container_registry.this.login_server
  description = "ACR login server (e.g. myacr.azurecr.io)"
}

output "resource_id" {
  value       = azurerm_container_registry.this.id
  description = "ACR ARM resource ID"
}
