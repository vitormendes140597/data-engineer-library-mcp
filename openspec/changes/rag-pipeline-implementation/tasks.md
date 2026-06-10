## 1. Project Setup

- [x] 1.1 Create the RAG pipeline Python package structure for queue handling, event parsing, blob access, PDF extraction, chunking, embeddings, persistence, and reprocessing.
- [x] 1.2 Add dependencies for Azure Blob Storage, Azure Storage Queue, Azure Identity, Azure AI Projects, PyMuPDF, LangChain, SQLAlchemy, Alembic, pgvector support, python-dotenv, and test tooling.
- [x] 1.3 Add configuration loading with `python-dotenv` for queue, storage mode, Azurite endpoints/connection string, database, embedding provider, Azure AI Foundry, chunking, retry, and observability settings.
- [x] 1.4 Add Docker entrypoints or commands for ingestion worker mode, reprocessor mode, and local helper commands.
- [x] 1.5 Extend root Docker Compose with Azurite and PostgreSQL pgvector services for local RAG development.
- [x] 1.6 Add a local bootstrap command that creates the Azurite containers and queue required by the RAG worker.

## 2. Database Schema and Migrations

- [x] 2.1 Initialize Alembic migration configuration for the RAG pipeline.
- [x] 2.2 Add migrations for required PostgreSQL extensions, including pgvector support.
- [x] 2.3 Add migrations for `documents`, `chunks`, `images`, `chunk_images`, and `processing_failures`.
- [x] 2.4 Add constraints and indexes for `documents.blob_url`, document chunk ordering, chunk-image relations, failure status selection, and pgvector HNSW search.
- [x] 2.5 Implement SQLAlchemy models and repository methods for document state, replacement, deletion, image metadata, chunk storage, and failure records.

## 3. Queue and Event Handling

- [x] 3.1 Implement one-message Storage Queue receive/delete behavior with visibility timeout handling.
- [x] 3.2 Parse Event Grid BlobCreated and BlobDeleted payloads from Storage Queue messages.
- [x] 3.3 Implement BlobCreated skip logic when an existing document has the same content length.
- [x] 3.4 Implement BlobCreated replacement logic when an existing document has a different content length.
- [x] 3.5 Implement BlobDeleted cleanup for chunks, vectors, image links, image metadata, and extracted image blobs.
- [x] 3.6 Implement local CLI helper commands to upload PDFs to Azurite and enqueue Event Grid-shaped BlobCreated messages.
- [x] 3.7 Implement local CLI helper commands to enqueue Event Grid-shaped BlobDeleted messages for Azurite blob URLs.

## 4. PDF Extraction and Chunking

- [x] 4.1 Implement Blob Storage PDF download using Azure credentials.
- [x] 4.2 Implement PyMuPDF markdown extraction with page provenance and hierarchy metadata where available.
- [x] 4.3 Implement PyMuPDF image extraction and upload extracted images to the configured Blob container.
- [x] 4.4 Persist image metadata including blob path, blob URL, source page, dimensions, format, bbox where available, and metadata.
- [x] 4.5 Implement LangChain text chunking with page ranges, heading metadata, chunk indexes, and chunk metadata.
- [x] 4.6 Link each chunk to all extracted images whose source pages fall within the chunk page range.

## 5. Embeddings and Persistence

- [x] 5.1 Implement configurable embedding provider selection for `fake` and `azure_ai_foundry`.
- [x] 5.2 Implement deterministic fake embedding generation for local/offline development and tests.
- [x] 5.3 Implement Azure AI Projects embedding client integration for the configured Foundry embedding deployment.
- [x] 5.4 Batch embedding requests within model token and service limits.
- [x] 5.5 Store chunk text, metadata, page range, image links, and embedding vectors transactionally.
- [x] 5.6 Add cleanup for old extracted image blobs during replacement and source PDF deletion.

## 6. Failure Handling and Reprocessing

- [x] 6.1 Record processing failures with blob URL, event payload, failure stage, error details, attempt count, status, and next retry time.
- [x] 6.2 Ensure queue messages are deleted after failure records are durably stored.
- [x] 6.3 Implement scheduled reprocessor entrypoint that selects due pending failures.
- [x] 6.4 Claim failure rows with database locking so concurrent reprocessor executions do not process the same row.
- [x] 6.5 Retry failed PDF processing up to three times, then mark failures as `permanently_failed`.
- [x] 6.6 Mark failure records as `resolved` when reprocessing succeeds.

## 7. Tests and Documentation

- [x] 7.1 Add unit tests for Event Grid payload parsing and unsupported event handling.
- [x] 7.2 Add unit tests for same-size skip, changed-size replacement, and BlobDeleted cleanup decisions.
- [x] 7.3 Add unit tests for page-range image-to-chunk linking.
- [x] 7.4 Add unit tests for failure retry state transitions and max-attempt behavior.
- [x] 7.5 Add unit tests for embedding provider selection and deterministic fake embedding output.
- [x] 7.6 Add integration tests for Alembic migrations and repository operations against local PostgreSQL pgvector.
- [x] 7.7 Add integration tests for Blob download/upload and Queue receive/delete behavior against Azurite.
- [x] 7.8 Add integration tests or CLI tests for local Event Grid-shaped message enqueueing.
- [x] 7.9 Update `rag-pipeline/README.md` with local setup, `.env` variables, migrations, worker commands, reprocessor commands, local helper commands, and required environment variables.
