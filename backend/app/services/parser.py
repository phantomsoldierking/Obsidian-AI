from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
TAG_RE = re.compile(r"(^|\s)#([A-Za-z0-9_\-/]+)")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


@dataclass
class ParsedDocument:
    path: Path
    title: str
    body: str
    frontmatter: dict
    tags: list[str]
    headings: list[tuple[int, str]]
    links: list[str]


class MarkdownParser:
    def parse(self, path: Path) -> ParsedDocument:
        post = frontmatter.load(path)
        body = post.content or ""
        frontmatter_data = dict(post.metadata)

        headings = [(m.start(), m.group(2).strip()) for m in HEADING_RE.finditer(body)]
        tags = sorted(set(x[1] for x in TAG_RE.findall(body)))
        links = sorted(set(l.strip() for l in WIKILINK_RE.findall(body)))

        title = frontmatter_data.get("title")
        if not title:
            title = path.stem.replace("-", " ").replace("_", " ").strip()

        return ParsedDocument(
            path=path,
            title=title,
            body=body,
            frontmatter=frontmatter_data,
            tags=tags,
            headings=headings,
            links=links,
        )
