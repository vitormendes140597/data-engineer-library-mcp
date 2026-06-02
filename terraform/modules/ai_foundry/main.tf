# Azure AI Foundry is provisioned as a Cognitive Services account with kind=AIServices.
resource "azurerm_cognitive_account" "this" {
  name                  = var.name
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = "AIServices"
  sku_name              = var.sku_name
  custom_subdomain_name = var.custom_subdomain_name
  tags                  = var.tags
}
