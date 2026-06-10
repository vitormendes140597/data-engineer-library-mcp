## Why

The RAG pipeline architecture is defined, but the Terraform codebase must provision the concrete Azure runtime that supports queue-triggered PDF ingestion, scheduled reprocessing, extracted image storage, PostgreSQL pgvector, Azure AI Foundry embeddings, secrets, and observability. This change makes the cloud infrastructure ready for the implementation work without mixing application behavior into the infrastructure change.

## What Changes

- Extend Terraform storage resources to support raw PDF uploads, extracted image blobs, queue messages for PDF lifecycle events, and any poison/failure-support queues still needed for infrastructure failures.
- Configure Event Grid subscriptions for both `Microsoft.Storage.BlobCreated` and `Microsoft.Storage.BlobDeleted` events from the raw PDF container into Storage Queue.
- Configure the queue-scaled Azure Container App for one-message-per-process ingestion with KEDA queue scaling.
- Add a scheduled Azure Container App Job for failed PDF reprocessing.
- Ensure Terraform exposes the application settings, secrets, identities, and role assignments required by the RAG worker and reprocessor.
- Ensure Azure AI Foundry, PostgreSQL Flexible Server with pgvector support, Key Vault, ACR, Log Analytics, and Application Insights are wired for the RAG runtime.
- Add or update Terraform outputs and environment variables needed by local deployment and CI/CD.

## Capabilities

### New Capabilities

- `rag-infra-runtime`: Terraform provisions the Azure runtime required for queue-driven RAG ingestion and scheduled failure reprocessing.
- `rag-infra-events`: Terraform routes blob create/delete lifecycle events into the queue consumed by the ingestion runtime.
- `rag-infra-secrets-rbac`: Terraform configures managed identity, Key Vault references, and RBAC for storage, queue, ACR, Azure AI Foundry, PostgreSQL connectivity, and observability.

### Modified Capabilities

None.

## Impact

- Affected code: `terraform/main.tf`, `terraform/locals.tf`, `terraform/variables.tf`, `terraform/outputs.tf`, `terraform/environments/*.tfvars`, and modules under `terraform/modules/*`.
- Affected Azure systems: Blob Storage, Storage Queue, Event Grid, Container Apps, Container App Jobs, ACR, Azure AI Foundry, PostgreSQL Flexible Server, Key Vault, Log Analytics, Application Insights, and RBAC assignments.
- Downstream dependency: the application implementation change will consume the Terraform-provided queue, storage containers, environment variables, identities, and secrets.
