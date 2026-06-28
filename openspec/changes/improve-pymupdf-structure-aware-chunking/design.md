## Context

The RAG pipeline currently extracts page markdown in `rag-pipeline/src/extraction/pdf_parser.py` by reading PyMuPDF text blocks, inferring headings from font sizes, and joining the remaining lines into paragraphs. `rag-pipeline/src/chunking/chunker.py` then combines all page markdown into a single character stream and uses LangChain recursive text splitting to produce chunks with page ranges and a first-heading metadata field.

That approach satisfies basic page provenance, but it loses too much structure before chunking starts. Tables are flattened into ambiguous text, list boundaries are weak, repeated headers and footers pollute chunks, and section context is available only when the first line of a chunk happens to be a markdown heading.

This design keeps the implementation non-LLM and non-OCR. PyMuPDF remains the extraction engine, but the system introduces a structured intermediate representation before markdown rendering and chunking.

## Goals / Non-Goals

**Goals:**

- Extract typed document elements from PDFs using PyMuPDF, including headings, paragraphs, list items, tables, captions, and image references where available.
- Preserve page provenance, bounding boxes, style metadata, heading levels, and heading paths for extracted elements.
- Detect tables with PyMuPDF table APIs and render tables as markdown while retaining row and column metadata.
- Remove repeated page headers, footers, and simple page-number noise conservatively.
- Generate chunk text from structured elements, not from a single flattened markdown string.
- Keep section context in chunk text and metadata so embeddings and retrieval have stronger semantic context.
- Preserve table boundaries during chunking, splitting oversized tables by row groups instead of arbitrary characters.
- Store richer chunk metadata in the existing `chunks.metadata` JSON field without a database migration.

**Non-Goals:**

- Add LLM-based parsing, OCR, image captioning, or document understanding services.
- Guarantee perfect reading order for all arbitrary PDF layouts.
- Persist every extracted document element in a new table.
- Change the embedding provider, vector schema, or retrieval API.
- Reprocess existing documents automatically.

## Decisions

### Use a DocumentElement Intermediate Model

The extraction layer will emit structured elements before markdown generation. Each element will include a type, text, rendered markdown, page range, bounding box, style data, and metadata. Heading elements will include a level. Table elements will include row and column metadata.

Alternative considered: keep returning `page_contents: dict[int, str]` and improve markdown heuristics. That would keep the current API simpler, but it would continue making markdown the only source of truth and would leave chunking unable to distinguish paragraphs from tables, captions, and lists.

### Keep PyMuPDF as the Only Extraction Dependency

The implementation will use PyMuPDF text dictionaries, span style metadata, bounding boxes, image rectangles, and table detection APIs. This keeps the runtime dependency surface close to the current system and avoids introducing LLM, OCR, or heavier document parsing stacks.

Alternative considered: add pdfplumber or unstructured. Those may be useful later for specific document classes, but the first implementation should improve the current PyMuPDF path before adding another PDF engine.

### Detect Headings With Style Profiles Instead of Font Size Alone

Heading detection will derive a body style from common text spans and classify heading candidates using font size, bold style, line length, numbering patterns, indentation, and vertical spacing. Heading levels will be assigned by ranked style profiles and capped to a small depth to avoid noisy heading hierarchies.

Alternative considered: rely only on font-size thresholds. The current implementation already does this and misses headings expressed by boldness, numbering, whitespace, or style changes without large font differences.

### Use Table Bounding Boxes to Avoid Duplicate Text

Tables detected by PyMuPDF will be emitted as table elements. Text blocks that heavily overlap detected table bounding boxes will be excluded from paragraph/list extraction so table content does not appear twice.

Alternative considered: allow both extracted table markdown and raw text blocks. That would maximize recall but would pollute embeddings with duplicate and inconsistently ordered content.

### Remove Headers and Footers Conservatively

The extractor will identify repeated normalized lines in top and bottom page bands across multiple pages and filter only high-confidence header/footer noise, such as page numbers and repeated document chrome.

Alternative considered: never remove repeated content. This is safer for recall but causes recurring page chrome to appear in many embeddings and weakens retrieval quality.

### Chunk by Element Packing

The chunker will accept structured elements and pack them into chunks using element boundaries. It will maintain a heading path stack, include heading context in chunk text, keep small tables atomic, split oversized tables by row groups with repeated headers, and fall back to recursive text splitting only for oversized paragraph-like elements.

Alternative considered: use MarkdownHeaderTextSplitter over rendered markdown. This would improve heading awareness, but still treats tables and other layout-sensitive content as text rather than first-class elements.

### Preserve Existing Persistence Schema

Chunks will continue to store text, page range, embedding, and metadata in the existing tables. Richer values such as heading path, element types, table metadata, and bounding-box references will be stored inside `chunks.metadata`.

Alternative considered: add a `document_elements` table. That would improve auditability and debugging, but it increases migration and repository complexity before the chunk quality improvement is proven.

## Risks / Trade-offs

- [Risk] PyMuPDF table detection may miss borderless or visually complex tables. -> Mitigation: preserve non-table text extraction fallback and add tests for detected and undetected table cases.
- [Risk] Heading heuristics can overclassify short bold body text as headings. -> Mitigation: use multiple signals, cap heading depth, and require tests for common false positives.
- [Risk] Header/footer removal can discard meaningful repeated section labels. -> Mitigation: filter only top/bottom repeated content and keep the heuristic conservative.
- [Risk] Multi-column reading order can still fail for mixed layouts. -> Mitigation: detect simple column clusters and retain deterministic ordering with test fixtures for single-column, two-column, and mixed pages.
- [Risk] Chunk metadata JSON can become large. -> Mitigation: store concise metadata summaries and avoid persisting every span-level detail per chunk.
- [Risk] New extraction output shape affects ingestion and reprocessing call sites. -> Mitigation: keep a compatibility wrapper or explicit adapter during the transition.

## Migration Plan

1. Add structured extraction models and PyMuPDF element extraction behind the existing extraction module boundary.
2. Add tests for heading, paragraph, list, table, caption, header/footer, page provenance, and bounding-box extraction.
3. Add a structure-aware chunker that consumes extracted elements and emits the existing chunk payload shape.
4. Update ingestion and reprocessing to pass structured extraction output into the new chunker.
5. Keep markdown rendering available for diagnostics and chunk text generation.
6. Validate the full ingestion/reprocessing test suite with fake embeddings.

Rollback: restore the ingestion/reprocessing call sites to use the existing `extract_markdown` and `chunk_text` flow. No database rollback is required because the first implementation does not change schema.

## Open Questions

- Should `extract_markdown` remain as a compatibility API name, or should the pipeline introduce a new `extract_structure` API and adapt call sites explicitly?
- What chunk budget should apply to tables: character count, approximate token count, or row count with a character fallback?
- Should image associations remain page-range based in this change, or should extracted image bounding boxes be linked to nearby structured elements as a follow-up?
