## ADDED Requirements

### Requirement: Structured PDF element extraction
The PDF extraction component SHALL extract typed document elements from PDF pages using PyMuPDF without LLM or OCR dependencies.

#### Scenario: Text elements extracted with provenance
- **WHEN** a PDF page contains readable text blocks
- **THEN** the extractor returns typed elements with text, markdown, source page, bounding box, and element type metadata

### Requirement: Heading detection with hierarchy metadata
The PDF extraction component SHALL classify detected headings and assign heading levels using PyMuPDF style and layout signals.

#### Scenario: Heading hierarchy extracted
- **WHEN** a PDF contains title and section lines distinguishable by style, numbering, or layout
- **THEN** the extractor returns heading elements with stable heading levels and source page provenance

### Requirement: Paragraph and list extraction
The PDF extraction component SHALL preserve paragraph and list item boundaries when converting page text into structured elements.

#### Scenario: List items preserved
- **WHEN** a PDF page contains adjacent bullet or numbered list items
- **THEN** the extractor returns list item elements instead of merging the items into one paragraph

### Requirement: Table extraction
The PDF extraction component SHALL detect PyMuPDF-recognized tables and emit table elements with rendered markdown and table metadata.

#### Scenario: Table element extracted
- **WHEN** a PDF page contains a table detected by PyMuPDF
- **THEN** the extractor returns a table element with markdown table text, source page, bounding box, row count, column count, and available header metadata

### Requirement: Duplicate table text suppression
The PDF extraction component SHALL avoid emitting paragraph or list elements for text that substantially overlaps a detected table element.

#### Scenario: Table text not duplicated
- **WHEN** table cells are present inside a detected table bounding box
- **THEN** the extractor emits the content through the table element and does not duplicate the same cell text as paragraph elements

### Requirement: Header and footer filtering
The PDF extraction component SHALL conservatively filter repeated page headers, footers, and simple page-number noise from structured text elements.

#### Scenario: Repeated footer removed
- **WHEN** the same normalized footer appears in the bottom page band across multiple pages
- **THEN** the extractor omits that footer from paragraph, list, and heading elements

### Requirement: Markdown rendering from structure
The PDF extraction component SHALL render markdown from structured elements after element classification is complete.

#### Scenario: Markdown generated from elements
- **WHEN** structured elements include headings, paragraphs, lists, and tables
- **THEN** the extractor returns markdown that reflects those element types while retaining page provenance in the structured output
