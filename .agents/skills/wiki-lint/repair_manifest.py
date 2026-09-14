#!/usr/bin/env python3
"""Generate a deterministic, resumable repair manifest for paper wiki pages."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import lint


DEFAULT_JSON = lint.WIKI / "reports" / "repair-manifest.json"
DEFAULT_MD = lint.WIKI / "reports" / "repair-manifest.md"
STATUS_ORDER = {"invalid": 0, "abstract-only": 1, "needs-review": 2, "complete": 3}


def has_placeholder_authors(fm: dict[str, str]) -> bool:
    authors = fm.get("authors", "").lower()
    return any(term.lower() in authors for term in lint.QUALITY["paper"]["placeholder_authors"])


def experiment_is_complete(body: str) -> bool:
    experiments = lint.extract_paper_section(body, "实验与结果") or ""
    fields = (
        lint.RESULT_VALUE_RE.search(experiments),
        lint.METRIC_RE.search(experiments),
        lint.BASELINE_RE.search(experiments),
        lint.BOUNDARY_RE.search(experiments),
    )
    return bool(fields[0]) and sum(bool(field) for field in fields) >= 3


def classify_page(text: str, *, source_ok: bool) -> dict[str, object]:
    fm, _ = lint.parse_frontmatter(text)
    body = lint.strip_frontmatter(text)
    issues: list[str] = []
    actions: list[str] = []

    if not source_ok:
        issues.append("missing-source")
    if has_placeholder_authors(fm):
        issues.append("placeholder-authors")
    unresolved = [phrase for phrase in lint.QUALITY["paper"]["unresolved_phrases"] if phrase in body]
    if unresolved:
        issues.extend(f"unresolved:{phrase}" for phrase in unresolved)

    has_locator = bool(lint.EVIDENCE_LOCATOR_RE.search(body))
    has_experiment = (
        fm.get("empirical_evidence", "").strip("'\"") == "none"
        or experiment_is_complete(body)
    )
    if not has_locator:
        issues.append("missing-evidence-locator")
    if not has_experiment:
        issues.append("incomplete-experiment-evidence")

    if "review_status" not in fm or "evidence_level" not in fm or "last_reviewed" not in fm:
        actions.append("add-quality-frontmatter")
    if lint.extract_paper_section(body, "论断—证据表") is None:
        actions.append("build-claim-evidence-map")

    if not source_ok or has_placeholder_authors(fm):
        status = "invalid"
        actions.append("verify-source-and-metadata")
    elif unresolved and len(body) < 3500:
        status = "abstract-only"
        actions.append("full-text-rebuild")
    elif unresolved or not has_locator or not has_experiment:
        status = "needs-review"
        actions.append("extract-and-verify-evidence")
    else:
        status = "complete"
        actions.append("verify-existing-note")

    return {
        "recommended_status": status,
        "issues": sorted(set(issues)),
        "repair_actions": list(dict.fromkeys(actions)),
    }


def source_is_resolved(fm: dict[str, str], md_index: dict, pdf_index: set, alias_index: dict) -> bool:
    for field in ("source_pdf", "source_md"):
        raw = fm.get(field, "")
        match = lint.WIKILINK_RE.search(raw)
        if not match or not lint.resolve_target(match.group(1), md_index, pdf_index, alias_index):
            return False
    return True


def build_manifest() -> dict:
    md_index = lint.build_file_index()
    pdf_index = lint.build_pdf_index()
    alias_index = lint.build_alias_index()
    pages = []
    for path in sorted((lint.WIKI / "papers").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = lint.parse_frontmatter(text)
        classification = classify_page(
            text,
            source_ok=source_is_resolved(fm, md_index, pdf_index, alias_index),
        )
        pages.append(
            {
                "page": path.relative_to(lint.ROOT).as_posix(),
                "source_pdf": fm.get("source_pdf", ""),
                "source_md": fm.get("source_md", ""),
                **classification,
            }
        )
    pages.sort(key=lambda item: (STATUS_ORDER[str(item["recommended_status"])], str(item["page"])))
    counts = Counter(str(item["recommended_status"]) for item in pages)
    return {"schema_version": 1, "paper_count": len(pages), "counts": dict(counts), "pages": pages}


def write_manifest(data: dict, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Paper Repair Manifest", "", f"- Papers: {data['paper_count']}"]
    for status in STATUS_ORDER:
        lines.append(f"- {status}: {data['counts'].get(status, 0)}")
    for status in STATUS_ORDER:
        lines.extend(["", f"## {status}", "", "| Page | Issues | Actions |", "|---|---|---|"])
        for item in data["pages"]:
            if item["recommended_status"] != status:
                continue
            page = str(item["page"]).replace("|", "\\|")
            issues = ", ".join(item["issues"]).replace("|", "\\|")
            actions = ", ".join(item["repair_actions"]).replace("|", "\\|")
            lines.append(f"| `{page}` | {issues} | {actions} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()
    data = build_manifest()
    write_manifest(data, args.json, args.markdown)
    print(json.dumps(data["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
