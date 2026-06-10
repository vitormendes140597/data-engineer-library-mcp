locals {
  # Role definition IDs (built-in Azure roles)
  roles = {
    storage_blob_data_reader             = "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"
    storage_blob_data_contributor        = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
    storage_queue_data_message_processor = "8a0f0c08-91a1-4084-bc3d-661d67233fed"
    cognitive_services_user              = "a97b65f3-24c7-4388-baec-2e87135dc908"
    key_vault_secrets_user               = "4633458b-17de-408a-b874-0445c86b69e6"
    acr_pull                             = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
    storage_queue_data_message_sender    = "c6a89b2d-59bc-44d0-9896-0f6e12d7b80a"
  }

  assignments = {
    ca_blob_reader = {
      principal_id = var.container_app_principal_id
      role_id      = local.roles.storage_blob_data_reader
      scope        = var.storage_account_resource_id
    }
    ca_blob_contributor = {
      principal_id = var.container_app_principal_id
      role_id      = local.roles.storage_blob_data_contributor
      scope        = var.storage_account_resource_id
    }
    ca_queue_consumer = {
      principal_id = var.container_app_principal_id
      role_id      = local.roles.storage_queue_data_message_processor
      scope        = var.storage_account_resource_id
    }
    ca_cognitive_user = {
      principal_id = var.container_app_principal_id
      role_id      = local.roles.cognitive_services_user
      scope        = var.ai_foundry_resource_id
    }
    ca_kv_secrets_user = {
      principal_id = var.container_app_principal_id
      role_id      = local.roles.key_vault_secrets_user
      scope        = var.key_vault_resource_id
    }
    ca_acr_pull = {
      principal_id = var.container_app_principal_id
      role_id      = local.roles.acr_pull
      scope        = var.acr_resource_id
    }
    reprocessor_blob_reader = {
      principal_id = var.reprocessor_principal_id
      role_id      = local.roles.storage_blob_data_reader
      scope        = var.storage_account_resource_id
    }
    reprocessor_blob_contributor = {
      principal_id = var.reprocessor_principal_id
      role_id      = local.roles.storage_blob_data_contributor
      scope        = var.storage_account_resource_id
    }
    reprocessor_cognitive_user = {
      principal_id = var.reprocessor_principal_id
      role_id      = local.roles.cognitive_services_user
      scope        = var.ai_foundry_resource_id
    }
    reprocessor_kv_secrets_user = {
      principal_id = var.reprocessor_principal_id
      role_id      = local.roles.key_vault_secrets_user
      scope        = var.key_vault_resource_id
    }
    reprocessor_acr_pull = {
      principal_id = var.reprocessor_principal_id
      role_id      = local.roles.acr_pull
      scope        = var.acr_resource_id
    }
    evgt_queue_sender = {
      principal_id = var.event_grid_principal_id
      role_id      = local.roles.storage_queue_data_message_sender
      scope        = var.storage_account_resource_id
    }
  }
}

resource "azurerm_role_assignment" "this" {
  for_each = local.assignments

  principal_id       = each.value.principal_id
  role_definition_id = "/providers/Microsoft.Authorization/roleDefinitions/${each.value.role_id}"
  scope              = each.value.scope
}
