provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  subscription_id = var.subscription_id
}

# ─── Resource Group ───────────────────────────────────────────────────────────

data "azurerm_resource_group" "main" {
  name = local.resource_group_name
}

# ─── Phase 1: Observability ───────────────────────────────────────────────────

module "observability" {
  source = "./modules/observability"

  name                = local.log_analytics_name
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  appinsights_name    = local.appinsights_name
  tags                = local.tags
}

# ─── Phase 2: Core Infrastructure (provisioned in parallel) ──────────────────

module "storage" {
  source = "./modules/storage"

  name                = local.storage_account_name
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  tags                = local.tags
}

module "acr" {
  source = "./modules/acr"

  name                = local.acr_name
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  tags                = local.tags
}

module "ai_foundry" {
  source = "./modules/ai_foundry"

  name                  = local.ai_foundry_name
  resource_group_name   = data.azurerm_resource_group.main.name
  location              = data.azurerm_resource_group.main.location
  custom_subdomain_name = local.ai_foundry_name
  tags                  = local.tags
}

module "postgres" {
  source = "./modules/postgres"

  name                   = local.postgres_name
  resource_group_name    = data.azurerm_resource_group.main.name
  location               = data.azurerm_resource_group.main.location
  administrator_login    = var.postgres_admin_login
  administrator_password = var.postgres_admin_password
  tags                   = local.tags
}

module "key_vault" {
  source = "./modules/key_vault"

  name                = local.key_vault_name
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  tenant_id           = var.tenant_id
  tags                = local.tags

  postgresql_connection_string          = "postgresql://${var.postgres_admin_login}:${var.postgres_admin_password}@${module.postgres.fqdn}:5432/ragdb?sslmode=require"
  openai_endpoint                       = module.ai_foundry.endpoint
  applicationinsights_connection_string = module.observability.appinsights_connection_string
}

# ─── Phase 3: Event Pipeline & Container Apps Runtime ────────────────────────

module "event_pipeline" {
  source = "./modules/event_pipeline"

  system_topic_name      = local.event_grid_topic_name
  subscription_name      = local.event_grid_subscription_name
  resource_group_name    = data.azurerm_resource_group.main.name
  location               = data.azurerm_resource_group.main.location
  source_arm_resource_id = module.storage.resource_id
  storage_account_id     = module.storage.resource_id
  queue_name             = "pdf-processing-jobs"
  tags                   = local.tags
}

module "container_apps" {
  source = "./modules/container_apps"

  environment_name                    = local.container_apps_env_name
  app_name                            = local.container_app_name
  resource_group_name                 = data.azurerm_resource_group.main.name
  location                            = data.azurerm_resource_group.main.location
  log_analytics_workspace_resource_id = module.observability.workspace_resource_id
  acr_login_server                    = module.acr.login_server
  storage_account_name                = module.storage.name
  raw_pdf_container_name              = module.storage.raw_pdf_container_name
  extracted_images_container_name     = module.storage.extracted_images_container_name
  queue_name                          = module.storage.queue_name
  postgresql_secret_versionless_id    = module.key_vault.postgresql_secret_versionless_id
  openai_secret_versionless_id        = module.key_vault.openai_secret_versionless_id
  appinsights_secret_versionless_id   = module.key_vault.appinsights_secret_versionless_id
  image_tag                           = var.image_tag
  reprocessor_schedule                = var.reprocessor_schedule
  reprocessor_max_parallelism         = var.reprocessor_max_parallelism
  tags                                = local.tags
}

# ─── Phase 4: RBAC ───────────────────────────────────────────────────────────

module "rbac" {
  source = "./modules/rbac"

  container_app_principal_id  = module.container_apps.identity_principal_id
  reprocessor_principal_id    = module.container_apps.reprocessor_identity_principal_id
  event_grid_principal_id     = module.event_pipeline.identity_principal_id
  storage_account_resource_id = module.storage.resource_id
  acr_resource_id             = module.acr.resource_id
  ai_foundry_resource_id      = module.ai_foundry.resource_id
  key_vault_resource_id       = module.key_vault.resource_id
}
