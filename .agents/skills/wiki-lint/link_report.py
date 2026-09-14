#!/usr/bin/env python3
"""Classify unresolved wiki targets and emit deterministic JSON/Markdown reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import lint


DEFAULT_JSON = lint.WIKI / "reports" / "link-status.json"
DEFAULT_MD = lint.WIKI / "reports" / "link-status.md"


def is_source_location(rel: str, line_no: int) -> bool:
    path = lint.ROOT / rel
    try:
        line = path.read_text(encoding="utf-8", errors="replace").splitlines()[line_no - 1]
    except (OSError, IndexError):
        return False
    return line.lstrip().startswith(("source_pdf:", "source_md:"))


def build_report() -> dict:
    result = lint.run_lint(summary_only=True)
    locations: dict[str, list[dict[str, object]]] = defaultdict(list)
    source_targets: set[str] = set()
    for rel, line_no, target in result["_broken"]:
        locations[target].append({"file": rel, "line": line_no})
        if is_source_location(rel, line_no):
            source_targets.add(target)

    # Rename suggestions must point to real page stems, never to another alias.
    known_stems = set(lint.build_file_index())
    decisions = lint.QUALITY.get("link_decisions", {})
    entries = []
    for target, inbound in result["_broken_targets"].most_common():
        entry = lint.classify_unresolved_target(
            target,
            inbound=inbound,
            known_stems=known_stems,
            decisions=decisions,
            is_source=target in source_targets,
        )
        entry["samples"] = locations[target][:5]
        entries.append(entry)

    counts = Counter(str(entry["category"]) for entry in entries)
    return {
        "schema_version": 1,
        "unresolved_references": result["broken"],
        "unresolved_targets": result["broken_unique"],
        "categories": dict(sorted(counts.items())),
        "targets": entries,
    }


def write_report(report: dict, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Link Status Report",
        "",
        f"- Unresolved references: {report['unresolved_references']}",
        f"- Unique targets: {report['unresolved_targets']}",
        "",
        "## Categories",
        "",
    ]
    for category, count in report["categories"].items():
        lines.append(f"- {category}: {count}")
    for category in (
        "source-broken",
        "rename-or-typo",
        "candidate-concept/entity",
        "external-or-intentional",
    ):
        lines.extend([
            "",
            f"## {category}",
            "",
            "| Target | Inbound | Decision | Rationale | Suggestion | Sample |",
            "|---|---:|---|---|---|---|",
        ])
        for entry in report["targets"]:
            if entry["category"] != category:
                continue
            sample = entry["samples"][0] if entry["samples"] else {}
            sample_text = f"{sample.get('file', '')}:{sample.get('line', '')}"
            target = str(entry["target"]).replace("|", "\\|")
            decision = str(entry.get("decision") or "").replace("|", "\\|")
            rationale = str(entry.get("rationale") or "").replace("|", "\\|")
            suggestion = str(entry.get("suggestion") or "").replace("|", "\\|")
            lines.append(
                f"| `{target}` | {entry['inbound']} | {decision} | {rationale} | `{suggestion}` | `{sample_text}` |"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()
    report = build_report()
    write_report(report, args.json, args.markdown)
    print(json.dumps(report["categories"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
