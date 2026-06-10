## ADDED Requirements

### Requirement: Local storage emulation
The RAG implementation SHALL support local Blob Storage and Storage Queue development using Azurite from the root Docker Compose file.

#### Scenario: Local storage services available
- **WHEN** the local RAG Docker Compose services are started
- **THEN** Azurite exposes Blob and Queue endpoints usable by the RAG worker and local helper

#### Scenario: Worker uses Azurite storage
- **WHEN** the worker is configured for local storage mode
- **THEN** it reads raw PDFs, writes extracted images, and receives queue messages through Azurite endpoints

### Requirement: Local PostgreSQL pgvector
The root Docker Compose setup SHALL provide a PostgreSQL service with pgvector support for local RAG development.

#### Scenario: Local migrations applied
- **WHEN** Alembic migrations run against the local database
- **THEN** the database supports the RAG schema and vector columns required by the worker

### Requirement: Local environment loading
The RAG implementation SHALL use `python-dotenv` to load local `.env` values before constructing runtime settings, while preserving real process environment variable precedence.

#### Scenario: Local `.env` loaded
- **WHEN** a developer runs the worker or local helper from the host with a `.env` file present
- **THEN** RAG settings are resolved from `.env` values unless the same variables are already set in the process environment

### Requirement: Local Event Grid message helper
The RAG implementation SHALL provide a CLI helper that uploads PDFs to Azurite and enqueues Event Grid-shaped BlobCreated messages into the local Storage Queue.

#### Scenario: Local PDF upload enqueues create event
- **WHEN** a developer runs the helper to upload a PDF
- **THEN** the helper uploads the PDF to the `raw-pdfs` Azurite container and enqueues a BlobCreated payload referencing the Azurite blob URL

### Requirement: Local delete message helper
The RAG implementation SHALL provide a CLI helper that enqueues Event Grid-shaped BlobDeleted messages for Azurite blob URLs.

#### Scenario: Local delete event enqueued
- **WHEN** a developer runs the helper to delete or simulate deletion for a local PDF
- **THEN** the helper enqueues a BlobDeleted payload referencing the Azurite blob URL

### Requirement: Configurable embedding provider
The RAG implementation SHALL select the embedding provider from configuration and support both deterministic fake embeddings and Azure AI Foundry embeddings.

#### Scenario: Fake embeddings selected
- **WHEN** the embedding provider is configured as `fake`
- **THEN** the worker generates deterministic vectors without calling Azure AI Foundry

#### Scenario: Azure AI Foundry embeddings selected
- **WHEN** the embedding provider is configured as `azure_ai_foundry`
- **THEN** the worker calls the configured Azure AI Foundry embedding deployment
