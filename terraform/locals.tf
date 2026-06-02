locals {
  tags = {
    environment = var.environment
    project     = "de-agent-rag"
  }

  resource_group_name          = "rg-de-agent-rag-${var.environment}"
  log_analytics_name           = "log-de-agent-rag-${var.environment}"
  appinsights_name             = "appi-de-agent-rag-${var.environment}"
  storage_account_name         = "stdeagentrag${var.environment}"
  event_grid_topic_name        = "evgt-de-agent-rag-${var.environment}"
  event_grid_subscription_name = "evgs-pdf-to-queue-${var.environment}"
  acr_name                     = "acrdeagentrag${var.environment}"
  ai_foundry_name              = "foundry-de-agent-rag-${var.environment}"
  postgres_name                = "psql-de-agent-rag-${var.environment}"
  key_vault_name               = "kv-de-agent-rag-${var.environment}"
  container_apps_env_name      = "cae-de-agent-rag-${var.environment}"
  container_app_name           = "ca-de-agent-rag-${var.environment}"
}
