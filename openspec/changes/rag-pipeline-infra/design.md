## Context

The repository already contains Terraform modules for the RAG Azure baseline: storage, Event Grid, ACR, Container Apps, Azure AI Foundry, PostgreSQL, Key Vault, observability, and RBAC. The architecture now requires two runtime paths: a queue-scaled ingestion Container App that processes one Storage Queue message per process, and a scheduled Container App Job that retries failed processing records from PostgreSQL.

The current Terraform state is close to the desired shape, but it only routes BlobCreated PDF events, stores raw PDFs, and defines a single Container App worker. It must be extended for BlobDeleted events, extracted image blob storage, a scheduled reprocessor job, and a clearer configuration contract for the implementation.

## Goals / Non-Goals

**Goals:**

- Provision Storage containers for raw PDFs and extracted images.
- Route BlobCreated and BlobDeleted PDF events from `raw-pdfs` into a Storage Queue.
- Configure a queue-scaled ingestion Container App with scale-to-zero and one-message-per-process runtime settings.
- Configure a scheduled Azure Container App Job for database-backed failure reprocessing.
- Provide secrets, app settings, outputs, and RBAC assignments required by the ingestion and reprocessor workloads.
- Keep the design budget-conscious by preserving public-network Azure services unless the existing architecture says otherwise.

**Non-Goals:**

- Implement the Python RAG worker.
- Define the PostgreSQL schema or Alembic migrations in Terraform.
- Add private endpoints, VNet integration, or production HA beyond the existing architecture.
- Build the query/retrieval application.

## Decisions

### Use Separate Runtime Resources for Ingestion and Reprocessing

Terraform will manage the ingestion worker as an `azurerm_container_app` and the reprocessor as an `azurerm_container_app_job`.

Alternative considered: run both modes in the same queue-scaled Container App. That would blur operational ownership and require the container to schedule its own retries. A Container App Job maps more directly to the database-backed retry table and keeps queue processing independent from process retry semantics.

### Keep Blob Lifecycle Events in One Processing Queue

Event Grid subscriptions will route both BlobCreated and BlobDeleted PDF events into the same Storage Queue. The application will branch on `eventType`.

Alternative considered: separate queues for create and delete. Separate queues can simplify consumers but requires more KEDA wiring and more runtime configuration. A single event queue is sufficient because payloads include event type and the worker processes one message at a time.

### Store Extracted Images in Blob Storage

Terraform will create a private container for extracted image artifacts. The implementation will write image blobs there and store image blob paths/URLs in PostgreSQL.

Alternative considered: store extracted images in PostgreSQL. Blob Storage is cheaper, better suited for binary artifacts, and aligns with the raw PDF storage model.

### Use Managed Identity Where Azure Services Support It

The Container App and Container App Job will use managed identity for Blob Storage, Queue Storage, Key Vault, ACR, Azure AI Foundry, and observability access. PostgreSQL connection details will remain in Key Vault because the architecture uses PostgreSQL user/password authentication.

Alternative considered: store storage connection strings for all access. Managed identity reduces secret surface area and matches the existing Terraform direction.

### Keep Schema Management in the Application Change

Terraform will provision PostgreSQL and enable required service configuration, but Alembic migrations in the implementation change will manage tables, pgvector extension setup, and indexes.

Alternative considered: manage tables through Terraform SQL execution. Database schema evolves with application code, so keeping it with Alembic gives better reviewability, local parity, and rollback control.

## Risks / Trade-offs

- [Risk] Azure Storage Queue processing is at-least-once, and duplicate events can happen. -> Mitigation: expose configuration that lets the application use database document state and locks for idempotency.
- [Risk] Container App Job schedule may retry failures later than desired. -> Mitigation: use a configurable cron schedule and start with a frequent schedule such as every 5 or 10 minutes.
- [Risk] KEDA identity support can vary by provider/API version. -> Mitigation: validate the Terraform provider supports identity-based `azure-queue` scaling; if not, use a Key Vault-backed storage connection secret as a fallback.
- [Risk] BlobDeleted events can arrive after reprocessing starts. -> Mitigation: route delete events through the same queue and require the application to check current document state before writes.
- [Risk] Public network access lowers security posture. -> Mitigation: keep RBAC strict and leave private endpoint/VNet hardening as a future architecture upgrade.

## Migration Plan

1. Extend storage module with extracted image container and queue outputs.
2. Extend Event Grid module to include BlobDeleted PDF events.
3. Extend Container Apps module with the scheduled reprocessor Container App Job and shared environment settings.
4. Extend RBAC module to grant the app/job identities required storage, queue, ACR, Key Vault, and Azure AI Foundry roles.
5. Add environment variables, variables, outputs, and tfvars defaults.
6. Run `terraform fmt -recursive`, `terraform validate`, and an environment plan.

Rollback: remove the scheduled job and new Event Grid subscriptions first, then remove the extracted images container only after confirming no image artifacts need retention.

## Open Questions

- Should the reprocessor cron start at every 5 minutes or every 10 minutes?
  - Answer: It should run once a day at 11 PM UTC - 3
- Should the extracted image container be in the same storage account as raw PDFs or a separate storage account for lifecycle-policy separation?
  - Answer: It should be in the same storage account but a different container
