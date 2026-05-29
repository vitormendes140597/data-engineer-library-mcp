# Infrastructure as Code

Terraform configuration for deploying the RAG pipeline and MCP server to Azure.

## Structure

```
terraform/
├── main.tf              # Main configuration
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── environments/        # Environment-specific configs
│   ├── dev.tfvars
│   ├── staging.tfvars
│   └── prod.tfvars
└── modules/             # Reusable modules
    ├── blob_storage/
    ├── vector_db/
    ├── container_registry/
    ├── webapp/
    └── networking/
```

## Prerequisites

- Terraform >= 1.0
- Azure CLI
- Azure subscription

## Getting Started

```bash
cd terraform

# Initialize Terraform
terraform init

# Plan deployment to dev environment
terraform plan -var-file="environments/dev.tfvars"

# Apply configuration
terraform apply -var-file="environments/dev.tfvars"
```

## Components

### Azure Blob Storage
- Document storage for RAG pipeline
- Containerized for isolated environments

### Vector Database
- Optimized for semantic search
- High-performance retrieval

### Container Registry
- Private registry for Docker images
- Supports both RAG pipeline and MCP server images

### WebApp
- Hosts the MCP server
- Auto-scaling and load balancing

### Networking
- Virtual networks and subnets
- Network security groups
- Private endpoints for secure communication

## Environment Management

Use separate `.tfvars` files for each environment:

```bash
# Development
terraform apply -var-file="environments/dev.tfvars"

# Staging
terraform apply -var-file="environments/staging.tfvars"

# Production
terraform apply -var-file="environments/prod.tfvars"
```

## Useful Commands

```bash
# Validate configuration
terraform validate

# Format configuration
terraform fmt -recursive

# Check what will be created/modified
terraform plan

# Destroy infrastructure (careful!)
terraform destroy
```

## Notes

- Local development uses Azurite for blob storage
- Cloud deployments use Azure Blob Storage
- All resources are tagged with environment and project name
- State is stored in Azure Storage (configure remote backend)
