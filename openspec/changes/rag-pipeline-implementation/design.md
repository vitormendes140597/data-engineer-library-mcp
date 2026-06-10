## Context

The `rag-pipeline/` directory is currently a placeholder for extraction, chunking, embeddings, and vector storage. The target runtime is an Azure Container App that scales from Storage Queue depth and runs one message per process, plus a scheduled Container App Job that retries failed processing records from PostgreSQL.

The worker receives Event Grid BlobCreated and BlobDeleted payloads through Azure Storage Queue. Blob URL is the document identity. If a BlobCreated event points to a previously processed document with the same PDF size, processing is skipped. If size differs, old chunks and extracted images are replaced. BlobDeleted events remove vectors, chunks, image links, image metadata, and extracted image blobs.

## Goals / Non-Goals

**Goals:**

- Implement one-message ingestion process semantics.
- Parse Event Grid BlobCreated and BlobDeleted queue messages.
- Download PDFs from Blob Storage using Azure credentials.
- Support local Blob Storage and Storage Queue development through Azurite.
- Parse PDFs with PyMuPDF into hierarchy-preserving markdown.
- Extract PDF images into Blob Storage and persist image metadata.
- Chunk markdown with page ranges and heading metadata using LangChain.
- Generate embeddings through a configurable provider, with Azure AI Foundry for real embeddings and deterministic fake embeddings for local/offline development.
- Store vectors and metadata in PostgreSQL pgvector using SQLAlchemy.
- Manage schema through Alembic migrations.
- Persist failed processing records and retry them through a scheduled reprocessor, max three attempts.
- Provide root Docker Compose services for local Azurite and PostgreSQL pgvector.
- Provide a CLI helper for local PDF upload and Event Grid-shaped queue message creation.

**Non-Goals:**

- Build the end-user query/retrieval interface.
- Interpret, caption, classify, or embed images.
- Use LangGraph.
- Implement private networking or Terraform infrastructure.
- Guarantee exactly-once queue processing; the system will be idempotent under at-least-once delivery.

## Decisions

### Use Blob URL as Document Identity

The `documents.blob_url` column will be unique and serve as the document identity. For change detection, the worker will compare the incoming PDF size to the stored `content_length`.

Alternative considered: use blob name, ETag, or content hash as identity. Blob URL is stable and globally resolvable for the source document. ETag/content hash are better as version indicators than primary identity.

### Use Size-Based Skip With Replacement on Change

When a BlobCreated event arrives for an existing document with the same `content_length`, the worker will skip processing. When size differs, it will delete old chunks, chunk-image links, image metadata, and extracted image blobs before storing the new version.

Alternative considered: always reprocess. Always reprocessing is simpler but wastes embedding and parsing cost for duplicate events.

### Use Page-Range Image Linking

Each chunk will carry `page_start` and `page_end`. Every extracted image whose source page falls within that inclusive page range will be linked to the chunk through `chunk_images`.

Alternative considered: geometric proximity linking. Page-range linking is deterministic, simple, and matches the requirement that chunks can span multiple pages and should link all pictures from those pages.

### Keep Image Files in Blob Storage

PyMuPDF-extracted images will be written to an extracted-images Blob container. PostgreSQL will store `image_blob_url`, `image_blob_path`, source page, dimensions, format, bbox where available, and metadata.

Alternative considered: store image bytes in PostgreSQL. Blob Storage is cheaper and better suited to binary files.

### Use SQLAlchemy and Alembic

SQLAlchemy will manage database access and transactions. Alembic will manage extensions, tables, indexes, and schema migrations, including pgvector setup.

Alternative considered: raw SQL scripts only. Alembic gives versioned migrations and works cleanly with local and cloud environments.

### Use Database-Backed Failure Reprocessing

The ingestion worker will record a `processing_failures` row when PDF processing fails after the event is accepted. The scheduled reprocessor will claim pending rows with database locking, retry up to three times, and mark rows as `resolved` or `permanently_failed`.

Alternative considered: rely only on Storage Queue retries. Queue retries do not give enough process-level observability and can fight with application retries.

### Use Plain Python Pipeline Instead of LangGraph

The processing flow will be implemented as explicit Python stages: receive event, resolve document, download, parse, store images, chunk, embed, persist, cleanup.

Alternative considered: LangGraph. The workflow is linear enough that LangGraph would add operational complexity without clear value.

### Use Azurite for Local Blob and Queue Storage

Local development will use Azurite from the root Docker Compose file to emulate both Blob Storage and Storage Queue. The worker will run against Azurite using local storage configuration, create/read raw PDFs from the `raw-pdfs` container, write extracted image artifacts to the `extracted-images` container, and consume messages from the `pdf-processing-jobs` queue.

Azurite does not emulate Event Grid delivery. Local BlobCreated and BlobDeleted events will be mocked by a RAG CLI helper that writes Event Grid-shaped JSON messages into the Azurite queue. Local document identity will use Azurite blob URLs.

Alternative considered: use production-shaped blob URLs locally. Azurite URLs are easier to resolve, keep local records faithful to the service being tested, and avoid extra URL translation logic.

### Use PostgreSQL pgvector in Local Docker Compose

The root Docker Compose setup will include a PostgreSQL service with pgvector support so local development and integration tests can exercise Alembic migrations, repository operations, and vector persistence without cloud infrastructure.

Alternative considered: use SQLite or skip local vector persistence. PostgreSQL pgvector provides better parity with the production schema and avoids testing a different persistence model.

### Load Local Environment With python-dotenv

The RAG pipeline will use `python-dotenv` to load `.env` values before resolving typed runtime settings. Existing process environment variables will take precedence over `.env` values so container and cloud runtime configuration is not overwritten.

Alternative considered: rely only on Docker Compose `env_file`. `python-dotenv` also supports host-based local execution of the worker and CLI helper without requiring the worker to run inside Docker.

### Use Configurable Embedding Providers

The embedding component will select an embedding provider from configuration. `azure_ai_foundry` will call the configured Azure AI Foundry embedding deployment through the Azure AI Projects Python package. `fake` will produce deterministic vectors for local/offline development and integration tests.

Alternative considered: always call Azure AI Foundry. Real embeddings are needed for production behavior, but deterministic fake embeddings make local tests repeatable, offline-capable, and cheaper.

## Risks / Trade-offs

- [Risk] Two different PDFs can share the same size. -> Mitigation: store ETag and metadata for observability and allow future change detection hardening without changing identity.
- [Risk] Queue visibility timeout can expire during long PDF processing. -> Mitigation: use a long visibility timeout and renew message visibility during processing if needed.
- [Risk] Duplicate queue delivery can process the same blob concurrently. -> Mitigation: use unique `blob_url`, document status, row locks, and idempotent replacement transactions.
- [Risk] Large PDFs may exceed memory if fully loaded. -> Mitigation: use temporary files or streaming download patterns and avoid holding all images in memory at once.
- [Risk] Partial failure after image upload can leave orphaned image blobs. -> Mitigation: store deterministic image blob paths and cleanup old paths during replacement and delete flows.
- [Risk] Embedding API limits can throttle batches. -> Mitigation: batch embeddings within token limits and retry transient Azure AI errors with bounded backoff.
- [Risk] Azurite does not produce Event Grid events. -> Mitigation: provide a CLI helper that enqueues Event Grid-shaped messages into the local Storage Queue.
- [Risk] Fake embeddings can hide provider-specific failures. -> Mitigation: keep fake embeddings as a configured provider for local/offline testing while preserving Azure AI Foundry integration tests or credentialed local runs where appropriate.

## Migration Plan

1. Create Python package structure for queue/event parsing, blob access, PDF extraction, chunking, embeddings, persistence, and retry processing.
2. Add dependencies for Azure SDKs, Azure AI Projects, PyMuPDF, LangChain, SQLAlchemy, Alembic, and pgvector support.
3. Add `python-dotenv` and typed configuration for Azure/Azurite storage, PostgreSQL, queue, and embedding providers.
4. Add Alembic migrations for extensions, tables, constraints, and indexes.
5. Implement ingestion entrypoint, reprocessor entrypoint, and local CLI helper.
6. Add unit tests for event parsing, skip/reprocess decisions, page-range image linking, embedding provider selection, and failure retry state transitions.
7. Add integration tests against local PostgreSQL pgvector and Azurite where practical.
8. Update Docker/runtime documentation and local `.env` examples.

Rollback: stop the Container App and scheduled job, keep database tables intact for inspection, and redeploy the previous image tag.

## Open Questions

- Should same-size reuploads also compare ETag when available, or strictly skip on size only?
- What exact markdown hierarchy extraction strategy should be used when PDF font/layout metadata does not expose reliable heading levels?
