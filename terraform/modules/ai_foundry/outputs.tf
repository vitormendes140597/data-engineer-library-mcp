output "endpoint" {
  value       = azurerm_cognitive_account.this.endpoint
  description = "AI Foundry endpoint URL"
}

output "resource_id" {
  value       = azurerm_cognitive_account.this.id
  description = "Cognitive Services account ARM resource ID"
}
