#!/usr/bin/env python3
"""Read-only wiki lint scanner for awesome-system-papers.

Implements the rule-based checks from wiki-lint SKILL.md.
Run: python3 .claude/skills/wiki-lint/lint.py [--summary-only] [--fix]
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WIKI = ROOT / "wiki"

# Keep in sync with wiki-update SKILL Step 5 watchlist.
WATCHLIST_ENTITIES = [
    "vLLM",
    "SGLang",
    "TensorRT-LLM",
    "DeepSpeed",
    "Megatron",
    "Mooncake",
]
WATCHLIST_CONCEPTS = [
    "KV-Cache",
    "MoE",
    "PagedAttention",
    "Speculative-Decoding",
    "FlashAttention",
    "Prefix-Caching",
    "Disaggregation",
    "RDMA",
    "Continuous-Batching",
    "RadixAttention",
]

ENTITY_THRESHOLD = 3
CONCEPT_THRESHOLD = 5

FRONTMATTER_REQUIRED = {
    "paper": [
        "name",
        "full_title",
        "authors",
        "venue",
        "year",
        "tags",
        "source_pdf",
        "source_md",
    ],
    "conference": ["venue", "year", "paper_count", "first_generated", "last_updated"],
    "entity": ["kind", "aliases", "status", "last_updated"],
    "concept": ["aliases", "last_updated"],
    "comparison": ["subjects", "last_updated"],
    "theme": ["last_updated", "tags"],
    "proposal": [
        "name",
        "title",
        "status",
        "created",
        "related_papers",
        "related_concepts",
        "related_systems",
        "novelty",
        "feasibility",
        "effort",
    ],
    "probe": ["topic", "created", "probed_papers"],
}

PAPER_REQUIRED_SECTIONS = [
    "## 问题与动机",
    "## 关键观察 / 隐含假设",
    "## 核心方法",
    "## 实验与结果",
    "## Critical Analysis",
    "## 局限与 Future Work",
]

SYSTEMS_VENUES = {"OSDI", "SOSP", "NSDI", "ATC", "FAST", "MLSys"}
SYSTEMS_TAGS = {
    "systems",
    "ml-systems",
    "storage",
    "networking",
    "llm-inference",
    "distributed",
}

WIKILINK_QUOTE_FIELDS = {"parent", "source_pdf", "source_md", "introduced_by", "subjects"}

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
HYBRID_RE = re.compile(r"\]\]\(")
LOG_HEADING_RE = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] .+$")
FM_BLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
FM_KEY_RE = re.compile(r"^(\w[\w_-]*):\s*(.*)$", re.MULTILINE)
ALIASES_RE = re.compile(r"aliases:\s*\[(.*?)\]", re.DOTALL)
# Conference/topic paper pages: flexible stem + venue suffix (OSDI25, arXiv15, SSRN18, …)
PAPER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]+-[A-Za-z][A-Za-z0-9-]*[0-9]{2}\.md$")
CONF_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]+-[0-9]{4}\.md$")
SECTION_RE = re.compile(r"^## +", re.MULTILINE)


def slug_variants(name: str) -> set[str]:
    stems = {name}
    if "-" in name:
        stems.add(name.replace("-", ""))
    else:
        kebab = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
        stems.add(kebab)
    return stems


def parse_frontmatter(text: str) -> tuple[dict[str, str], str | None]:
    m = FM_BLOCK_RE.match(text)
    if not m:
        return {}, None
    fm = {km.group(1): km.group(2).strip() for km in FM_KEY_RE.finditer(m.group(1))}
    return fm, m.group(1)


def parse_aliases(fm_raw: str | None) -> list[str]:
    if not fm_raw:
        return []
    m = ALIASES_RE.search(fm_raw)
    if not m:
        return []
    raw = m.group(1)
    return [a.strip().strip("'\"") for a in re.findall(r"['\"]([^'\"]+)['\"]", raw)]


def build_file_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    for base in [WIKI, ROOT / "markdowns"]:
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            index[p.stem].append(p)
    return index


def build_alias_index() -> dict[str, set[str]]:
    """alias or stem -> canonical wiki page stems."""
    alias_to_stems: dict[str, set[str]] = defaultdict(set)
    for sub in ("entities", "concepts"):
        d = WIKI / sub
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            text = p.read_text(encoding="utf-8", errors="replace")
            _, fm_raw = parse_frontmatter(text)
            names = {p.stem} | set(slug_variants(p.stem))
            names.update(parse_aliases(fm_raw))
            for n in names:
                alias_to_stems[n].update(names)
    return alias_to_stems


def build_pdf_index() -> set[str]:
    pdfs: set[str] = set()
    papers_dir = ROOT / "papers"
    if papers_dir.exists():
        for p in papers_dir.rglob("*.pdf"):
            pdfs.add(p.name)
            pdfs.add(p.stem)
    return pdfs


def resolve_target(target: str, md_index: dict, pdf_index: set, alias_index: dict) -> bool:
    if target.endswith(".pdf"):
        base = target.split("/")[-1]
        return base in pdf_index or Path(base).stem in pdf_index
    for name in slug_variants(target) | {target}:
        if name in md_index:
            return True
        if name in alias_index:
            return True
    return False


def has_entity_page(name: str, entity_stems: set[str], alias_index: dict) -> bool:
    for variant in slug_variants(name) | {name}:
        if variant in entity_stems:
            return True
        if variant in alias_index and any(s in entity_stems for s in alias_index[variant]):
            return True
    return False


def has_concept_page(name: str, concept_stems: set[str], alias_index: dict) -> bool:
    for variant in slug_variants(name) | {name}:
        if variant in concept_stems:
            return True
        if variant in alias_index and any(s in concept_stems for s in alias_index[variant]):
            return True
    return False


def count_inbound(term: str, files: list[Path]) -> int:
    patterns = [f"[[{term}]]", f"[[{term}|"]
    count = 0
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in patterns:
            count += text.count(pat)
    return count


def strip_frontmatter(text: str) -> str:
    m = FM_BLOCK_RE.match(text)
    if m:
        return text[m.end() :]
    return text


def extract_section(body: str, heading: str) -> str | None:
    """Extract content under a level-2 heading until the next level-2 heading."""
    marker = f"## {heading}"
    if marker not in body:
        return None
    start = body.index(marker) + len(marker)
    rest = body[start:]
    m = SECTION_RE.search(rest)
    return rest[: m.start()] if m else rest


def check_paper_structure(text: str, fm: dict[str, str]) -> list[str]:
    body = strip_frontmatter(text)
    warnings: list[str] = []
    for section in PAPER_REQUIRED_SECTIONS:
        heading = section.removeprefix("## ")
        if extract_section(body, heading) is None:
            warnings.append(f"missing section: {section}")

    venue = fm.get("venue", "").strip('"\'')
    tags_raw = fm.get("tags", "")
    tag_set = {t.strip().strip("'\"") for t in re.findall(r"['\"]([^'\"]+)['\"]", tags_raw)}
    is_systems = venue in SYSTEMS_VENUES or bool(tag_set & SYSTEMS_TAGS)

    obs = extract_section(body, "关键观察 / 隐含假设")
    if is_systems and obs is not None:
        bullets = [ln for ln in obs.splitlines() if ln.strip().startswith("-")]
        if len(bullets) < 2:
            warnings.append("systems paper: 关键观察 < 2 bullets")

    crit = extract_section(body, "Critical Analysis")
    if is_systems and crit is not None:
        for sub in ("论证链条", "假设压力测试", "实验可信度"):
            if sub not in crit:
                warnings.append(f"systems paper: Critical Analysis missing `{sub}`")

    fut = extract_section(body, "局限与 Future Work")
    if fut is not None and not any(ln.strip().startswith("-") for ln in fut.splitlines()):
        warnings.append("局限与 Future Work: no bullet items")

    return warnings


def check_naming(p: Path) -> str | None:
    name = p.name
    parent = p.parent.name
    stem = p.stem
    if parent == "papers" and not PAPER_NAME_RE.match(name):
        return "paper filename does not match {Name}-{Conf}{Year}.md"
    if parent == "conferences" and not CONF_NAME_RE.match(name):
        return "conference filename does not match {Conf}-{Year}.md"
    if parent in {"entities", "concepts", "comparisons", "themes"}:
        if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", stem):
            return "invalid PascalCase/kebab-case stem"
    if parent == "proposals" and stem != "_log":
        if not re.match(r"^[A-Z][A-Za-z0-9]+$", stem):
            return "proposal should use PascalCase"
    if parent == "probes":
        if not re.match(r"^[a-z][a-z0-9-]*$", stem):
            return "probe should use kebab-case"
    return None


def apply_fixes(md_files: list[Path], log_violations: list[tuple[str, int, str]]) -> int:
    today = datetime.date.today().isoformat()
    fixed = 0

    for p in md_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, fm_raw = parse_frontmatter(text)
        m = FM_BLOCK_RE.match(text)
        if not fm_raw or not m:
            continue
        page_type = fm.get("type", "").strip('"\'')
        new_fm_raw = fm_raw
        changed = False

        if page_type and "last_updated" not in fm:
            new_fm_raw += f"\nlast_updated: {today}"
            changed = True

        for field in WIKILINK_QUOTE_FIELDS:
            pattern = rf"^({field}:\s*)(\[\[.+?\]\])"
            new_fm_raw, n = re.subn(pattern, r'\1"\2"', new_fm_raw, flags=re.MULTILINE)
            if n:
                changed = True

        if changed:
            new_text = f"---\n{new_fm_raw}\n---{text[m.end() :]}"
            p.write_text(new_text, encoding="utf-8")
            fixed += 1

    for log_name, line_no, line in log_violations:
        log_path = ROOT / log_name
        if not log_path.exists():
            continue
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line_no > len(lines):
            continue
        raw = lines[line_no - 1]
        m = re.match(r"^## (\d{4}-\d{2}-\d{2}) (.+)$", raw)
        if m:
            lines[line_no - 1] = f"## [{m.group(1)}] {m.group(2)}"
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            fixed += 1

    return fixed


def run_lint(summary_only: bool = False, apply_fix: bool = False) -> dict:
    md_files = sorted(WIKI.rglob("*.md"))
    paper_files = sorted((WIKI / "papers").glob("*.md")) if (WIKI / "papers").exists() else []
    md_index = build_file_index()
    pdf_index = build_pdf_index()
    alias_index = build_alias_index()

    broken: list[tuple[str, int, str]] = []
    broken_targets: Counter[str] = Counter()
    hybrid: list[tuple[str, int, str]] = []
    fm_warnings: list[str] = []
    fm_quote_warnings: list[str] = []
    orphans: list[str] = []
    alias_conflicts: list[str] = []
    paper_no_link: list[str] = []
    paper_structure: list[tuple[str, list[str]]] = []
    naming_violations: list[str] = []

    inbound_targets: dict[str, set[str]] = defaultdict(set)
    index_text = (WIKI / "index.md").read_text(encoding="utf-8", errors="replace") if (WIKI / "index.md").exists() else ""

    entity_stems = (
        {p.stem for p in (WIKI / "entities").glob("*.md")}
        if (WIKI / "entities").exists()
        else set()
    )
    concept_stems = (
        {p.stem for p in (WIKI / "concepts").glob("*.md")}
        if (WIKI / "concepts").exists()
        else set()
    )

    # Alias conflicts
    alias_owner: dict[str, list[str]] = defaultdict(list)
    for sub in ("entities", "concepts"):
        d = WIKI / sub
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            rel = p.relative_to(ROOT).as_posix()
            _, fm_raw = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            for alias in parse_aliases(fm_raw) + [p.stem]:
                alias_owner[alias].append(rel)
    for alias, pages in sorted(alias_owner.items()):
        unique = sorted(set(pages))
        if len(unique) > 1:
            alias_conflicts.append(f"`{alias}` -> {', '.join(unique)}")

    for p in md_files:
        rel = p.relative_to(ROOT).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
        except OSError:
            continue

        fm, fm_raw = parse_frontmatter(text)
        page_type = fm.get("type", "").strip('"\'')

        naming_issue = check_naming(p)
        if naming_issue:
            naming_violations.append(f"`{rel}`: {naming_issue}")

        if page_type in FRONTMATTER_REQUIRED:
            missing = [k for k in FRONTMATTER_REQUIRED[page_type] if k not in fm]
            if missing:
                fm_warnings.append(f"`{rel}`: missing {', '.join(missing)}")

        if fm_raw:
            for field in WIKILINK_QUOTE_FIELDS:
                if re.search(rf"^{field}:\s*\[\[", fm_raw, re.MULTILINE):
                    fm_quote_warnings.append(f"`{rel}`: `{field}` wikilink not quoted")

        if page_type == "paper":
            body_links = WIKILINK_RE.findall(strip_frontmatter(text))
            non_source = [t for t in body_links if t not in ("source_pdf", "source_md")]
            if not non_source:
                paper_no_link.append(rel)
            struct = check_paper_structure(text, fm)
            if struct:
                paper_structure.append((rel, struct))

        for i, line in enumerate(lines, 1):
            if HYBRID_RE.search(line):
                hybrid.append((rel, i, line.strip()[:120]))
            for m in WIKILINK_RE.finditer(line):
                target = m.group(1).strip()
                inbound_targets[target].add(rel)
                if not resolve_target(target, md_index, pdf_index, alias_index):
                    broken.append((rel, i, target))
                    broken_targets[target] += 1

    watchlist_missing = []
    for term in WATCHLIST_ENTITIES:
        if has_entity_page(term, entity_stems, alias_index):
            continue
        inbound = count_inbound(term, paper_files)
        if inbound >= ENTITY_THRESHOLD:
            watchlist_missing.append((term, "entity", inbound))
    for term in WATCHLIST_CONCEPTS:
        if has_concept_page(term, concept_stems, alias_index):
            continue
        inbound = count_inbound(term, paper_files)
        if inbound >= CONCEPT_THRESHOLD:
            watchlist_missing.append((term, "concept", inbound))
    watchlist_missing.sort(key=lambda x: -x[2])

    for p in md_files:
        if p.parent.name not in ("entities", "concepts", "comparisons", "themes"):
            continue
        rel = p.relative_to(ROOT).as_posix()
        stem = p.stem
        has_inbound = False
        for variant in slug_variants(stem) | {stem}:
            refs = inbound_targets.get(variant, set()) - {rel}
            if refs:
                has_inbound = True
                break
            if f"[[{variant}]]" in index_text or f"[[{variant}|" in index_text:
                has_inbound = True
                break
        if not has_inbound:
            orphans.append(rel)

    log_violations: list[tuple[str, int, str]] = []
    for log_name in ["wiki/log.md", "wiki/proposals/_log.md"]:
        log_path = ROOT / log_name
        if not log_path.exists():
            continue
        for i, line in enumerate(log_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.startswith("## ") and not LOG_HEADING_RE.match(line):
                log_violations.append((log_name, i, line))

    fixes_applied = 0
    if apply_fix:
        fixes_applied = apply_fixes(md_files, log_violations)

    result = {
        "broken": len(broken),
        "broken_unique": len(broken_targets),
        "hybrid": len(hybrid),
        "watchlist_missing": len(watchlist_missing),
        "orphans": len(orphans),
        "fm_warnings": len(fm_warnings),
        "fm_quote_warnings": len(fm_quote_warnings),
        "log_violations": len(log_violations),
        "alias_conflicts": len(alias_conflicts),
        "paper_no_link": len(paper_no_link),
        "paper_structure": len(paper_structure),
        "naming_violations": len(naming_violations),
        "fixes_applied": fixes_applied,
        "_broken": broken,
        "_broken_targets": broken_targets,
        "_hybrid": hybrid,
        "_watchlist_missing": watchlist_missing,
        "_orphans": orphans,
        "_fm_warnings": fm_warnings,
        "_fm_quote_warnings": fm_quote_warnings,
        "_log_violations": log_violations,
        "_alias_conflicts": alias_conflicts,
        "_paper_no_link": paper_no_link,
        "_paper_structure": paper_structure,
        "_naming_violations": naming_violations,
    }

    if not summary_only:
        today = datetime.date.today().isoformat()
        print(f"# Wiki Lint Report ({today})\n")
        print("## Summary\n")
        print(f"- Broken wikilinks: {result['broken']} ({result['broken_unique']} unique targets)")
        print(f"- Hybrid wikilink + paren: {result['hybrid']}")
        print(f"- 高频缺页建议: {result['watchlist_missing']}")
        print(f"- Orphan pages: {result['orphans']}")
        print(f"- Frontmatter warnings: {result['fm_warnings']}")
        print(f"- Frontmatter wikilink unquoted: {result['fm_quote_warnings']}")
        print(f"- Log 格式违规: {result['log_violations']}")
        print(f"- Alias 冲突: {result['alias_conflicts']}")
        print(f"- Paper 页无 wikilink: {result['paper_no_link']}")
        print(f"- Paper 结构 warning: {result['paper_structure']}")
        print(f"- 命名违规: {result['naming_violations']}")
        if apply_fix:
            print(f"- Fixes applied: {result['fixes_applied']}")
        print()

        print("### 1. Broken wikilinks — top targets by frequency")
        for target, cnt in broken_targets.most_common(20):
            print(f"- `[[{target}]]` — {cnt} refs")
        if not broken_targets:
            print("- (none)")
        print()

        print("### 1b. Broken wikilinks — sample locations (top 15)")
        for rel, ln, target in broken[:15]:
            print(f"- `{rel}:{ln}`: `[[{target}]]`")
        if not broken:
            print("- (none)")
        print()

        print("### 2. Hybrid wikilink + paren")
        for rel, ln, snippet in hybrid[:20]:
            print(f"- `{rel}:{ln}`: `{snippet}`")
        if not hybrid:
            print("- (none)")
        print()

        print("### 3. 高频缺页 watchlist")
        for term, kind, inbound in watchlist_missing:
            print(f"- {term} ({kind}, inbound={inbound}) — 缺页")
        if not watchlist_missing:
            print("- (none)")
        print()

        print("### 4. Orphan pages")
        for rel in orphans:
            print(f"- `{rel}`")
        if not orphans:
            print("- (none)")
        print()

        print("### 5. Frontmatter issues")
        for w in fm_warnings[:20]:
            print(f"- {w}")
        for w in fm_quote_warnings[:20]:
            print(f"- {w}")
        if not fm_warnings and not fm_quote_warnings:
            print("- (none)")
        print()

        print("### 6. log.md format issues")
        for log_name, i, line in log_violations:
            print(f"- `{log_name}:{i}`: `{line[:80]}`")
        if not log_violations:
            print("- (none)")
        print()

        print("### 7. Alias conflicts")
        for c in alias_conflicts[:20]:
            print(f"- {c}")
        if not alias_conflicts:
            print("- (none)")
        print()

        print("### 8. Paper pages with no body wikilinks")
        for rel in paper_no_link[:20]:
            print(f"- `{rel}`")
        if not paper_no_link:
            print("- (none)")
        print()

        print("### 9. Paper structure warnings (top 20)")
        for rel, warns in paper_structure[:20]:
            print(f"- `{rel}`: {', '.join(warns)}")
        if not paper_structure:
            print("- (none)")
        print()

        print("### 10. Naming violations")
        for v in naming_violations[:20]:
            print(f"- {v}")
        if not naming_violations:
            print("- (none)")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Wiki lint scanner")
    parser.add_argument("--summary-only", action="store_true", help="Print summary counts only")
    parser.add_argument("--fix", action="store_true", help="Apply minimal safe fixes")
    args = parser.parse_args()

    result = run_lint(summary_only=args.summary_only, apply_fix=args.fix)

    if args.summary_only:
        for key in (
            "broken",
            "broken_unique",
            "hybrid",
            "watchlist_missing",
            "orphans",
            "fm_warnings",
            "fm_quote_warnings",
            "log_violations",
            "alias_conflicts",
            "paper_no_link",
            "paper_structure",
            "naming_violations",
            "fixes_applied",
        ):
            print(f"{key}={result[key]}")

    # Non-zero exit on actionable issues.
    # Broken links are mostly prospective Obsidian stubs; paper structure is informational.
    critical = (
        result["hybrid"]
        + result["watchlist_missing"]
        + result["orphans"]
        + result["fm_warnings"]
        + result["fm_quote_warnings"]
        + result["log_violations"]
        + result["alias_conflicts"]
        + result["paper_no_link"]
        + result["naming_violations"]
    )
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())