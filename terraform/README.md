# Infrastructure as Code

Terraform configuration for deploying the RAG pipeline and MCP server to Azure.

## Structure

```
terraform/
├── main.tf              # Main configuration
├── locals.tf            # Local values
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── environments/        # Environment-specific configs
│   ├── dev.tfvars
│   ├── staging.tfvars
│   └── prod.tfvars
└── modules/             # Reusable modules
    ├── storage/         # Blob Storage & Queues
    ├── event_pipeline/  # Event Grid subscriptions
    ├── container_apps/  # Container App & Container App Job
    ├── acr/            # Azure Container Registry
    ├── ai_foundry/     # Azure AI Foundry (embeddings)
    ├── postgres/       # PostgreSQL Flexible Server
    ├── key_vault/      # Key Vault (secrets management)
    ├── observability/  # Log Analytics & Application Insights
    └── rbac/           # RBAC role assignments
```

## Prerequisites

- Terraform >= 1.0
- Azure CLI
- Azure subscription with appropriate permissions

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
- Raw PDF uploads (`raw-pdfs` container)
- Extracted images (`extracted-images` container)
- Processing queue for PDF lifecycle events

### Event Grid
- Routes PDF blob lifecycle events (created/deleted) to Storage Queue
- Filters to only PDF files in `raw-pdfs` container

### Container Apps (Ingestion Worker)
- Queue-scaled ingestion worker that processes one PDF per replica
- Scales from zero based on queue depth
- Uses KEDA Azure Queue scaler
- Reads from raw PDFs, writes extracted images, consumes queue messages

### Container App Job (Scheduled Reprocessor)
- Runs on cron schedule (default: daily at 11 PM UTC)
- Retries failed PDF processing from PostgreSQL
- Configurable concurrency (default: 1 parallel execution)

### Azure AI Foundry
- Embedding generation for RAG pipeline
- Used by both ingestion worker and reprocessor

### PostgreSQL Flexible Server
- pgvector extension for semantic search
- Stores RAG embeddings and failure tracking

### Key Vault
- Stores PostgreSQL connection string
- Stores Azure AI Foundry endpoint
- Stores Application Insights connection string
- Accessed by Container App and Container App Job via managed identity

### Container Registry
- Hosts RAG pipeline Docker image
- Accessed via managed identity (no credentials stored)

### Observability
- Log Analytics Workspace for centralized logging
- Application Insights for application performance monitoring

### RBAC
- Container App identity: storage (read/write), queue (consume), Key Vault (read secrets), ACR (pull), Azure AI Foundry (embed)
- Reprocessor identity: storage (read/write), Key Vault (read secrets), ACR (pull), Azure AI Foundry (embed)
- Event Grid identity: storage queue (send messages)

## Environment Management

Use separate `.tfvars` files for each environment:

```bash
# Development
terraform plan -var-file="environments/dev.tfvars"
terraform apply -var-file="environments/dev.tfvars"

# Staging
terraform plan -var-file="environments/staging.tfvars"
terraform apply -var-file="environments/staging.tfvars"

# Production
terraform plan -var-file="environments/prod.tfvars"
terraform apply -var-file="environments/prod.tfvars"
```

## Configuration Variables

Key variables (see `variables.tf` for full list):

- `subscription_id` — Azure subscription ID
- `tenant_id` — Azure AD tenant ID
- `environment` — Deployment environment (dev/staging/prod)
- `image_tag` — Container image tag to deploy (default: "latest")
- `reprocessor_schedule` — Cron schedule for reprocessor job (default: "0 23 * * *" = 11 PM daily)
- `reprocessor_max_parallelism` — Max concurrent reprocessor executions (default: 1)

## Useful Commands

```bash
# Validate configuration
terraform validate

# Format configuration
terraform fmt -recursive

# Check what will be created/modified
terraform plan -var-file="environments/dev.tfvars"

# Destroy infrastructure (careful!)
terraform destroy -var-file="environments/dev.tfvars"
```

## Notes

- All resources are tagged with environment and project name
- Managed identities are used for secure authentication (no stored credentials)
- Secrets are stored in Key Vault and accessed via versionless URIs
- The ingestion worker scales to zero when no queue messages are available
- Container App Job concurrency is limited to prevent resource exhaustion
- State is stored locally (configure Azure Storage backend for team environments)

