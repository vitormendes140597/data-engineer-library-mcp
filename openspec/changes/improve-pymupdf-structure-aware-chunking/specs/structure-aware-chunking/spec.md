## ADDED Requirements

### Requirement: Element-based chunk generation
The chunking component SHALL generate chunks from structured document elements instead of splitting a single flattened markdown string.

#### Scenario: Chunk produced from structured elements
- **WHEN** structured elements are available for a document
- **THEN** the chunker emits chunk payloads with text, page range, heading metadata, and source element metadata

### Requirement: Heading path preservation
The chunking component SHALL maintain the active heading path while packing elements into chunks.

#### Scenario: Chunk includes section context
- **WHEN** a paragraph appears under nested heading elements
- **THEN** the generated chunk includes the full heading path in metadata and includes relevant heading context in the chunk text

### Requirement: Page range preservation
The chunking component SHALL compute chunk page ranges from the source pages of included structured elements.

#### Scenario: Multi-page chunk page range
- **WHEN** a chunk includes elements from pages 2 through 4
- **THEN** the chunk has `page_start` set to 2 and `page_end` set to 4

### Requirement: Table-aware chunking
The chunking component SHALL preserve table boundaries when generating chunks.

#### Scenario: Small table kept atomic
- **WHEN** a table element fits within the configured chunk budget
- **THEN** the chunker emits the table in a single chunk without splitting rows across unrelated text chunks

### Requirement: Oversized table splitting
The chunking component SHALL split oversized tables by row groups while preserving table context.

#### Scenario: Large table split by rows
- **WHEN** a table element exceeds the configured chunk budget
- **THEN** the chunker emits multiple table chunks that repeat available heading, caption, and header row context

### Requirement: Oversized text fallback splitting
The chunking component SHALL split oversized paragraph-like elements with the configured recursive text splitter only after preserving source metadata.

#### Scenario: Long paragraph split safely
- **WHEN** a paragraph element exceeds the configured chunk budget
- **THEN** the chunker splits the paragraph into bounded chunks that retain the paragraph source page and active heading path metadata

### Requirement: Rich chunk metadata
The chunking component SHALL include structured metadata for generated chunks without requiring a database schema change.

#### Scenario: Metadata stored in existing payload
- **WHEN** a chunk is generated from structured elements
- **THEN** the chunk metadata includes page range, heading path, element types, and concise table or bounding-box references suitable for storage in the existing JSON metadata column
