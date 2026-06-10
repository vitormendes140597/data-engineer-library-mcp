## ADDED Requirements

### Requirement: Processing failure log
The ingestion worker SHALL write a processing failure row when PDF processing fails after a queue message has been accepted.

#### Scenario: Failure recorded
- **WHEN** PDF processing fails during download, parsing, chunking, embedding, image storage, or database persistence
- **THEN** the system records blob URL, event payload, failure stage, error details, attempt count, status, and retry timing in PostgreSQL

### Requirement: Queue message finalized after failure is recorded
The ingestion worker SHALL delete the Storage Queue message after the failure row is durably stored.

#### Scenario: Failure ownership transferred
- **WHEN** the worker records a processing failure successfully
- **THEN** the original queue message is deleted and future retries are owned by the reprocessor

### Requirement: Scheduled failure reprocessing
The reprocessor SHALL read pending failure rows from PostgreSQL and retry failed PDF processing.

#### Scenario: Pending failure retried
- **WHEN** the scheduled reprocessor runs and a pending failure is due
- **THEN** it claims the row and retries processing for the associated blob URL

### Requirement: Maximum reprocessing attempts
The reprocessor SHALL attempt a failed process no more than three times.

#### Scenario: Failure permanently marked
- **WHEN** a failure reaches three unsuccessful reprocessing attempts
- **THEN** the reprocessor marks the failure as permanently failed

### Requirement: Successful reprocessing resolution
The reprocessor SHALL mark a failure row as resolved when retry processing succeeds.

#### Scenario: Failure resolved
- **WHEN** a retry successfully processes the PDF
- **THEN** the failure row status is set to resolved

### Requirement: Concurrent retry protection
The reprocessor SHALL prevent multiple scheduled executions from processing the same failure row concurrently.

#### Scenario: Failure row claimed once
- **WHEN** multiple reprocessor executions run at the same time
- **THEN** only one execution claims and processes a given pending failure row
