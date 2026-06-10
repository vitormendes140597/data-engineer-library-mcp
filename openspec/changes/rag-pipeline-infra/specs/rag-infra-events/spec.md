## ADDED Requirements

### Requirement: BlobCreated events routed
Terraform SHALL route PDF BlobCreated events from the raw PDF container to the processing Storage Queue.

#### Scenario: PDF created event delivered
- **WHEN** a `.pdf` blob is created in the `raw-pdfs` container
- **THEN** Event Grid delivers a BlobCreated event to the `pdf-processing-jobs` queue

### Requirement: BlobDeleted events routed
Terraform SHALL route PDF BlobDeleted events from the raw PDF container to the processing Storage Queue.

#### Scenario: PDF deleted event delivered
- **WHEN** a `.pdf` blob is deleted from the `raw-pdfs` container
- **THEN** Event Grid delivers a BlobDeleted event to the `pdf-processing-jobs` queue

### Requirement: Raw PDF event filtering
Terraform SHALL filter blob lifecycle events so only PDF events from the raw PDF container are sent to the processing queue.

#### Scenario: Non-PDF event ignored
- **WHEN** a non-PDF blob is created or deleted
- **THEN** Event Grid does not enqueue a RAG processing event

#### Scenario: Other container event ignored
- **WHEN** a PDF blob is created or deleted outside `raw-pdfs`
- **THEN** Event Grid does not enqueue a RAG processing event
