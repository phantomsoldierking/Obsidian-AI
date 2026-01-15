from __future__ import annotations

import logging
from uuid import uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.models.schemas import SourceItem

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self, url: str, collection_name: str, vector_size: int):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)
        self._ensure_collection(vector_size)

    def _ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        names = {c.name for c in collections}
        if self.collection_name not in names:
            logger.info("Creating collection %s", self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            self.client.create_payload_index(
                self.collection_name, field_name="file_path", field_schema=PayloadSchemaType.KEYWORD
            )

    def upsert_chunks(self, points: list[dict]) -> None:
        qpoints = [
            PointStruct(
                id=str(uuid5(NAMESPACE_URL, p["chunk_id"])),
                vector=p["vector"],
                payload=p["payload"],
            )
            for p in points
        ]
        if qpoints:
            self.client.upsert(collection_name=self.collection_name, points=qpoints, wait=True)

    def delete_file(self, file_path: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="file_path", match=MatchValue(value=file_path))])
            ),
            wait=True,
        )

    def search(self, vector: list[float], limit: int) -> list[SourceItem]:
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit,
            with_payload=True,
        )
        return [
            SourceItem(
                file_path=hit.payload.get("file_path", ""),
                score=float(hit.score),
                title=hit.payload.get("title"),
                heading=hit.payload.get("heading"),
                snippet=hit.payload.get("text", "")[:300],
                line_start=hit.payload.get("line_start"),
                line_end=hit.payload.get("line_end"),
            )
            for hit in hits
        ]

    def health(self) -> bool:
        try:
            self.client.get_collection(self.collection_name)
            return True
        except Exception:
            return False
