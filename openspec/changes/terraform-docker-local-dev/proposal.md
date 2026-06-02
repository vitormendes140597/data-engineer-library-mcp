## Why

Only the Terraform infrastructure code exists today, but there is no local development environment to run it. Engineers must install Terraform manually and configure Azure credentials by hand, making onboarding error-prone and environment-dependent. A containerised setup eliminates this friction.

## What Changes

- New custom Docker image based on `alpine:3.21` with Terraform installed — no Azure CLI, no extra tooling
- New `docker-compose.yml` at the repository root for spinning up the Terraform container locally
- Updated `.env.example` with the Azure Service Principal environment variables required by the container
- The local `./terraform` directory is bind-mounted into the container so changes made on the host are reflected immediately inside the container

## Capabilities

### New Capabilities

- `terraform-docker-image`: A minimal, reproducible Docker image that provides exactly the Terraform binary needed to run infrastructure commands
- `local-dev-compose`: A Docker Compose configuration that wires the image, bind-mount, and Service Principal auth together for frictionless local development

### Modified Capabilities

<!-- None — no existing specs are changing -->

## Impact

- **New files**: `terraform/docker/Dockerfile`, `docker-compose.yml`
- **Modified files**: `.env.example` (add `ARM_*` and `TF_VAR_*` variable stubs)
- **Dependencies**: Docker and Docker Compose must be installed on the developer's machine; Azure Service Principal credentials required at runtime
- **No production impact**: the image and compose file are for local development only and are not referenced by the Terraform or CI/CD pipelines
