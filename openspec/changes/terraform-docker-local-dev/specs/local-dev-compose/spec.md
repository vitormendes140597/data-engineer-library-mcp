## ADDED Requirements

### Requirement: Single Terraform service defined in Docker Compose
The `docker-compose.yml` SHALL define one service named `terraform` that uses the custom image built from `terraform/docker/Dockerfile`.

#### Scenario: Service is defined
- **WHEN** `docker compose config` is run
- **THEN** the output includes a service named `terraform` referencing the local Dockerfile build context

### Requirement: Service Principal credentials injected via env_file
The compose service SHALL read Azure Service Principal credentials from an `.env` file via the `env_file` directive. The variables SHALL be `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, and `ARM_SUBSCRIPTION_ID`.

#### Scenario: Missing .env file prevents startup gracefully
- **WHEN** the `.env` file does not exist and the user runs `docker compose run`
- **THEN** Docker Compose reports a clear error about the missing file before attempting to start the container

#### Scenario: Credentials available inside container
- **WHEN** the container starts with a valid `.env` file
- **THEN** running `printenv ARM_CLIENT_ID` inside the container returns the expected value

### Requirement: Local terraform directory bind-mounted to /workspace
The `./terraform` directory on the host SHALL be mounted as a bind-mount to `/workspace` inside the container so that file changes on the host are reflected immediately without rebuilding the image.

#### Scenario: File created on host appears in container
- **WHEN** a file is created under `./terraform/` on the host while the container is running
- **THEN** the same file is immediately visible at `/workspace/` inside the container

#### Scenario: File edited on host reflects in container
- **WHEN** an existing `.tf` file is edited and saved on the host
- **THEN** the updated content is immediately readable at the corresponding path inside the container

### Requirement: Service placed under the `infra` Docker Compose profile
The `terraform` service SHALL be assigned to the `infra` profile so it is not started by a bare `docker compose up`.

#### Scenario: Bare up does not start terraform service
- **WHEN** `docker compose up` is run without specifying a profile
- **THEN** the `terraform` service is not started

#### Scenario: Explicit profile starts the service
- **WHEN** `docker compose --profile infra run terraform <command>` is executed
- **THEN** the container starts and the Terraform command runs against `/workspace`

### Requirement: .env.example documents required variables
The repository SHALL contain a `.env.example` file with stub (non-secret) values for all variables consumed by the compose service, so developers know what to populate.

#### Scenario: Example file contains all required ARM variables
- **WHEN** `.env.example` is read
- **THEN** it contains stubs for `ARM_SUBSCRIPTION_ID`, `ARM_TENANT_ID`, `ARM_CLIENT_ID`, and `ARM_CLIENT_SECRET`

#### Scenario: .env is gitignored
- **WHEN** `.gitignore` is read
- **THEN** it contains an entry that prevents `.env` from being committed
