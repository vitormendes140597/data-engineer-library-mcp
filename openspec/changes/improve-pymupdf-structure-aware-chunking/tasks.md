## 1. Structured Extraction Models

- [x] 1.1 Define typed extraction models for document elements, element styles, bounding boxes, table metadata, and structured extraction results.
- [x] 1.2 Add markdown rendering helpers for headings, paragraphs, list items, captions, and tables generated from structured elements.
- [x] 1.3 Add compatibility helpers for deriving `text`, `pages`, and `page_contents` from structured extraction results while call sites are migrated.

## 2. PyMuPDF Element Extraction

- [x] 2.1 Implement raw PyMuPDF page extraction that captures text blocks, lines, spans, styles, bounding boxes, and source page numbers.
- [x] 2.2 Implement conservative repeated header/footer and page-number filtering across page top and bottom bands.
- [x] 2.3 Implement heading classification using style profiles, numbering patterns, line length, indentation, and layout spacing.
- [x] 2.4 Implement paragraph and list item classification while preserving adjacent list item boundaries.
- [x] 2.5 Implement PyMuPDF table detection and table markdown rendering with row, column, header, page, and bounding-box metadata.
- [x] 2.6 Suppress paragraph/list elements whose bounding boxes substantially overlap detected table bounding boxes.
- [x] 2.7 Add deterministic reading-order handling for single-column, two-column, and mixed full-width-heading layouts.
- [x] 2.8 Return structured extraction results from the extraction module without introducing LLM or OCR dependencies.

## 3. Structure-Aware Chunking

- [x] 3.1 Implement a chunker entry point that accepts structured document elements and emits the existing chunk payload shape.
- [x] 3.2 Maintain active heading path metadata while packing elements into chunks.
- [x] 3.3 Include relevant heading context in chunk text even when the chunk begins below the heading element.
- [x] 3.4 Compute `page_start` and `page_end` from included element source pages.
- [x] 3.5 Keep tables atomic when they fit the configured chunk budget.
- [x] 3.6 Split oversized tables by row groups while repeating heading, caption, and header row context.
- [x] 3.7 Split oversized paragraph-like elements with the configured recursive text splitter while preserving source metadata.
- [x] 3.8 Populate concise chunk metadata with heading path, element types, page range, table summaries, and bounding-box references.

## 4. Pipeline Integration

- [x] 4.1 Update ingestion and reprocessing to pass structured extraction results into the structure-aware chunker.
- [x] 4.2 Preserve image linking behavior using existing page-range links for this change.
- [x] 4.3 Ensure persisted chunk records continue using the existing database schema and `metadata` JSON column.
- [x] 4.4 Keep existing markdown extraction behavior available as a fallback or compatibility path until tests cover the new flow.

## 5. Tests

- [x] 5.1 Add unit tests for structured element extraction with page provenance and bounding boxes.
- [x] 5.2 Add unit tests for heading hierarchy detection and false-positive heading cases.
- [x] 5.3 Add unit tests for paragraph and list item boundary preservation.
- [x] 5.4 Add unit tests for PyMuPDF table extraction, markdown rendering, and duplicate table text suppression.
- [x] 5.5 Add unit tests for conservative header/footer filtering.
- [x] 5.6 Add unit tests for structure-aware chunking with nested heading paths and page ranges.
- [x] 5.7 Add unit tests for small table atomic chunks and oversized table row-group chunks.
- [x] 5.8 Update ingestion/reprocessing tests to assert rich chunk metadata is persisted through the existing schema.

## 6. Verification and Documentation

- [x] 6.1 Run focused extraction and chunking tests.
- [x] 6.2 Run the full RAG pipeline test suite with fake embeddings.
- [x] 6.3 Document the structured extraction and chunking behavior in the RAG pipeline README or local developer notes.
