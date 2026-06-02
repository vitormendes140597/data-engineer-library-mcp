## Context

The repository contains Terraform infrastructure code under `terraform/`. Currently there is no standardised way to run Terraform locally — each developer must install the correct Terraform version, configure Azure credentials manually, and ensure their environment matches CI. This leads to version drift and onboarding friction.

The solution is a minimal Docker image that encapsulates the Terraform binary and a Docker Compose file that handles credential injection and bind-mounting the local `terraform/` directory.

No Azure CLI is needed: the `azurerm` provider authenticates exclusively via the four Service Principal environment variables (`ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`).

## Goals / Non-Goals

**Goals:**
- Reproducible, version-pinned Terraform environment for local development
- Service Principal authentication without any interactive login step
- Live reflection of local file changes inside the container via bind-mount
- Zero mandatory tooling beyond Docker and Docker Compose

**Non-Goals:**
- CI/CD pipeline integration (the image is for local use only)
- Installing the Azure CLI or any other Azure tooling in the image
- Multi-environment orchestration (dev/staging/prod targets are handled via `.tfvars`, not by this compose setup)
- Any component other than Terraform (RAG pipeline, MCP server)

## Decisions

### 1. Base image: `alpine:3.21`

| Option | Size | Notes |
|--------|------|-------|
| `alpine:3.21` | ~7 MB | Minimal; requires manual Terraform install |
| `hashicorp/terraform:1.10` | ~90 MB | Official; larger; opinionated entrypoint |
| `mcr.microsoft.com/azure-cli` | ~800 MB | Includes Azure CLI — unnecessary for SP auth |

**Decision**: `alpine:3.21`. We install the Terraform binary directly from HashiCorp releases, giving us full control over the version and no unnecessary layers.

### 2. Terraform version pinning

`terraform/versions.tf` requires `>= 1.5.0` with `azurerm ~> 4.0`. We pin to `1.10.3` (latest stable at time of writing) in the Dockerfile. This can be bumped via a single ARG.

### 3. Service Principal auth only

The `azurerm` provider reads `ARM_*` environment variables natively. No `az login` or browser flow is needed. Credentials are injected via Docker Compose `env_file` pointing at a `.env` file that is `.gitignore`d.

### 4. Bind-mount strategy

`./terraform` is mounted to `/workspace` inside the container, and `/workspace` is set as the working directory. Any file saved on the host is immediately visible inside the container — no rebuild required.

### 5. Docker Compose `profiles`

The `terraform` service is placed under `profiles: [infra]` so that a bare `docker compose up` (e.g., from a future compose file that includes application services) does not accidentally start Terraform commands.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `.env` file committed with secrets | `.env` added to `.gitignore`; `.env.example` ships stub values only |
| Terraform binary download fails during build (network issue) | Pin to a specific release URL; CI can cache the layer |
| Version drift if `1.10.3` is not bumped | Document the `TERRAFORM_VERSION` ARG; update as part of infra upgrade tasks |
| Bind-mount is host-OS dependent (Windows path format) | Document Docker Desktop requirement; WSL2 path notes in README |
