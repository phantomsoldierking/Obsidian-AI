from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.chunker import SectionAwareChunker
from app.services.classifier import QueryRouterClassifier
from app.services.embeddings import EmbeddingService
from app.services.graph import VaultGraphService
from app.services.indexer import VaultIndexer
from app.services.llm_service import LocalLLMService
from app.services.parser import MarkdownParser
from app.services.qdrant_service import QdrantService
from app.services.rag import RAGService
from app.services.watcher import VaultWatcher


@dataclass
class ServiceContainer:
    parser: MarkdownParser
    chunker: SectionAwareChunker
    embedder: EmbeddingService
    qdrant: QdrantService
    llm: LocalLLMService
    classifier: QueryRouterClassifier
    rag: RAGService
    indexer: VaultIndexer
    watcher: VaultWatcher
    graph: VaultGraphService



def build_container(settings: Settings) -> ServiceContainer:
    parser = MarkdownParser()
    chunker = SectionAwareChunker(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    embedder = EmbeddingService(settings.embedding_model)
    qdrant = QdrantService(settings.qdrant_url, settings.qdrant_collection, embedder.dimension)
    llm = LocalLLMService(settings.llm_model, settings.llm_max_new_tokens)
    classifier = QueryRouterClassifier(settings.classifier_model_path, settings.label_list, embedder)
    rag = RAGService(embedder, qdrant, llm, classifier, settings.top_k_default)
    indexer = VaultIndexer(settings.vault_path, parser, chunker, embedder, qdrant)
    watcher = VaultWatcher(settings.vault_path, indexer, settings.auto_reindex_debounce_sec)
    graph = VaultGraphService(settings.vault_path, parser)
    return ServiceContainer(parser, chunker, embedder, qdrant, llm, classifier, rag, indexer, watcher, graph)
