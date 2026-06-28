## Why

The current PDF extraction path flattens PyMuPDF text blocks into lightly inferred markdown, which loses tables, lists, layout, and section context before chunking begins. Improving chunk quality requires preserving PDF structure first, then generating markdown and chunks from that structured representation.

## What Changes

- Introduce a PyMuPDF-based structured extraction layer that emits typed document elements before markdown rendering.
- Detect and preserve headings, paragraphs, list items, tables, captions, and source layout metadata such as page numbers and bounding boxes.
- Add conservative header/footer noise filtering to reduce repeated page chrome in embeddings.
- Generate markdown from structured elements instead of using markdown as the primary extraction model.
- Replace character-stream chunking with structure-aware chunk packing that preserves heading paths, table boundaries, page ranges, and element metadata.
- Keep the existing persistence schema initially by storing richer chunk metadata in the existing JSON metadata column.
- Keep the solution non-LLM and non-OCR for this change.

## Capabilities

### New Capabilities

- `pdf-structure-extraction`: Extract typed, page-provenanced document elements from PDFs using PyMuPDF without LLM or OCR dependencies.
- `structure-aware-chunking`: Generate retrieval chunks from structured document elements while preserving section context, tables, lists, page ranges, and metadata.

### Modified Capabilities

- None.

## Impact

- Affected runtime code: `rag-pipeline/src/extraction/`, `rag-pipeline/src/chunking/`, and ingestion/reprocessing call sites that pass extracted content into chunking.
- Affected tests: extraction and chunking unit tests, plus relevant ingestion/reprocessing tests that assert chunk metadata.
- Dependencies: continue using PyMuPDF; no LLM, OCR, or database migration is required for the first implementation.
- Data impact: newly processed documents will produce richer chunk text and metadata; existing persisted chunks remain unchanged until documents are reprocessed.
