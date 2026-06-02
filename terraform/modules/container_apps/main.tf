resource "azurerm_container_app_environment" "this" {
  name                       = var.environment_name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  log_analytics_workspace_id = var.log_analytics_workspace_resource_id
  tags                       = var.tags
}

resource "azurerm_container_app" "rag_worker" {
  name                         = var.app_name
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type = "SystemAssigned"
  }

  registry {
    server = var.acr_login_server
    # Use system-assigned MI for ACR authentication (no admin credentials)
    identity = "System"
  }

  # Key Vault secret references — Container App reads these via its system MI.
  # The MI needs "Key Vault Secrets User" role (granted in rbac module).
  secret {
    name                = "postgresql-connection-string"
    identity            = "System"
    key_vault_secret_id = var.postgresql_secret_versionless_id
  }

  secret {
    name                = "openai-endpoint"
    identity            = "System"
    key_vault_secret_id = var.openai_secret_versionless_id
  }

  secret {
    name                = "applicationinsights-connection-string"
    identity            = "System"
    key_vault_secret_id = var.appinsights_secret_versionless_id
  }

  template {
    min_replicas = 0
    max_replicas = 5

    container {
      name   = "rag-worker"
      image  = "${var.acr_login_server}/de-agent-rag:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "BLOB_STORAGE_ACCOUNT_NAME"
        value = var.storage_account_name
      }

      env {
        name        = "POSTGRES_CONNECTION_STRING"
        secret_name = "postgresql-connection-string"
      }

      env {
        name        = "OPENAI_ENDPOINT"
        secret_name = "openai-endpoint"
      }

      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "applicationinsights-connection-string"
      }
    }

    # KEDA azure-queue scaler — workload identity (system MI) for queue auth
    custom_scale_rule {
      name             = "queue-length"
      custom_rule_type = "azure-queue"
      metadata = {
        queueName             = "pdf-processing-jobs"
        accountName           = var.storage_account_name
        queueLength           = "1"
        activationQueueLength = "0"
      }
    }
  }
}
