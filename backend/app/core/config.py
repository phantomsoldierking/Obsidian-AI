from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Obsidian AI Doc Intel"
    app_env: str = "dev"
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000

    vault_path: Path = Field(default=Path("/vault"))
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "obsidian_docs"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "distilgpt2"
    llm_max_new_tokens: int = 220

    classifier_model_path: Path = Field(default=Path("/app/models/doc_classifier.keras"))
    classifier_labels: str = "general,task,note,research"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,app://obsidian.md"
    top_k_default: int = 6
    chunk_size: int = 900
    chunk_overlap: int = 120

    watcher_enabled: bool = True
    auto_reindex_debounce_sec: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def label_list(self) -> list[str]:
        return [x.strip() for x in self.classifier_labels.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
