from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.models.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    GraphResponse,
    HealthResponse,
    IndexRequest,
    IndexResponse,
    QueryRequest,
    QueryResponse,
    SemanticSearchResponse,
    SummarizeRequest,
)
from app.services.container import ServiceContainer

router = APIRouter()


def _container(request: Request) -> ServiceContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise HTTPException(status_code=500, detail="Service container not initialized")
    return container


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    c = _container(request)
    return HealthResponse(
        status="ok",
        qdrant_ok=c.qdrant.health(),
        watcher_running=c.watcher.running,
        metadata={"collection": c.qdrant.collection_name},
    )


@router.post("/index", response_model=IndexResponse)
async def index_docs(payload: IndexRequest, request: Request) -> IndexResponse:
    c = _container(request)
    stats = await c.indexer.full_index()
    return IndexResponse(status="indexed", stats=stats)


@router.post("/query", response_model=QueryResponse)
async def query_docs(payload: QueryRequest, request: Request) -> QueryResponse:
    c = _container(request)
    return await run_in_threadpool(c.rag.answer, payload.query, payload.top_k)


@router.post("/summarize")
async def summarize(payload: SummarizeRequest, request: Request) -> dict:
    c = _container(request)
    summary = await run_in_threadpool(c.rag.summarize, payload.text)
    return {"answer": summary, "sources": [], "confidence": 0.7}


@router.post("/classify", response_model=ClassifyResponse)
async def classify(payload: ClassifyRequest, request: Request) -> ClassifyResponse:
    c = _container(request)
    label, confidence, scores = await run_in_threadpool(c.classifier.classify, payload.text)
    return ClassifyResponse(label=label, confidence=confidence, all_scores=scores)


@router.post("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search(payload: QueryRequest, request: Request) -> SemanticSearchResponse:
    c = _container(request)
    results = await run_in_threadpool(c.rag.semantic_search, payload.query, payload.top_k)
    return SemanticSearchResponse(results=results)


@router.get("/graph", response_model=GraphResponse)
async def graph_notes(request: Request) -> GraphResponse:
    c = _container(request)
    return await run_in_threadpool(c.graph.build_graph)
