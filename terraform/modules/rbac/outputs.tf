output "role_assignment_ids" {
  value       = { for k, v in azurerm_role_assignment.this : k => v.id }
  description = "Map of RBAC assignment keys to ARM resource IDs"
}
