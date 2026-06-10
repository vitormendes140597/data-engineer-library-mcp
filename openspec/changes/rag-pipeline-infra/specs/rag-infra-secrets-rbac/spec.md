## ADDED Requirements

### Requirement: Runtime secret references
Terraform SHALL configure Key Vault-backed secret references for database, Azure AI Foundry, and observability settings required by the ingestion and reprocessor runtimes.

#### Scenario: Secret references configured
- **WHEN** Terraform is applied
- **THEN** the ingestion Container App and reprocessor Container App Job can read their configured Key Vault secret references through managed identity

### Requirement: Storage permissions
Terraform SHALL grant the ingestion and reprocessor identities permissions to read raw PDFs, write and delete extracted image blobs, and consume queue messages.

#### Scenario: Ingestion storage access granted
- **WHEN** Terraform is applied
- **THEN** the ingestion identity has data-plane access to read blobs, manage extracted image blobs, and consume queue messages

#### Scenario: Reprocessor storage access granted
- **WHEN** Terraform is applied
- **THEN** the reprocessor identity has data-plane access to read blobs and manage extracted image blobs

### Requirement: Event Grid queue sender permission
Terraform SHALL grant the Event Grid system topic identity permission to send messages to the processing queue.

#### Scenario: Event Grid can enqueue
- **WHEN** Blob Storage emits a matching lifecycle event
- **THEN** Event Grid can write the event message to the Storage Queue

### Requirement: ACR and Azure AI Foundry permissions
Terraform SHALL grant the runtime identities permission to pull the RAG image from ACR and call the Azure AI Foundry embedding deployment.

#### Scenario: Runtime can start and embed
- **WHEN** an ingestion or reprocessor container starts
- **THEN** it can pull its image and authenticate to the configured Azure AI Foundry resource
