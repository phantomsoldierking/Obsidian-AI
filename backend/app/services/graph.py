from __future__ import annotations

from pathlib import Path

from app.models.schemas import GraphEdge, GraphNode, GraphResponse
from app.services.parser import MarkdownParser


class VaultGraphService:
    def __init__(self, vault_path: Path, parser: MarkdownParser):
        self.vault_path = vault_path
        self.parser = parser

    def build_graph(self) -> GraphResponse:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        files = list(self.vault_path.rglob("*.md"))
        existing = {f.stem for f in files}

        for md in files:
            parsed = self.parser.parse(md)
            rel = md.relative_to(self.vault_path).as_posix()
            nodes.append(GraphNode(id=rel, title=parsed.title))
            for link in parsed.links:
                if link in existing:
                    target = next((f for f in files if f.stem == link), None)
                    if target is not None:
                        edges.append(
                            GraphEdge(
                                source=rel,
                                target=target.relative_to(self.vault_path).as_posix(),
                            )
                        )

        return GraphResponse(nodes=nodes, edges=edges)
