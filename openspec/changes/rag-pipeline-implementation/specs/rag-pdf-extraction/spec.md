## ADDED Requirements

### Requirement: PDF markdown extraction
The PDF extraction component SHALL use PyMuPDF to convert PDF content into markdown that preserves detected document hierarchy where available.

#### Scenario: Structured text extracted
- **WHEN** a PDF contains text with detectable headings and body content
- **THEN** the extractor returns markdown with heading structure and page provenance

### Requirement: PDF image extraction
The PDF extraction component SHALL extract images from PDFs and store each extracted image in Blob Storage.

#### Scenario: Image artifact stored
- **WHEN** a PDF page contains an extractable image
- **THEN** the extractor writes the image to the extracted image Blob container

### Requirement: Image metadata captured
The PDF extraction component SHALL produce metadata for each extracted image including document identity, source page, image blob path, image blob URL, format when known, dimensions when known, and other available PyMuPDF metadata.

#### Scenario: Image metadata returned
- **WHEN** an image is extracted from a PDF page
- **THEN** the extractor returns metadata sufficient to persist an `images` table row

### Requirement: Page provenance retained
The PDF extraction component SHALL retain page provenance for markdown content so downstream chunks can include page ranges.

#### Scenario: Chunk source pages available
- **WHEN** markdown content is prepared for chunking
- **THEN** each chunk can be assigned a `page_start` and `page_end`
