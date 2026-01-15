from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.services.indexer import VaultIndexer

logger = logging.getLogger(__name__)


class _VaultEventHandler(FileSystemEventHandler):
    def __init__(self, indexer: VaultIndexer, debounce_sec: float, loop: asyncio.AbstractEventLoop):
        self.indexer = indexer
        self.debounce_sec = debounce_sec
        self.loop = loop
        self._tasks: dict[Path, concurrent.futures.Future] = {}

    def _schedule(self, path_str: str, is_delete: bool = False) -> None:
        path = Path(path_str)
        if path.suffix.lower() != ".md":
            return

        existing = self._tasks.get(path)
        if existing and not existing.done():
            existing.cancel()

        self._tasks[path] = asyncio.run_coroutine_threadsafe(self._handle(path, is_delete), self.loop)

    async def _handle(self, path: Path, is_delete: bool) -> None:
        await asyncio.sleep(self.debounce_sec)
        try:
            if is_delete:
                await self.indexer.remove_file(path)
            else:
                await self.indexer.index_file(path)
        except Exception:
            logger.exception("Watcher failed for %s", path)

    def on_created(self, event):
        if not event.is_directory:
            self._schedule(event.src_path, is_delete=False)

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule(event.src_path, is_delete=False)

    def on_deleted(self, event):
        if not event.is_directory:
            self._schedule(event.src_path, is_delete=True)


class VaultWatcher:
    def __init__(self, vault_path: Path, indexer: VaultIndexer, debounce_sec: float):
        self.vault_path = vault_path
        self.indexer = indexer
        self.debounce_sec = debounce_sec
        self.observer: Observer | None = None

    def start(self) -> None:
        if self.observer is not None:
            return
        handler = _VaultEventHandler(self.indexer, self.debounce_sec, asyncio.get_running_loop())
        observer = Observer()
        observer.schedule(handler, str(self.vault_path), recursive=True)
        observer.start()
        self.observer = observer
        logger.info("Vault watcher started on %s", self.vault_path)

    def stop(self) -> None:
        if self.observer is None:
            return
        self.observer.stop()
        self.observer.join(timeout=5)
        self.observer = None
        logger.info("Vault watcher stopped")

    @property
    def running(self) -> bool:
        return self.observer is not None and self.observer.is_alive()
