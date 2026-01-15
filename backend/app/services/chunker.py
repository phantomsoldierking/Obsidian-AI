from __future__ import annotations

from dataclasses import dataclass

from app.services.parser import ParsedDocument


@dataclass
class Chunk:
    chunk_id: str
    text: str
    heading: str | None
    line_start: int
    line_end: int


class SectionAwareChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: ParsedDocument) -> list[Chunk]:
        sections = self._split_by_headings(doc.body)
        chunks: list[Chunk] = []
        idx = 0
        running_line = 1

        for heading, text in sections:
            section_chunks = self._sliding_chunks(text)
            for part in section_chunks:
                line_count = part.count("\n") + 1
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.path.as_posix()}::{idx}",
                        text=part,
                        heading=heading,
                        line_start=running_line,
                        line_end=running_line + line_count - 1,
                    )
                )
                idx += 1
                running_line += max(line_count - 1, 1)

        return chunks

    def _split_by_headings(self, body: str) -> list[tuple[str | None, str]]:
        lines = body.splitlines()
        sections: list[tuple[str | None, list[str]]] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if line.lstrip().startswith("#"):
                if current_lines:
                    sections.append((current_heading, current_lines))
                current_heading = line.strip("# ").strip() or None
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, current_lines))

        if not sections:
            return [(None, body)]

        return [(h, "\n".join(block).strip()) for h, block in sections if "\n".join(block).strip()]

    def _sliding_chunks(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        step = max(self.chunk_size - self.chunk_overlap, 1)
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += step
        return chunks
