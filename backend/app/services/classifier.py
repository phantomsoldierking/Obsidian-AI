from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import tensorflow as tf

from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class QueryRouterClassifier:
    def __init__(self, model_path: Path, labels: list[str], embedding_service: EmbeddingService):
        self.labels = labels
        self.embedding_service = embedding_service
        self.model = None

        if model_path.exists():
            logger.info("Loading TensorFlow classifier from %s", model_path)
            self.model = tf.keras.models.load_model(model_path)
        else:
            logger.warning("Classifier model not found at %s; using heuristic fallback", model_path)

    def classify(self, text: str) -> tuple[str, float, dict[str, float]]:
        if self.model is None:
            return self._heuristic(text)

        vec = np.array([self.embedding_service.embed_one(text)], dtype=np.float32)
        probs = self.model.predict(vec, verbose=0)[0]
        idx = int(np.argmax(probs))
        scores = {self.labels[i]: float(probs[i]) for i in range(min(len(self.labels), len(probs)))}
        label = self.labels[idx] if idx < len(self.labels) else "general"
        return label, float(probs[idx]), scores

    def _heuristic(self, text: str) -> tuple[str, float, dict[str, float]]:
        q = text.lower()
        if any(k in q for k in ["todo", "task", "deadline", "remind"]):
            return "task", 0.6, {"task": 0.6, "general": 0.4}
        if any(k in q for k in ["summarize", "summary", "tl;dr"]):
            return "note", 0.55, {"note": 0.55, "general": 0.45}
        if any(k in q for k in ["compare", "analyze", "evidence", "study"]):
            return "research", 0.58, {"research": 0.58, "general": 0.42}
        return "general", 0.5, {"general": 0.5}


PROMPT_TEMPLATES = {
    "general": "You are a precise Obsidian assistant. Use only the context to answer. If unknown, say so.",
    "task": "You are a productivity assistant. Extract concrete actions with deadlines when present.",
    "note": "You are a note synthesis assistant. Produce concise summaries and key bullets.",
    "research": "You are a research analyst. Highlight evidence, assumptions, and disagreements.",
}
