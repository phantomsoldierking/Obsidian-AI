from __future__ import annotations

from statistics import mean

from app.models.schemas import QueryResponse, SourceItem
from app.services.classifier import PROMPT_TEMPLATES, QueryRouterClassifier
from app.services.embeddings import EmbeddingService
from app.services.llm_service import LocalLLMService
from app.services.qdrant_service import QdrantService


class RAGService:
    def __init__(
        self,
        embedder: EmbeddingService,
        qdrant: QdrantService,
        llm: LocalLLMService,
        classifier: QueryRouterClassifier,
        top_k_default: int,
    ):
        self.embedder = embedder
        self.qdrant = qdrant
        self.llm = llm
        self.classifier = classifier
        self.top_k_default = top_k_default

    def semantic_search(self, query: str, top_k: int | None = None) -> list[SourceItem]:
        qvec = self.embedder.embed_one(query)
        return self.qdrant.search(qvec, top_k or self.top_k_default)

    def answer(self, query: str, top_k: int | None = None) -> QueryResponse:
        label, cls_conf, _ = self.classifier.classify(query)
        sources = self.semantic_search(query, top_k)

        context_block = "\n\n".join(
            [
                f"[source:{i+1}] file={s.file_path} heading={s.heading or '-'}\n{s.snippet}"
                for i, s in enumerate(sources)
            ]
        )

        system = PROMPT_TEMPLATES.get(label, PROMPT_TEMPLATES["general"])
        prompt = (
            f"{system}\n\n"
            "Rules:\n"
            "1) Use only provided context.\n"
            "2) Cite source indices like [source:2].\n"
            "3) Keep answer factual and concise.\n\n"
            f"Question:\n{query}\n\n"
            f"Context:\n{context_block}\n\n"
            "Answer:"
        )

        raw_answer = self.llm.generate(prompt)
        avg_score = mean([s.score for s in sources]) if sources else 0.0
        confidence = max(0.0, min(1.0, 0.65 * avg_score + 0.35 * cls_conf))

        return QueryResponse(
            answer=raw_answer,
            sources=sources,
            confidence=confidence,
            route=label,
        )

    def summarize(self, text: str) -> str:
        prompt = (
            "You summarize technical markdown notes for a knowledge worker.\n"
            "Return: 3-6 bullets and one short conclusion.\n\n"
            f"Text:\n{text}\n\nSummary:"
        )
        return self.llm.generate(prompt)
