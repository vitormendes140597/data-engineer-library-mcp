## ADDED Requirements

### Requirement: Queue-scaled ingestion runtime
Terraform SHALL provision an Azure Container App ingestion runtime that scales from zero based on the `pdf-processing-jobs` Storage Queue.

#### Scenario: Queue scaler configured
- **WHEN** Terraform is applied
- **THEN** the ingestion Container App has a KEDA Azure Queue scale rule for `pdf-processing-jobs`

#### Scenario: Scale to zero configured
- **WHEN** no queue messages are available
- **THEN** the ingestion Container App can scale to zero replicas

### Requirement: One-message process configuration
Terraform SHALL provide environment configuration that allows the ingestion container to process one queue message and exit.

#### Scenario: Worker mode configured
- **WHEN** the ingestion Container App starts a replica
- **THEN** the container receives settings for queue name, storage account, raw PDF container, extracted image container, and one-message worker mode

### Requirement: Scheduled reprocessor job
Terraform SHALL provision an Azure Container App Job that runs the failure reprocessor on a cron schedule.

#### Scenario: Reprocessor job configured
- **WHEN** Terraform is applied
- **THEN** a Container App Job exists with a schedule trigger and access to the same image, secrets, and storage settings required for reprocessing

#### Scenario: Reprocessor concurrency bounded
- **WHEN** the scheduled job is configured
- **THEN** Terraform limits job parallelism so concurrent executions do not exceed the configured maximum

### Requirement: Extracted image storage
Terraform SHALL provision a private Blob Storage container for extracted image artifacts.

#### Scenario: Image container created
- **WHEN** Terraform is applied
- **THEN** the storage account contains a private container for extracted PDF images
