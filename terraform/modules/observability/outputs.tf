output "workspace_id" {
  value       = azurerm_log_analytics_workspace.this.workspace_id
  description = "Log Analytics Workspace GUID (customer_id)"
}

output "workspace_resource_id" {
  value       = azurerm_log_analytics_workspace.this.id
  description = "Log Analytics Workspace ARM resource ID"
}

output "appinsights_connection_string" {
  value       = azurerm_application_insights.this.connection_string
  description = "Application Insights connection string"
  sensitive   = true
}

output "instrumentation_key" {
  value       = azurerm_application_insights.this.instrumentation_key
  description = "Application Insights instrumentation key"
  sensitive   = true
}
