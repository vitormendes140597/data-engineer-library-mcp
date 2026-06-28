"""Structured PDF extraction models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ElementType(str, Enum):
    """Supported structured document element types."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CAPTION = "caption"


@dataclass(frozen=True)
class BoundingBox:
    """PDF coordinate bounding box."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def area(self) -> float:
        """Return the positive area covered by the box."""
        return max(self.x1 - self.x0, 0.0) * max(self.y1 - self.y0, 0.0)

    def overlap_ratio(self, other: "BoundingBox") -> float:
        """Return how much of this box is covered by another box."""
        x0 = max(self.x0, other.x0)
        y0 = max(self.y0, other.y0)
        x1 = min(self.x1, other.x1)
        y1 = min(self.y1, other.y1)
        overlap = max(x1 - x0, 0.0) * max(y1 - y0, 0.0)
        if self.area <= 0:
            return 0.0
        return overlap / self.area

    def to_list(self) -> list[float]:
        """Serialize the box as JSON-friendly coordinates."""
        return [round(value, 2) for value in (self.x0, self.y0, self.x1, self.y1)]


@dataclass(frozen=True)
class ElementStyle:
    """Dominant style information for a document element."""

    font_size: float
    font_name: str = ""
    is_bold: bool = False
    is_italic: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize style data as a JSON-friendly dictionary."""
        return {
            "font_size": round(self.font_size, 2),
            "font_name": self.font_name,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
        }


@dataclass(frozen=True)
class TableMetadata:
    """Metadata for a detected table element."""

    row_count: int
    column_count: int
    has_header: bool = False
    header_rows: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize table metadata as a JSON-friendly dictionary."""
        return {
            "row_count": self.row_count,
            "column_count": self.column_count,
            "has_header": self.has_header,
            "header_rows": self.header_rows,
        }


@dataclass(frozen=True)
class DocumentElement:
    """A classified PDF document element."""

    element_type: ElementType
    text: str
    markdown: str
    page_start: int
    page_end: int
    bbox: BoundingBox
    style: ElementStyle | None = None
    level: int | None = None
    table: TableMetadata | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        """Return concise element metadata for chunk payloads."""
        data: dict[str, Any] = {
            "type": self.element_type.value,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "bbox": self.bbox.to_list(),
        }
        if self.level is not None:
            data["level"] = self.level
        if self.style is not None:
            data["style"] = self.style.to_dict()
        if self.table is not None:
            data["table"] = self.table.to_dict()
        if self.metadata:
            data["metadata"] = self.metadata
        return data


@dataclass(frozen=True)
class StructuredExtractionResult:
    """Structured extraction output with compatibility helpers."""

    elements: list[DocumentElement]

    @property
    def page_contents(self) -> dict[int, str]:
        """Return rendered markdown grouped by source page."""
        grouped: dict[int, list[str]] = {}
        for element in self.elements:
            grouped.setdefault(element.page_start, []).append(element.markdown)
        return {
            page: "\n\n".join(part for part in parts if part.strip())
            for page, parts in sorted(grouped.items())
        }

    @property
    def text(self) -> str:
        """Return full rendered markdown text."""
        return "\n\n".join(
            self.page_contents[page] for page in sorted(self.page_contents)
        )

    @property
    def pages(self) -> list[dict[str, Any]]:
        """Return the legacy page list shape."""
        pages: list[dict[str, Any]] = []
        for page_number, markdown in self.page_contents.items():
            page_elements = [
                element
                for element in self.elements
                if element.page_start == page_number
            ]
            pages.append(
                {
                    "page_number": page_number,
                    "text": "\n".join(element.text for element in page_elements),
                    "markdown": markdown,
                    "headings": [
                        {"text": element.text, "level": element.level}
                        for element in page_elements
                        if element.element_type == ElementType.HEADING
                    ],
                }
            )
        return pages

    def to_legacy_dict(self) -> dict[str, Any]:
        """Return the previous extraction dictionary shape plus elements."""
        return {
            "text": self.text,
            "pages": self.pages,
            "page_contents": self.page_contents,
            "elements": self.elements,
        }
