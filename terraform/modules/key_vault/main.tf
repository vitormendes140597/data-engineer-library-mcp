data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  name                       = var.name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  tenant_id                  = var.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# Grant the Terraform execution principal Secrets Officer so it can create secrets.
resource "azurerm_role_assignment" "tf_secrets_officer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_key_vault_secret" "postgresql_connection_string" {
  name         = "postgresql-connection-string"
  value        = var.postgresql_connection_string
  key_vault_id = azurerm_key_vault.this.id

  depends_on = [azurerm_role_assignment.tf_secrets_officer]
}

resource "azurerm_key_vault_secret" "openai_endpoint" {
  name         = "openai-endpoint"
  value        = var.openai_endpoint
  key_vault_id = azurerm_key_vault.this.id

  depends_on = [azurerm_role_assignment.tf_secrets_officer]
}

resource "azurerm_key_vault_secret" "applicationinsights_connection_string" {
  name         = "applicationinsights-connection-string"
  value        = var.applicationinsights_connection_string
  key_vault_id = azurerm_key_vault.this.id

  depends_on = [azurerm_role_assignment.tf_secrets_officer]
}
