## 1. Storage and Events

- [x] 1.1 Extend the storage module with a private extracted-images container and outputs for raw PDF container, extracted image container, and processing queue names.
- [x] 1.2 Add or verify queue settings required by the ingestion worker, including queue name, visibility timeout assumptions, and poison/failure-support queue decisions.
- [x] 1.3 Extend the Event Grid module so PDF BlobCreated events from `raw-pdfs` are routed to `pdf-processing-jobs`.
- [x] 1.4 Extend the Event Grid module so PDF BlobDeleted events from `raw-pdfs` are routed to `pdf-processing-jobs`.
- [x] 1.5 Verify Event Grid subject filters ignore non-PDF blobs and blobs outside `raw-pdfs`.

## 2. Container Apps Runtime

- [x] 2.1 Update the Container Apps module with ingestion worker settings for queue name, storage account, raw PDF container, extracted image container, and one-message worker mode.
- [x] 2.2 Verify the ingestion Container App has scale-to-zero enabled and a KEDA Azure Queue scaler for `pdf-processing-jobs`.
- [x] 2.3 Add an Azure Container App Job for scheduled failure reprocessing using the same RAG image.
- [x] 2.4 Configure the reprocessor job schedule, retry/concurrency settings, command or environment mode, and required runtime environment variables.
- [x] 2.5 Add Terraform variables for image tag, reprocessor schedule, max replicas/parallelism, queue/container names where needed.

## 3. Secrets and RBAC

- [x] 3.1 Ensure Key Vault exposes secret references for PostgreSQL connection string, Azure AI Foundry endpoint, and Application Insights connection string.
- [x] 3.2 Grant ingestion and reprocessor identities Key Vault Secrets User access.
- [x] 3.3 Grant ingestion and reprocessor identities blob permissions for raw PDF reads and extracted image writes/deletes.
- [x] 3.4 Grant ingestion identity queue consumer permissions for `pdf-processing-jobs`.
- [x] 3.5 Grant Event Grid system topic identity queue sender permissions.
- [x] 3.6 Grant ingestion and reprocessor identities ACR pull and Azure AI Foundry user permissions.

## 4. Root Wiring and Outputs

- [x] 4.1 Wire new module variables and outputs through `terraform/main.tf`, `locals.tf`, `variables.tf`, and `outputs.tf`.
- [x] 4.2 Update `terraform/environments/*.tfvars` with environment-specific values for schedule, image tag, and runtime settings.
- [x] 4.3 Update Terraform README or deployment notes with the ingestion app and scheduled reprocessor job.

## 5. Verification

- [ ] 5.1 Run `terraform fmt -recursive`. (Skipped per user feedback - will do format later)
- [x] 5.2 Run `terraform validate`.
- [ ] 5.3 Run a dev environment `terraform plan` and verify storage, Event Grid, Container App, Container App Job, Key Vault, and RBAC changes are present. (Skipped per user feedback)
