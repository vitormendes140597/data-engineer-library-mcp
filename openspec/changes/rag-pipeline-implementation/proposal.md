## Why

The repository currently contains a placeholder RAG pipeline, but the system needs a production-ready worker that reacts to blob lifecycle events, extracts structured PDF content and images, embeds chunks, stores vectors in PostgreSQL pgvector, and retries failed processing safely. This change implements the application behavior that runs on the Terraform-provisioned Azure runtime.

## What Changes

- Implement a Python ingestion worker that receives exactly one Azure Storage Queue message per process execution and exits after success, recorded failure, or no work.
- Parse Event Grid BlobCreated and BlobDeleted payloads delivered through Storage Queue.
- Support local RAG development through root Docker Compose services for Azurite and PostgreSQL pgvector, with the worker running against the local services.
- Provide a local CLI helper that uploads PDFs to Azurite and enqueues Event Grid-shaped BlobCreated/BlobDeleted messages for the worker.
- For BlobCreated events, use the blob URL as document identity, skip processing when an existing document has the same PDF size, and replace old chunks/images when the size changes.
- Download PDFs from Azure Blob Storage, parse them with PyMuPDF into hierarchy-preserving markdown, extract images, and store extracted image files in Blob Storage.
- Create text chunks with page ranges, heading metadata, image associations, and embeddings generated through the Azure AI Projects Python package.
- Support configurable embedding providers, including deterministic fake embeddings for local/offline development and Azure AI Foundry embeddings for cloud or credentialed local runs.
- Store documents, chunks, images, chunk-image relations, embeddings, and processing failures in PostgreSQL using SQLAlchemy and pgvector.
- Use Alembic database migrations to manage PostgreSQL schema, extensions, indexes, and vector table structures.
- For BlobDeleted events, remove vectors, chunks, image metadata, chunk-image relations, and extracted image blobs.
- Implement a scheduled reprocessor entrypoint that reads failed processing rows from PostgreSQL, retries up to three times, and marks failures as resolved or permanently failed.
- Remove LangGraph from the implementation approach.

## Capabilities

### New Capabilities

- `rag-ingestion-worker`: Processes blob lifecycle queue messages and turns PDFs into searchable vector chunks.
- `rag-pdf-extraction`: Converts PDFs to hierarchy-preserving markdown and extracts image artifacts with metadata.
- `rag-vector-storage`: Persists documents, chunks, images, chunk-image links, embeddings, and failure records in PostgreSQL pgvector using migrations.
- `rag-failure-reprocessing`: Retries failed PDF processing through a scheduled database-backed reprocessor with a maximum of three attempts.
- `rag-local-development`: Provides local Azurite, PostgreSQL pgvector, dotenv configuration, local event enqueueing, and configurable embedding-provider support.

### Modified Capabilities

None.

## Impact

- Affected code: `rag-pipeline/` Python package, dependency files, Dockerfile/runtime configuration, root Docker Compose configuration, tests, and local development instructions.
- Affected dependencies: LangChain, PyMuPDF, SQLAlchemy, Alembic, pgvector support, Azure Blob Storage SDK, Azure Storage Queue SDK, Azure Identity, Azure AI Projects Python package, and python-dotenv.
- Affected data stores: PostgreSQL pgvector schema and extracted image Blob Storage container.
- Runtime dependency: assumes the Terraform infrastructure change provides storage containers, queue, identities, secrets, Azure AI Foundry deployment, PostgreSQL, and observability settings.
