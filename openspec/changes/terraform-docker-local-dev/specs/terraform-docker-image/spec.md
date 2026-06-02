## ADDED Requirements

### Requirement: Minimal Alpine base with pinned Terraform binary
The image SHALL use `alpine:3.21` as its base and install a single, version-pinned Terraform binary downloaded directly from HashiCorp releases. No Azure CLI or other cloud tooling SHALL be included.

#### Scenario: Image builds successfully
- **WHEN** `docker build` is run against the Dockerfile
- **THEN** the build completes without error and the resulting image contains the `terraform` binary at a location on `$PATH`

#### Scenario: Image size is minimal
- **WHEN** the built image is inspected
- **THEN** its compressed size SHALL be under 100 MB

#### Scenario: Correct Terraform version is installed
- **WHEN** `terraform version` is executed inside the container
- **THEN** the output reports the version matching the pinned `TERRAFORM_VERSION` build argument

### Requirement: Terraform version is overridable at build time
The Dockerfile SHALL expose a `TERRAFORM_VERSION` build argument so the pinned version can be changed without editing the file body.

#### Scenario: Custom version via build arg
- **WHEN** `docker build --build-arg TERRAFORM_VERSION=1.9.0` is executed
- **THEN** the installed Terraform binary reports version `1.9.0`

### Requirement: Container working directory is /workspace
The image SHALL set `/workspace` as the default working directory so that Terraform commands run against files mounted at that path without requiring an explicit `cd`.

#### Scenario: Default working directory
- **WHEN** a shell is opened in a container started from the image
- **THEN** the current directory is `/workspace`
