variable "system_topic_name" {
  type        = string
  description = "Event Grid System Topic name"
}

variable "subscription_name" {
  type        = string
  description = "Event Grid System Topic Subscription name"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "source_arm_resource_id" {
  type        = string
  description = "ARM resource ID of the source storage account"
}

variable "storage_account_id" {
  type        = string
  description = "ARM resource ID of the storage account (for the queue endpoint)"
}

variable "queue_name" {
  type        = string
  description = "Storage queue name for event delivery"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
