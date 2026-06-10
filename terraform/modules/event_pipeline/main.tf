resource "azurerm_eventgrid_system_topic" "this" {
  name                   = var.system_topic_name
  resource_group_name    = var.resource_group_name
  location               = var.location
  source_arm_resource_id = var.source_arm_resource_id
  topic_type             = "Microsoft.Storage.StorageAccounts"

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_eventgrid_system_topic_event_subscription" "pdf_created_to_queue" {
  name                = var.subscription_name
  system_topic        = azurerm_eventgrid_system_topic.this.name
  resource_group_name = var.resource_group_name

  included_event_types = ["Microsoft.Storage.BlobCreated"]

  subject_filter {
    subject_begins_with = "/blobServices/default/containers/raw-pdfs"
    subject_ends_with   = ".pdf"
  }

  storage_queue_endpoint {
    storage_account_id = var.storage_account_id
    queue_name         = var.queue_name
  }
}

resource "azurerm_eventgrid_system_topic_event_subscription" "pdf_deleted_to_queue" {
  name                = "${var.subscription_name}-deleted"
  system_topic        = azurerm_eventgrid_system_topic.this.name
  resource_group_name = var.resource_group_name

  included_event_types = ["Microsoft.Storage.BlobDeleted"]

  subject_filter {
    subject_begins_with = "/blobServices/default/containers/raw-pdfs"
    subject_ends_with   = ".pdf"
  }

  storage_queue_endpoint {
    storage_account_id = var.storage_account_id
    queue_name         = var.queue_name
  }
}
