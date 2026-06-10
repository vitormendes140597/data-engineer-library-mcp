## ADDED Requirements

### Requirement: Migration-managed schema
The RAG implementation SHALL use Alembic migrations to create and update PostgreSQL schema objects, including required extensions, tables, constraints, and vector indexes.

#### Scenario: Fresh database initialized
- **WHEN** migrations are applied to an empty PostgreSQL database
- **THEN** the database contains the required RAG tables, pgvector support, and indexes

### Requirement: Document records
The persistence layer SHALL store one document record per blob URL with content length, optional ETag, processing status, timestamps, and failure counters.

#### Scenario: Document persisted
- **WHEN** a PDF is accepted for processing
- **THEN** the system creates or updates a document row identified by blob URL

### Requirement: Chunk embeddings
The persistence layer SHALL store markdown chunks with document reference, chunk index, page range, heading metadata, text content, embedding vector, and JSON metadata.

#### Scenario: Chunk persisted with vector
- **WHEN** a chunk embedding is generated
- **THEN** the chunk row is stored with its vector and source metadata

### Requirement: Image and chunk-image records
The persistence layer SHALL store extracted image metadata and SHALL link each chunk to all images whose source pages fall within the chunk page range.

#### Scenario: Images linked to chunk pages
- **WHEN** a chunk spans pages 2 through 4 and extracted images exist on pages 2, 3, and 4
- **THEN** the system creates chunk-image links for all those images

### Requirement: SQLAlchemy database access
The RAG implementation SHALL use SQLAlchemy for PostgreSQL connections, transactions, and persistence operations.

#### Scenario: Transactional replacement
- **WHEN** a changed-size document is reprocessed
- **THEN** SQLAlchemy-managed transactions replace old database rows with new rows without leaving mixed old and new chunk records

### Requirement: Azure AI Projects embeddings
The embedding component SHALL use the Azure AI Projects Python package to generate text embeddings from chunk text.

#### Scenario: Embedding generated
- **WHEN** chunk text is ready for embedding
- **THEN** the system calls the configured Azure AI Foundry embedding deployment and stores the returned vector
