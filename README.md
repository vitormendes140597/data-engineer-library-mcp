# Data Engineer Knowledge RAG

A comprehensive solution for extracting, standardizing, and retrieving data engineering knowledge from books using RAG (Retrieval-Augmented Generation) and MCP (Model Context Protocol).

## Project Structure

The repository contains two main components:

### 1. RAG Pipeline (`rag-pipeline/`)
Responsible for:
- Reading data engineering books
- Extracting and standardizing data
- Creating vector chunks
- Storing into vector database

**Technology Stack:**
- Python
- LangChain
- Docker
- Azure Blob Storage (Azurite for local development)
- Terraform for infrastructure

### 2. MCP Server (`mcp-server/`)
A Model Context Protocol server providing:
- Semantic retrieval from vector database
- Integration with AI agents

**Technology Stack:**
- Python
- FastMCP
- Docker
- Azure WebApp
- Terraform for infrastructure

### 3. Infrastructure (`terraform/`)
Infrastructure as Code for cloud deployment using Terraform.

## Development Guidelines

- Use Pythonic code and best practices
- Containerize all solutions with Docker
- Use Azurite for local blob storage mocking
- Local resources for development, cloud resources for production
- Infrastructure-as-Code with Terraform

## Getting Started

### Prerequisites
- Python 3.10+
- Docker
- Terraform
- Git
- Azure CLI (for cloud deployment)

### Local Development Setup

```bash
# Clone and navigate
git clone <repository>
cd de-agent-mcp

# Set up Python environments
cd rag-pipeline
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

cd ../mcp-server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Docker Setup

Build and run containers:

```bash
# RAG Pipeline
docker build -t de-agent-rag:latest ./rag-pipeline
docker run -v /path/to/data:/data de-agent-rag:latest

# MCP Server
docker build -t de-agent-mcp:latest ./mcp-server
docker run -p 8000:8000 de-agent-mcp:latest
```

## Development Phases

### Phase 1: RAG ETL Pipeline
- Extract data from data engineering books
- Create and populate vector database
- Standalone implementation

### Phase 2: MCP Server
- Build semantic retrieval server
- Integrate with RAG pipeline outputs
- Deploy as Azure WebApp

## External Resources

- [LangChain Documentation MCP](https://docs.langchain.com/mcp)
- [OpenSpec - Spec Driven Development](https://github.com/Fission-AI/OpenSpec)
- [Azure Architecture Builder](https://github.com/github/awesome-copilot/blob/main/skills/azure-architecture-autopilot/SKILL.md)
- [Terraform MCP Server](https://developer.hashicorp.com/terraform/mcp-server)
- [Azure Learn Docs MCP](https://learn.microsoft.com/api/mcp)

## Contributing

Follow these guidelines:
- Create feature branches from `main`
- Use conventional commits
- Include tests for new functionality
- Update documentation as needed
