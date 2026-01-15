from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from app.models.schemas import IndexStats
from app.services.chunker import SectionAwareChunker
from app.services.embeddings import EmbeddingService
from app.services.parser import MarkdownParser
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)


class VaultIndexer:
    def __init__(
        self,
        vault_path: Path,
        parser: MarkdownParser,
        chunker: SectionAwareChunker,
        embedder: EmbeddingService,
        qdrant: QdrantService,
    ):
        self.vault_path = vault_path
        self.parser = parser
        self.chunker = chunker
        self.embedder = embedder
        self.qdrant = qdrant
        self._lock = asyncio.Lock()

    async def full_index(self) -> IndexStats:
        async with self._lock:
            files = list(self.vault_path.rglob("*.md"))
            logger.info("Found %d markdown files", len(files))

            files_indexed = 0
            chunks_indexed = 0

            for path in files:
                c = await self.index_file(path)
                if c > 0:
                    files_indexed += 1
                    chunks_indexed += c

            return IndexStats(
                files_seen=len(files),
                files_indexed=files_indexed,
                chunks_indexed=chunks_indexed,
                finished_at=datetime.utcnow(),
            )

    async def index_file(self, path: Path) -> int:
        if not path.exists() or path.suffix.lower() != ".md":
            return 0

        parsed = self.parser.parse(path)
        chunks = self.chunker.chunk_document(parsed)
        if not chunks:
            return 0

        vectors = self.embedder.embed([c.text for c in chunks])
        file_rel = path.relative_to(self.vault_path).as_posix()
        self.qdrant.delete_file(file_rel)

        points = []
        for chunk, vec in zip(chunks, vectors):
            points.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "vector": vec,
                    "payload": {
                        "file_path": file_rel,
                        "title": parsed.title,
                        "heading": chunk.heading,
                        "text": chunk.text,
                        "tags": parsed.tags,
                        "frontmatter": parsed.frontmatter,
                        "links": parsed.links,
                        "line_start": chunk.line_start,
                        "line_end": chunk.line_end,
                    },
                }
            )

        self.qdrant.upsert_chunks(points)
        logger.info("Indexed %s (%d chunks)", file_rel, len(points))
        return len(points)

    async def remove_file(self, path: Path) -> None:
        if path.suffix.lower() != ".md":
            return
        try:
            file_rel = path.relative_to(self.vault_path).as_posix()
        except ValueError:
            return
        self.qdrant.delete_file(file_rel)
        logger.info("Removed %s from index", file_rel)
