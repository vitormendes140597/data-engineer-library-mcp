# MCP Server - Semantic Retrieval Service

This component implements a Model Context Protocol server for semantic retrieval from the vector database populated by the RAG pipeline.

## Purpose

Provide a semantic search interface to the vector database, enabling AI agents and applications to retrieve relevant data engineering knowledge efficiently.

## Architecture

```
Semantic Query → Embedding → Vector Search → Ranked Results → Response
```

## Technologies

- **FastMCP**: Model Context Protocol server framework
- **Python**: Core implementation language
- **Docker**: Containerization
- **Azure WebApp**: Cloud hosting
- **LangChain**: Query processing and embedding

## Project Structure

```
mcp-server/
├── src/
│   ├── server.py           # MCP server implementation
│   ├── retrieval/          # Semantic search logic
│   ├── models/             # Data models
│   └── config.py           # Configuration
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
- Access to populated vector database (from RAG pipeline)

### Setup

```bash
cd mcp-server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running Locally

```bash
python src/server.py --port 8000
```

### Docker

```bash
docker build -t de-agent-mcp:latest -f docker/Dockerfile .
docker run -p 8000:8000 de-agent-mcp:latest
```

## Configuration

```
VECTOR_DB_ENDPOINT=...
VECTOR_DB_KEY=...
MCP_PORT=8000
LOG_LEVEL=INFO
```

## API Specification

The server implements the MCP protocol for semantic retrieval:

- **Resource Tools**: Semantic search queries
- **Input**: Natural language or structured queries
- **Output**: Ranked list of relevant knowledge chunks

## Next Steps

1. Implement FastMCP server framework
2. Create semantic retrieval logic
3. Integrate with vector database
4. Add query preprocessing and ranking
5. Implement caching for common queries
6. Add comprehensive testing
