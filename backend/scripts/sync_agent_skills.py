#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

MARKER_FILE = ".managed_by_obsidianai"


@dataclass
class SkillItem:
    name: str
    path: Path
    is_dir: bool


def expand(path_str: str) -> Path:
    return Path(os.path.expanduser(path_str)).resolve()


def detect_source(vault_path: Path, source_folder_name: str) -> Path:
    if vault_path.name.lower() in {"skill", "skills"}:
        return vault_path

    candidates = [vault_path / source_folder_name]
    if source_folder_name.lower() != "skill":
        candidates.append(vault_path / "skill")
    if source_folder_name.lower() != "skills":
        candidates.append(vault_path / "skills")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        f"No skill source found. Checked vault root name and folders: {[c.as_posix() for c in candidates]}"
    )


def collect_skills(source: Path) -> list[SkillItem]:
    items: list[SkillItem] = []
    for child in sorted(source.iterdir(), key=lambda x: x.name.lower()):
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "SKILL.md").exists():
            items.append(SkillItem(name=child.name, path=child, is_dir=True))
        elif child.is_file() and child.suffix.lower() == ".md":
            items.append(SkillItem(name=child.stem, path=child, is_dir=False))

    if not items and (source / "SKILL.md").exists():
        items.append(SkillItem(name=source.name, path=source, is_dir=True))

    return items


def prepare_target(target: Path, force: bool) -> None:
    target.mkdir(parents=True, exist_ok=True)
    marker = target / MARKER_FILE

    if marker.exists() or not any(target.iterdir()):
        for child in list(target.iterdir()):
            if child.name == MARKER_FILE:
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
        marker.write_text("managed=true\n", encoding="utf-8")
        return

    if not force:
        raise RuntimeError(f"Target {target} contains unmanaged files. Use --force to overwrite.")

    for child in list(target.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    marker.write_text("managed=true\n", encoding="utf-8")


def copy_skill(item: SkillItem, target: Path) -> None:
    dst = target / item.name
    if item.is_dir:
        shutil.copytree(item.path, dst)
        return

    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(item.path, dst / "SKILL.md")


def link_skill(item: SkillItem, target: Path) -> None:
    dst = target / item.name
    if item.is_dir:
        dst.symlink_to(item.path, target_is_directory=True)
        return

    dst.mkdir(parents=True, exist_ok=True)
    (dst / "SKILL.md").symlink_to(item.path)


def sync_target(target: Path, skills: list[SkillItem], mode: str, force: bool) -> dict:
    prepare_target(target, force=force)

    created: list[str] = []
    for skill in skills:
        if mode == "symlink":
            link_skill(skill, target)
        else:
            copy_skill(skill, target)
        created.append(skill.name)

    return {
        "target": target.as_posix(),
        "mode": mode,
        "skills": created,
        "count": len(created),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync vault skills to local coding agent skill dirs")
    parser.add_argument("--vault-path", required=True)
    parser.add_argument("--source-folder", default="skills")
    parser.add_argument("--agent", choices=["codex", "claude", "both"], default="both")
    parser.add_argument("--codex-target", default="~/.codex/skills/obsidian-vault")
    parser.add_argument("--claude-target", default="~/.claude/skills/obsidian-vault")
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    vault_path = expand(args.vault_path)
    source = detect_source(vault_path, args.source_folder)
    skills = collect_skills(source)
    if not skills:
        raise RuntimeError(f"No skills found in {source}")

    outputs = []
    if args.agent in {"codex", "both"}:
        outputs.append(sync_target(expand(args.codex_target), skills, mode=args.mode, force=args.force))
    if args.agent in {"claude", "both"}:
        outputs.append(sync_target(expand(args.claude_target), skills, mode=args.mode, force=args.force))

    print(
        json.dumps(
            {
                "vault": vault_path.as_posix(),
                "source": source.as_posix(),
                "skills_found": len(skills),
                "targets": outputs,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
