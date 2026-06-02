output "name" {
  value       = azurerm_storage_account.this.name
  description = "Storage account name"
}

output "resource_id" {
  value       = azurerm_storage_account.this.id
  description = "Storage account ARM resource ID"
}

output "primary_blob_endpoint" {
  value       = azurerm_storage_account.this.primary_blob_endpoint
  description = "Primary blob service endpoint"
}

output "queue_name" {
  value       = azurerm_storage_queue.jobs.name
  description = "Processing queue name"
}
