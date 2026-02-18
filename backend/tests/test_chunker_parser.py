from pathlib import Path

from app.services.chunker import SectionAwareChunker
from app.services.parser import MarkdownParser


def test_parser_extracts_frontmatter_tags_headings_links(tmp_path: Path):
    md = tmp_path / "sample.md"
    md.write_text(
        """---\ntitle: Sample Doc\n---\n# Intro\nSome text with #tag1 and [[LinkedNote]].\n## Next\nMore content.\n""",
        encoding="utf-8",
    )

    parsed = MarkdownParser().parse(md)

    assert parsed.title == "Sample Doc"
    assert "tag1" in parsed.tags
    assert any(h[1] == "Intro" for h in parsed.headings)
    assert "LinkedNote" in parsed.links


def test_chunker_splits_section_aware(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text(
        "# A\n" + ("alpha " * 300) + "\n# B\n" + ("beta " * 300),
        encoding="utf-8",
    )

    parsed = MarkdownParser().parse(md)
    chunks = SectionAwareChunker(chunk_size=300, chunk_overlap=50).chunk_document(parsed)

    assert len(chunks) > 2
    headings = {c.heading for c in chunks}
    assert "A" in headings and "B" in headings
