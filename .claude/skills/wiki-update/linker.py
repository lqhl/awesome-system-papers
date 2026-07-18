#!/usr/bin/env python3
"""Deterministically add first-use entity/concept links to one paper page."""

from __future__ import annotations

import argparse
import difflib
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WIKI = ROOT / "wiki"
FM_RE = re.compile(r"^---\s*\n.*?\n---", re.DOTALL)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
PREFERRED_SECTIONS = (
    "关键观察 / 隐含假设",
    "核心方法",
    "设计取舍",
    "Critical Analysis",
    "局限与 Future Work",
)


def protected_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    fm = FM_RE.match(text)
    if fm:
        spans.append(fm.span())
    for pattern in (FENCE_RE, INLINE_CODE_RE, WIKILINK_RE):
        spans.extend(match.span() for match in pattern.finditer(text))
    return sorted(spans)


def is_protected(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < span_end and end > span_start for span_start, span_end in spans)


def section_rank(text: str, pos: int) -> int:
    heading = ""
    for match in HEADING_RE.finditer(text, 0, pos):
        heading = match.group(1).strip()
    try:
        return PREFERRED_SECTIONS.index(heading)
    except ValueError:
        return len(PREFERRED_SECTIONS)


def alias_pattern(alias: str) -> re.Pattern[str]:
    left = r"(?<![A-Za-z0-9_])" if alias and (alias[0].isalnum() or alias[0] == "_") else ""
    right = r"(?![A-Za-z0-9_])" if alias and (alias[-1].isalnum() or alias[-1] == "_") else ""
    return re.compile(left + re.escape(alias) + right)


def link_text(text: str, aliases: dict[str, str]) -> tuple[str, list[dict[str, str]]]:
    """Link at most one occurrence per canonical target, preferring research sections."""
    by_canonical: dict[str, list[str]] = defaultdict(list)
    for alias, canonical in aliases.items():
        by_canonical[canonical].append(alias)

    changes: list[dict[str, str]] = []
    updated = text
    for canonical in sorted(by_canonical):
        if re.search(rf"\[\[{re.escape(canonical)}(?:\||\]\])", updated):
            continue
        spans = protected_spans(updated)
        candidates = []
        for alias in sorted(by_canonical[canonical], key=len, reverse=True):
            for match in alias_pattern(alias).finditer(updated):
                if not is_protected(match.start(), match.end(), spans):
                    candidates.append((section_rank(updated, match.start()), match.start(), -len(alias), match, alias))
        if not candidates:
            continue
        _, _, _, match, alias = min(candidates, key=lambda item: item[:3])
        replacement = f"[[{canonical}|{alias}]]"
        updated = updated[: match.start()] + replacement + updated[match.end() :]
        changes.append({"canonical": canonical, "alias": alias})
    return updated, changes


def parse_aliases(raw: str) -> list[str]:
    match = re.search(r"^aliases:\s*\[(.*?)\]", raw, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    return [value.strip().strip("'\"") for value in match.group(1).split(",") if value.strip()]


def build_alias_map() -> dict[str, str]:
    owners: dict[str, set[str]] = defaultdict(set)
    for subdir in ("entities", "concepts"):
        for path in (WIKI / subdir).glob("*.md"):
            raw = path.read_text(encoding="utf-8", errors="replace")
            for alias in {path.stem, *parse_aliases(raw)}:
                owners[alias].add(path.stem)
    return {alias: next(iter(targets)) for alias, targets in owners.items() if len(targets) == 1}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write the patch; default is dry-run")
    args = parser.parse_args()
    path = args.paper.resolve()
    if path.parent != (WIKI / "papers").resolve():
        parser.error("paper must be directly under wiki/papers")
    old = path.read_text(encoding="utf-8")
    new, changes = link_text(old, build_alias_map())
    if not changes:
        print("No safe link changes.")
        return 0
    if args.apply:
        path.write_text(new, encoding="utf-8")
        print(f"Applied {len(changes)} links to {path.relative_to(ROOT)}")
    else:
        print("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(path), tofile=str(path))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
