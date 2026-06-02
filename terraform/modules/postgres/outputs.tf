output "fqdn" {
  value       = azurerm_postgresql_flexible_server.this.fqdn
  description = "PostgreSQL Flexible Server FQDN"
}

output "resource_id" {
  value       = azurerm_postgresql_flexible_server.this.id
  description = "PostgreSQL Flexible Server ARM resource ID"
}

output "database_name" {
  value       = azurerm_postgresql_flexible_server_database.ragdb.name
  description = "Application database name"
}
