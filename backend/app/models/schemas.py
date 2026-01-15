from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    file_path: str
    score: float
    title: str | None = None
    heading: str | None = None
    snippet: str
    line_start: int | None = None
    line_end: int | None = None


class QueryRequest(BaseModel):
    query: str = Field(min_length=2)
    top_k: int | None = Field(default=None, ge=1, le=30)


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    confidence: float = Field(ge=0, le=1)
    route: str


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=10)


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=2)


class ClassifyResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    all_scores: dict[str, float]


class IndexRequest(BaseModel):
    force_full: bool = True


class IndexStats(BaseModel):
    files_seen: int
    files_indexed: int
    chunks_indexed: int
    finished_at: datetime


class IndexResponse(BaseModel):
    status: str
    stats: IndexStats


class SemanticSearchResponse(BaseModel):
    results: list[SourceItem]


class GraphNode(BaseModel):
    id: str
    title: str


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class HealthResponse(BaseModel):
    status: str
    qdrant_ok: bool
    watcher_running: bool
    metadata: dict[str, Any] = {}
