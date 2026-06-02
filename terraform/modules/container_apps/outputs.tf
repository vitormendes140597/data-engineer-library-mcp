output "environment_id" {
  value       = azurerm_container_app_environment.this.id
  description = "Container Apps Environment ARM resource ID"
}

output "app_name" {
  value       = azurerm_container_app.rag_worker.name
  description = "Container App name"
}

output "app_id" {
  value       = azurerm_container_app.rag_worker.id
  description = "Container App ARM resource ID"
}

output "identity_principal_id" {
  value       = azurerm_container_app.rag_worker.identity[0].principal_id
  description = "System-assigned Managed Identity principal ID of the Container App"
}
