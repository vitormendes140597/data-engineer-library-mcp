# RAG Pipeline - Data Extraction and Vectorization

This component handles the extraction, processing, and vectorization of data engineering knowledge from books.

## Purpose

Extract data from data engineering books, standardize the content, create vector embeddings, and store them in a vector database for semantic retrieval.

## Architecture

```
Books → Extraction → Standardization → Chunking → Embedding → Vector DB
```

## Technologies

- **LangChain**: Document processing and RAG orchestration
- **Python**: Core implementation language
- **Docker**: Containerization
- **Azure Blob Storage**: Document storage (Azurite for local development)
- **Vector Database**: Storage and retrieval (to be determined)

## Project Structure

```
rag-pipeline/
├── src/
│   ├── extractors/         # Document extraction logic
│   ├── processors/         # Data standardization
│   ├── embeddings/         # Vector embedding generation
│   ├── storage/            # Vector database operations
│   └── main.py             # Entry point
├── tests/                  # Unit and integration tests
├── docker/
│   └── Dockerfile
├── requirements.txt        # Python dependencies
└── README.md
```

## Development

### Prerequisites

- Python 3.10+
- Docker
- Azurite (Docker image or local installation)

### Setup

```bash
cd rag-pipeline
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running Locally

```bash
python src/main.py
```

### Docker

```bash
docker build -t de-agent-rag:latest -f docker/Dockerfile .
docker run -v $(pwd)/data:/data -e AZURITE_ACCOUNT_NAME=devstoreaccount1 de-agent-rag:latest
```

## Configuration

Configuration is managed via environment variables:

```
AZURE_STORAGE_CONNECTION_STRING=...
VECTOR_DB_ENDPOINT=...
VECTOR_DB_KEY=...
```

For local development, use `.env` file or docker-compose.

## Next Steps

1. Implement document extractors for various book formats (PDF, EPUB, etc.)
2. Create standardization processors
3. Integrate with LangChain for chunking and embedding
4. Set up vector database integration
5. Add comprehensive testing
