# Data Engineer Knowledge RAG

## Goal
The project goal can be split into two:

1. Create a RAG Pipeline to read data engineering books, extract data, standardize, create chunks and store into a vector database for later retrieval.

    tools:
        - Azure blob storage
        - Python
        - LangChain
        - LangGraph (if needed)
        - Docker
        - Azure Container Registry
        - Terraform
        - Git

2. Create a MCP server that is able to do a semantic retrieval in the vector database

    tools:
        - Python
        - FastMCP
        - Azure WebApp
        - Docker
        - Azure Container Registry
        - Terraform
        - Git

## Basic Development Guidelines

- Always use pythonic way and python best practices
- Use docker to containerize the solution
- Use Azurite to mock blob storage on local development
- Always use local resources for local development
- Terraform for cloud infrastructure


## How will it be developed?

The project should be developed in the following way:

- First wave will create the RAG ETL and populate vector database.
- Second and last wave will create the MCP

So they are distinct projects but they will coexist in the same github repository.

# External AI Tools

Use the following external tools to connect to our AI Agent

- LangChain Documentation MCP: https://docs.langchain.com/mcp
- OpenSpec Skills for Spec Driven Development: https://github.com/Fission-AI/OpenSpec
- Azure Architecture Builder Skill: https://github.com/github/awesome-copilot/blob/main/skills/azure-architecture-autopilot/SKILL.md
- Terraform Docs MCP: https://developer.hashicorp.com/terraform/mcp-server
- Azure Learn Docs MCP: https://learn.microsoft.com/api/mcp


