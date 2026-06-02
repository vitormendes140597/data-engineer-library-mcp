## 1. Dockerfile

- [x] 1.1 Create `terraform/docker/` directory
- [x] 1.2 Create `terraform/docker/Dockerfile` using `alpine:3.21` base with `TERRAFORM_VERSION` build argument (default `1.10.3`)
- [x] 1.3 Add `RUN` layer to download and verify the Terraform binary from HashiCorp releases using `curl` and `unzip`, then remove the archive
- [x] 1.4 Set `WORKDIR /workspace` and verify `terraform version` runs successfully in the built image

## 2. Docker Compose

- [x] 2.1 Create `docker-compose.yml` at the repository root with a single `terraform` service
- [x] 2.2 Configure the service `build` context to point at `terraform/docker/Dockerfile`
- [x] 2.3 Add `env_file: [.env]` to inject Service Principal credentials (`ARM_*` variables)
- [x] 2.4 Add bind-mount `./terraform:/workspace` so local changes are reflected immediately in the container
- [x] 2.5 Assign the service to `profiles: [infra]` to prevent accidental startup

## 3. Environment Variables

- [x] 3.1 Update `.env.example` to include stub entries for `ARM_SUBSCRIPTION_ID`, `ARM_TENANT_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, and relevant `TF_VAR_*` variables
- [x] 3.2 Ensure `.env` is listed in `.gitignore` (add if not already present)

## 4. Verification

- [x] 4.1 Run `docker build -t de-agent-terraform:latest terraform/docker/` and confirm the build succeeds
- [x] 4.2 Run `docker compose --profile infra run --rm terraform version` and confirm the correct Terraform version is reported
- [x] 4.3 Confirm that `docker compose up` (without `--profile infra`) does NOT start the terraform service
- [x] 4.4 Create a test file in `./terraform/` on the host and confirm it is visible at `/workspace/` inside the container
