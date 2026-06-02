output "system_topic_id" {
  value       = azurerm_eventgrid_system_topic.this.id
  description = "Event Grid System Topic ARM resource ID"
}

output "identity_principal_id" {
  value       = azurerm_eventgrid_system_topic.this.identity[0].principal_id
  description = "System-assigned Managed Identity principal ID of the Event Grid topic"
}
