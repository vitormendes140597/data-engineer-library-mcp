# RAG Pipeline

The RAG pipeline ingests PDF blobs, extracts markdown and images, creates embeddings, and stores
searchable chunks plus retry state in PostgreSQL pgvector.

## Architecture Overview

```text
BlobCreated/BlobDeleted -> Storage Queue -> ingestion_worker
                                      |-> Blob download (Azure/Azurite)
                                      |-> PDF markdown extraction
                                      |-> Image extraction/upload
                                      |-> Chunking + image linking
                                      |-> Embedding provider
                                      `-> PostgreSQL pgvector persistence

processing_failures -> reprocessor -> retry processing or permanently_failed
```

Key runtime components:
- `src/ingestion_worker.py`: processes at most one queue message per execution
- `src/reprocessor.py`: retries due `processing_failures` rows
- `src/cli.py`: local helper commands for Azurite bootstrap and Event Grid-shaped messages
- `src/persistence/`: SQLAlchemy models and repository methods
- `src/extraction/`, `src/chunking/`, `src/embeddings/`: document processing pipeline

## Structured PDF Extraction and Chunking

PDF ingestion now uses PyMuPDF to build a structured document representation before
chunking. The extractor emits typed elements for headings, paragraphs, list items, and
PyMuPDF-detected tables with page provenance, bounding boxes, style metadata, and rendered
markdown. Repeated header/footer text and simple page numbers are filtered conservatively
from the top and bottom page bands.

The structure-aware chunker packs elements rather than splitting one flattened markdown
string. It preserves active heading paths in chunk text and metadata, computes page ranges
from source elements, keeps tables atomic when they fit the chunk budget, and splits
oversized tables by row groups while repeating table context. Oversized paragraph-like
elements still use the configured recursive splitter as a fallback.

Persistence continues to use the existing `chunks` table. Richer values such as
`heading_path`, `element_types`, `source_elements`, table summaries, and bounding-box
references are stored in the existing `chunks.metadata` JSON column. The legacy
`extract_markdown()` and `chunk_text()` APIs remain available for compatibility and
rollback paths.

## Local Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose

### Start local dependencies

From the repository root:

```bash
docker compose up -d azurite postgres
```

### Install Python dependencies

```bash
cd rag-pipeline
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Example `.env`

Create `rag-pipeline/.env`:

```env
STORAGE_MODE=azurite
AZURE_STORAGE_BLOB_CONN_STR=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;
AZURE_STORAGE_QUEUE_CONN_STR=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;
QUEUE_NAME=pdf-processing-jobs
RAW_PDFS_CONTAINER=raw-pdfs
EXTRACTED_IMAGES_CONTAINER=extracted-images
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@127.0.0.1:5432/rag_db
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_ECHO_SQL=false
EMBEDDING_PROVIDER=fake
FAKE_EMBEDDING_DIMENSION=1536
AZURE_AI_FOUNDRY_PROJECT=
AZURE_AI_FOUNDRY_ENDPOINT=
AZURE_AI_FOUNDRY_DEPLOYMENT=
EMBEDDING_BATCH_SIZE=25
EMBEDDING_MAX_TOKENS_PER_BATCH=8000
CHUNK_SIZE=1024
CHUNK_OVERLAP=128
MAX_RETRY_ATTEMPTS=3
INITIAL_RETRY_DELAY_SECONDS=300
MAX_RETRY_DELAY_SECONDS=3600
USE_MANAGED_IDENTITY=true
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
OBSERVABILITY_ENABLED=true
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `AZURE_STORAGE_QUEUE_CONN_STR` | required | Queue connection string for Azure Storage Queue or Azurite. |
| `QUEUE_NAME` | `pdf-processing-jobs` | Queue consumed by the ingestion worker and CLI. |
| `QUEUE_VISIBILITY_TIMEOUT_SECONDS` | `3600` | Visibility timeout for received queue messages. |
| `QUEUE_MAX_RECEIVE_MESSAGES` | `1` | Max messages requested per worker run; code caps processing to one message. |
| `AZURE_STORAGE_BLOB_CONN_STR` | required | Blob connection string for Azure Storage or Azurite. |
| `RAW_PDFS_CONTAINER` | `raw-pdfs` | Container storing source PDFs. |
| `EXTRACTED_IMAGES_CONTAINER` | `extracted-images` | Container storing extracted image artifacts. |
| `STORAGE_MODE` | `azurite` | Storage backend mode: `azurite` or `azure`. |
| `DATABASE_URL` | required | PostgreSQL connection string used by Alembic and SQLAlchemy. |
| `DB_POOL_SIZE` | `5` | SQLAlchemy connection pool size. |
| `DB_MAX_OVERFLOW` | `10` | Extra pooled connections allowed above `DB_POOL_SIZE`. |
| `DB_ECHO_SQL` | `false` | Enables SQL logging when set to `true`. |
| `EMBEDDING_PROVIDER` | `fake` | Embedding backend: `fake` or `azure_ai_foundry`. |
| `FAKE_EMBEDDING_DIMENSION` | `1536` | Vector dimension used by deterministic fake embeddings. |
| `AZURE_AI_FOUNDRY_PROJECT` | empty | Azure AI Foundry project name when using real embeddings. |
| `AZURE_AI_FOUNDRY_ENDPOINT` | empty | Azure AI Foundry endpoint or project API endpoint. |
| `AZURE_AI_FOUNDRY_DEPLOYMENT` | empty | Azure AI Foundry embedding deployment/model name. |
| `EMBEDDING_BATCH_SIZE` | `25` | Maximum texts per embedding batch. |
| `EMBEDDING_MAX_TOKENS_PER_BATCH` | `8000` | Approximate token cap per embedding batch. |
| `CHUNK_SIZE` | `1024` | Max chunk size passed to the chunker. |
| `CHUNK_OVERLAP` | `128` | Overlap between adjacent chunks. |
| `CHUNK_SEPARATORS` | internal default | Chunk separator list; currently defined in code defaults. |
| `MAX_RETRY_ATTEMPTS` | `3` | Maximum reprocessing attempts before permanent failure. |
| `INITIAL_RETRY_DELAY_SECONDS` | `300` | Initial retry delay used for exponential backoff. |
| `MAX_RETRY_DELAY_SECONDS` | `3600` | Upper bound for retry backoff. |
| `USE_MANAGED_IDENTITY` | `true` | Uses managed identity when downloading from Azure. |
| `AZURE_TENANT_ID` | empty | Service principal tenant ID for explicit Azure auth. |
| `AZURE_CLIENT_ID` | empty | Managed identity or service principal client ID. |
| `AZURE_CLIENT_SECRET` | empty | Service principal client secret. |
| `OBSERVABILITY_ENABLED` | `true` | Flag reserved for runtime observability configuration. |

## Configuration Precedence

Configuration is loaded in this order:

1. Explicit process environment variables
2. Values from `rag-pipeline/.env`
3. Code defaults in `src/config.py`

`python-dotenv` is loaded with `override=False`, so real environment variables always win over
`.env` values.

## Running Migrations

Apply the schema to PostgreSQL:

```bash
cd rag-pipeline
alembic upgrade head
```

Rollback all migrations:

```bash
alembic downgrade base
```

## Ingestion Worker

Process a single visible queue message and exit:

```bash
cd rag-pipeline
python -m src.ingestion_worker
```

Behavior summary:
- parses Event Grid-shaped `BlobCreated` and `BlobDeleted` messages
- skips same-size reuploads for completed documents
- replaces changed-size documents transactionally
- records failures in `processing_failures`

## Reprocessor

Retry due failures from PostgreSQL:

```bash
cd rag-pipeline
python -m src.reprocessor
```

The reprocessor claims pending rows, retries processing, marks rows as `resolved`, and marks
exhausted rows as `permanently_failed`.

## Local Helper Commands

Bootstrap Azurite containers and queue:

```bash
cd rag-pipeline
python -m src.cli bootstrap
```

Upload a PDF and enqueue a local `BlobCreated` message:

```bash
python -m src.cli upload-pdf /absolute/path/to/book.pdf
```

Enqueue a local `BlobDeleted` message for a blob URL:

```bash
python -m src.cli delete-blob "http://127.0.0.1:10000/devstoreaccount1/raw-pdfs/book.pdf"
```

## Development

Run the test suite with coverage:

```bash
cd rag-pipeline
pytest tests/ --cov=src
```

Format code:

```bash
black src tests
isort src tests
```

Lint code:

```bash
flake8 src tests --max-line-length=100
```

## Local Workflow Summary

1. `docker compose up -d azurite postgres`
2. `cd rag-pipeline && source venv/bin/activate`
3. `alembic upgrade head`
4. `python -m src.cli bootstrap`
5. `python -m src.cli upload-pdf /path/to/file.pdf`
6. `python -m src.ingestion_worker`
7. `python -m src.reprocessor` for retry validation when needed
