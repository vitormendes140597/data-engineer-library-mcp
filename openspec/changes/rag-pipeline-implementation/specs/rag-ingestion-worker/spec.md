## ADDED Requirements

### Requirement: One-message queue processing
The ingestion worker SHALL receive at most one visible Storage Queue message per process execution and SHALL exit after processing, recording failure, or finding no message.

#### Scenario: One message processed
- **WHEN** the ingestion process starts and one queue message is available
- **THEN** the worker processes that message and exits after deleting or recording the message outcome

#### Scenario: No message available
- **WHEN** the ingestion process starts and no queue message is available
- **THEN** the worker exits successfully without processing a document

### Requirement: Event Grid payload parsing
The ingestion worker SHALL parse Event Grid BlobCreated and BlobDeleted payloads from Storage Queue messages and extract blob URL, blob name, event type, content length when present, ETag when present, event id, and event time.

#### Scenario: BlobCreated event parsed
- **WHEN** a BlobCreated queue message is received
- **THEN** the worker extracts the blob URL and event metadata required for ingestion

#### Scenario: BlobDeleted event parsed
- **WHEN** a BlobDeleted queue message is received
- **THEN** the worker extracts the blob URL and event metadata required for deletion

### Requirement: Same-size document skip
The ingestion worker SHALL use blob URL as document identity and SHALL skip BlobCreated processing when an existing document for that blob URL has the same stored content length.

#### Scenario: Same-size upload skipped
- **WHEN** a BlobCreated event is received for an existing document with matching content length
- **THEN** the worker does not download, parse, embed, or rewrite chunks for that PDF

### Requirement: Changed-size document replacement
The ingestion worker SHALL replace existing stored content when a BlobCreated event has the same blob URL and a different content length.

#### Scenario: Changed-size upload reprocessed
- **WHEN** a BlobCreated event is received for an existing document with a different content length
- **THEN** the worker removes old chunks, image links, image rows, extracted image blobs, and writes the newly processed content

### Requirement: Blob deletion cleanup
The ingestion worker SHALL handle BlobDeleted events by removing stored vectors, chunks, chunk-image links, image metadata, and extracted image blobs for the document blob URL.

#### Scenario: Source PDF deleted
- **WHEN** a BlobDeleted event is received for a known document
- **THEN** the worker removes searchable content and extracted image artifacts for that document
