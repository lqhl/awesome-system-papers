#!/usr/bin/env python3
"""Read-only wiki lint scanner for awesome-system-papers.

Implements the rule-based checks from wiki-lint SKILL.md.
Run: python3 .claude/skills/wiki-lint/lint.py [--summary-only] [--fix]
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WIKI = ROOT / "wiki"
QUALITY_CONFIG_PATH = WIKI / ".quality.yml"


def load_quality_config(path: Path = QUALITY_CONFIG_PATH) -> dict:
    """Load the shared quality policy. JSON is used because it is valid YAML."""
    return json.loads(path.read_text(encoding="utf-8"))


QUALITY = load_quality_config()

# Keep in sync with wiki-update SKILL Step 5 watchlist.
WATCHLIST_ENTITIES = QUALITY["watchlist"]["entities"]
WATCHLIST_CONCEPTS = QUALITY["watchlist"]["concepts"]
ENTITY_THRESHOLD = QUALITY["thresholds"]["entity_inbound"]
CONCEPT_THRESHOLD = QUALITY["thresholds"]["concept_inbound"]

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
        "review_status",
        "evidence_level",
        "last_reviewed",
    ],
    "conference": ["venue", "year", "paper_count", "first_generated", "last_updated"],
    "entity": ["kind", "aliases", "status", "last_updated"],
    "concept": ["aliases", "last_updated"],
    "comparison": ["subjects", "last_updated"],
    "theme": [
        "topic",
        "theme_kind",
        "member_tag",
        "paper_count",
        "first_generated",
        "last_updated",
        "tags",
    ],
    "proposal": [
        "name",
        "title",
        "status",
        "created",
        "evidence_mode",
        "related_papers",
        "related_concepts",
        "related_systems",
        "novelty",
        "feasibility",
        "effort",
    ],
    "probe": ["topic", "created", "last_updated", "probed_papers"],
}

PAPER_SECTION_ALIASES = {
    "问题与动机": ("问题与动机",),
    "关键观察 / 隐含假设": ("关键观察 / 隐含假设",),
    "核心方法": ("核心方法",),
    "实验与结果": ("实验与结果",),
    "论断—证据表": ("论断—证据表", "Claim–Evidence Map"),
    "批判性分析": ("批判性分析", "Critical Analysis"),
    "局限与后续工作": ("局限与后续工作", "局限与 Future Work"),
}
PAPER_REQUIRED_SECTIONS = [
    "问题与动机",
    "关键观察 / 隐含假设",
    "核心方法",
    "实验与结果",
    "批判性分析",
    "局限与后续工作",
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

WIKILINK_QUOTE_FIELDS = {
    "parent",
    "source_pdf",
    "source_md",
    "introduced_by",
    "subjects",
    "source_probe",
}

WIKILINK_RE = re.compile(r"\[\[([^\]|\\]+)(?:\\?\|[^\]]+)?\]\]")
HYBRID_RE = re.compile(r"\]\]\(")
LOG_HEADING_RE = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] .+$")
FM_BLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
FM_KEY_RE = re.compile(r"^(\w[\w_-]*):\s*(.*)$", re.MULTILINE)
ALIASES_RE = re.compile(r"aliases:\s*\[(.*?)\]", re.DOTALL)
# Conference/topic paper pages: flexible stem + venue suffix (OSDI25, arXiv15, SSRN18, …)
PAPER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]+-[A-Za-z][A-Za-z0-9-]*[0-9]{2}\.md$")
CONF_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]+-[0-9]{4}\.md$")
SECTION_RE = re.compile(r"^## +", re.MULTILINE)
EVIDENCE_LOCATOR_RE = re.compile(
    r"(?:§\s*\d|Fig(?:ure)?\.?\s*\d|Table\s*\d|图\s*\d|表\s*\d)", re.IGNORECASE
)
RESULT_VALUE_RE = re.compile(
    r"(?:\d+\.\d+|\d+(?:\.\d+)?)\s*(?:%|×|x|倍|µs|us|ms|s|GB|MB|TB|QPS|req/s|tokens?/s|Gbps|Mbps)",
    re.IGNORECASE,
)
METRIC_RE = re.compile(
    r"吞吐|延迟|成功率|准确率|命中率|得分|分数|利用率|加速|改进|"
    r"latency|throughput|speedup|开销|overhead|accuracy|recall|成本|cost|"
    r"F1|AUC|rank|score|objective|error|QPS|bandwidth",
    re.IGNORECASE,
)
BASELINE_RE = re.compile(
    r"(?:\bvs\.?\b|相比|相对|对比|优于|超过|不及|"
    r"比\s*[^\s，。；\n]{1,30}\s*(?:高|低|快|慢|提升|下降|减少|增加|更好|更差))",
    re.IGNORECASE,
)
BOUNDARY_RE = re.compile(
    r"trace|workload|benchmark|A100|H100|GPU|CPU|模型|model|集群|cluster|"
    r"请求|request|token|数据集|dataset|任务|基准|数据|硬件|设置|配置|领域|样本",
    re.IGNORECASE,
)
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
ENGLISH_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")
ENGLISH_NARRATIVE_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "when",
    "while",
    "with",
}
LEGACY_LANGUAGE_HEADINGS = {
    "Claim–Evidence Map",
    "Claim-Evidence Map",
    "Critical Analysis",
    "局限与 Future Work",
}
DESCRIPTIVE_H1_TYPES = {"theme", "proposal", "probe"}


def slug_variants(name: str) -> set[str]:
    stems = {name}
    if "-" in name:
        stems.add(name.replace("-", ""))
    else:
        kebab = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
        stems.add(kebab)
    return stems


def normalize_link_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def classify_unresolved_target(
    target: str,
    *,
    inbound: int,
    known_stems: set[str],
    decisions: dict,
    is_source: bool = False,
) -> dict[str, str | int | None]:
    """Classify an unresolved wikilink using deterministic, reviewable rules."""
    if target in decisions:
        decision = decisions[target]
        return {
            "target": target,
            "inbound": inbound,
            "category": decision["category"],
            "suggestion": decision.get("suggestion"),
            "decision": decision.get("decision"),
            "rationale": decision.get("rationale"),
            "source": "manual",
        }
    if target.endswith(".pdf") or is_source:
        return {
            "target": target,
            "inbound": inbound,
            "category": "source-broken",
            "suggestion": None,
            "source": "rule",
        }

    normalized = normalize_link_name(target)
    exact_normalized = sorted(
        stem for stem in known_stems if stem != target and normalize_link_name(stem) == normalized
    )
    if exact_normalized:
        suggestion = exact_normalized[0]
        return {
            "target": target,
            "inbound": inbound,
            "category": "rename-or-typo",
            "suggestion": suggestion,
            "source": "rule",
        }

    threshold = QUALITY["thresholds"]["concept_inbound"]
    category = "candidate-concept/entity" if inbound >= threshold else "external-or-intentional"
    return {
        "target": target,
        "inbound": inbound,
        "category": category,
        "suggestion": None,
        "source": "rule",
    }


def parse_frontmatter(text: str) -> tuple[dict[str, str], str | None]:
    m = FM_BLOCK_RE.match(text)
    if not m:
        return {}, None
    fm = {km.group(1): km.group(2).strip() for km in FM_KEY_RE.finditer(m.group(1))}
    return fm, m.group(1)


def check_proposal_evidence_frontmatter(
    fm: dict[str, str], *, probe_stems: set[str] | None = None
) -> list[str]:
    warnings: list[str] = []
    mode = fm.get("evidence_mode", "").strip("'\"")
    if mode not in {"probe-backed", "scoped"}:
        warnings.append(f"invalid evidence_mode: {mode or '(missing)'}")
        return warnings

    source = fm.get("source_probe")
    if mode == "probe-backed":
        if not source:
            warnings.append("probe-backed proposal missing source_probe")
        elif not re.fullmatch(r'["\']?\[\[[a-z][a-z0-9-]*\]\]["\']?', source):
            warnings.append("source_probe must be a quoted probe wikilink")
        elif probe_stems is not None:
            stem = source.strip("'\"")[2:-2]
            if stem not in probe_stems:
                warnings.append(f"source_probe target does not exist in wiki/probes: {stem}")
    elif source:
        warnings.append("scoped proposal should omit source_probe")
    return warnings


def parse_aliases(fm_raw: str | None) -> list[str]:
    if not fm_raw:
        return []
    m = ALIASES_RE.search(fm_raw)
    if not m:
        return []
    raw = m.group(1)
    return [a.strip().strip("'\"") for a in raw.split(",") if a.strip()]


def parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]


def extract_theme_members(text: str, paper_stems: set[str]) -> dict[str, object]:
    heading = QUALITY["theme_policy"]["core_heading"]
    body = strip_frontmatter(text)
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL
    )
    if not match:
        return {
            "has_core_section": False,
            "members": [],
            "duplicates": [],
            "unresolved": [],
        }

    members: list[str] = []
    duplicates: list[str] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    for target in WIKILINK_RE.findall(match.group(1)):
        if target in paper_stems:
            if target in seen and target not in duplicates:
                duplicates.append(target)
            elif target not in seen:
                members.append(target)
                seen.add(target)
        elif PAPER_NAME_RE.match(f"{target}.md") and target not in unresolved:
            unresolved.append(target)
    return {
        "has_core_section": True,
        "members": members,
        "duplicates": duplicates,
        "unresolved": unresolved,
    }


def _index_theme_count(index_text: str, theme_stem: str) -> int | None:
    match = re.search(
        rf"^- \[\[{re.escape(theme_stem)}(?:\\?\|[^\]]+)?\]\] — (\d+) 篇",
        index_text,
        re.MULTILINE,
    )
    return int(match.group(1)) if match else None


def _valid_member_tag(member_tag: str) -> bool:
    prefixes = "|".join(re.escape(p) for p in QUALITY["theme_policy"]["member_tag_prefixes"])
    return bool(re.fullmatch(rf"(?:{prefixes})/[a-z0-9][a-z0-9-]*", member_tag))


def find_unowned_reserved_facet_tags(
    paper_frontmatters: dict[str, dict[str, str]],
    *,
    owned_member_tags: set[str],
) -> dict[str, list[str]]:
    """Return reserved paper facets that are not owned by any current theme."""
    prefixes = set(QUALITY["theme_policy"]["member_tag_prefixes"])
    warnings: dict[str, list[str]] = {}
    for stem, paper_fm in paper_frontmatters.items():
        paper_warnings = [
            f"reserved facet tag has no owning theme: {tag}"
            for tag in parse_inline_list(paper_fm.get("tags", ""))
            if "/" in tag and tag.split("/", 1)[0] in prefixes and tag not in owned_member_tags
        ]
        if paper_warnings:
            warnings[stem] = paper_warnings
    return warnings


def analyze_theme(
    theme_stem: str,
    text: str,
    *,
    index_text: str,
    paper_frontmatters: dict[str, dict[str, str]],
) -> dict[str, object]:
    fm, _ = parse_frontmatter(text)
    member_result = extract_theme_members(text, set(paper_frontmatters))
    members = member_result["members"]
    warnings: list[str] = []

    kind = fm.get("theme_kind", "").strip("'\"")
    if kind not in QUALITY["theme_policy"]["kinds"]:
        warnings.append(f"invalid theme_kind: {kind or '(missing)'}")

    member_tag = fm.get("member_tag", "").strip("'\"")
    if not _valid_member_tag(member_tag):
        warnings.append(f"invalid member_tag: {member_tag or '(missing)'}")

    if not member_result["has_core_section"]:
        warnings.append("missing ## 核心论文 section")
    for target in member_result["duplicates"]:
        warnings.append(f"duplicate core member: {target}")
    for target in member_result["unresolved"]:
        warnings.append(f"unresolved core member: {target}")

    try:
        declared_count = int(fm.get("paper_count", ""))
    except ValueError:
        declared_count = None
    if declared_count != len(members):
        warnings.append(f"paper_count {declared_count} != core member count {len(members)}")

    index_count = _index_theme_count(index_text, theme_stem)
    if index_count is None:
        warnings.append("theme missing from index")
    elif index_count != len(members):
        warnings.append(f"index count {index_count} != core member count {len(members)}")

    if member_tag:
        for target in members:
            tags = parse_inline_list(paper_frontmatters[target].get("tags", ""))
            if member_tag not in tags:
                warnings.append(f"member missing tag: {target} -> {member_tag}")

    member_set = set(members)
    candidate_tags = set(parse_inline_list(fm.get("candidate_tags", "")))
    candidates = sorted(
        stem
        for stem, paper_fm in paper_frontmatters.items()
        if (
            (member_tag and member_tag in parse_inline_list(paper_fm.get("tags", "")))
            or candidate_tags.intersection(parse_inline_list(paper_fm.get("tags", "")))
        )
        and stem not in member_set
    )
    return {
        "members": members,
        "warnings": warnings,
        "candidates": candidates,
        **member_result,
    }


def _replace_frontmatter_scalar(text: str, key: str, value: str) -> str:
    fm, fm_raw = parse_frontmatter(text)
    match = FM_BLOCK_RE.match(text)
    if not fm_raw or not match or key not in fm:
        return text
    new_fm, count = re.subn(
        rf"^{re.escape(key)}:\s*.*$", f"{key}: {value}", fm_raw, count=1, flags=re.MULTILINE
    )
    return f"---\n{new_fm}\n---{text[match.end():]}" if count else text


def _append_inline_tag(text: str, tag: str) -> str:
    fm, fm_raw = parse_frontmatter(text)
    match = FM_BLOCK_RE.match(text)
    if not fm_raw or not match:
        return text
    tags = parse_inline_list(fm.get("tags", ""))
    if not tags or tag in tags:
        return text
    tags.append(tag)
    new_fm, count = re.subn(
        r"^tags:\s*\[[^\n]*\]$",
        f"tags: [{', '.join(tags)}]",
        fm_raw,
        count=1,
        flags=re.MULTILINE,
    )
    return f"---\n{new_fm}\n---{text[match.end():]}" if count else text


def _sync_index_theme_count(index_text: str, theme_stem: str, count: int) -> str:
    pattern = rf"(^- \[\[{re.escape(theme_stem)}(?:\\?\|[^\]]+)?\]\] — )\d+( 篇)"
    return re.sub(pattern, rf"\g<1>{count}\2", index_text, count=1, flags=re.MULTILINE)


def sync_theme_metadata(
    theme_stem: str,
    theme_text: str,
    index_text: str,
    paper_texts: dict[str, str],
) -> tuple[str, str, dict[str, str]]:
    result = extract_theme_members(theme_text, set(paper_texts))
    fm, _ = parse_frontmatter(theme_text)
    theme_kind = fm.get("theme_kind", "").strip("'\"")
    member_tag = fm.get("member_tag", "").strip("'\"")
    if (
        not result["has_core_section"]
        or result["duplicates"]
        or result["unresolved"]
        or theme_kind not in QUALITY["theme_policy"]["kinds"]
        or not _valid_member_tag(member_tag)
        or "paper_count" not in fm
        or _index_theme_count(index_text, theme_stem) is None
    ):
        return theme_text, index_text, dict(paper_texts)
    members = result["members"]
    count = len(members)
    new_theme = _replace_frontmatter_scalar(theme_text, "paper_count", str(count))
    new_index = _sync_index_theme_count(index_text, theme_stem, count)
    new_papers = dict(paper_texts)
    if member_tag:
        for stem in members:
            new_papers[stem] = _append_inline_tag(new_papers[stem], member_tag)
    return new_theme, new_index, new_papers


def add_missing_last_updated(text: str, *, today: str) -> str:
    fm, fm_raw = parse_frontmatter(text)
    match = FM_BLOCK_RE.match(text)
    if not fm_raw or not match:
        return text
    page_type = fm.get("type", "").strip("'\"")
    required = FRONTMATTER_REQUIRED.get(page_type, [])
    if "last_updated" not in required or "last_updated" in fm:
        return text
    return f"---\n{fm_raw}\nlast_updated: {today}\n---{text[match.end():]}"


def build_file_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    for base in [WIKI, ROOT / "markdowns"]:
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            if base == WIKI and WIKI / "reports" in p.parents:
                continue
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


def _first_h1(body: str) -> str | None:
    match = re.search(r"^# (?!#)(.+?)\s*$", body, re.MULTILINE)
    return match.group(1).strip() if match else None


def _narrative_lines(body: str):
    """Yield prose-like lines while skipping syntax whose language is not authored prose."""
    in_fence = False
    in_math = False
    for line_no, raw in enumerate(body.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("$$"):
            if stripped.count("$$") == 1:
                in_math = not in_math
            continue
        if in_math or not stripped:
            continue
        if stripped.startswith("> **原题**："):
            continue
        if stripped.startswith("# "):
            continue
        if stripped.startswith("|"):
            continue
        if re.match(r"^\|?\s*:?-{3,}", stripped):
            continue
        cleaned = re.sub(r"https?://\S+", "", stripped)
        cleaned = re.sub(r"\[\[[^]]+\]\]", "", cleaned)
        cleaned = re.sub(r"`[^`]*`", "", cleaned)
        cleaned = re.sub(r"\$[^$]*\$", "", cleaned)
        cleaned = re.sub(r"!?(?:\[[^]]*\])?\([^)]*\)", "", cleaned)
        yield line_no, cleaned


def check_language(text: str, fm: dict[str, str], *, page_type: str) -> list[str]:
    """Return conservative language-policy warnings for one wiki page."""
    warnings: list[str] = []
    body = strip_frontmatter(text)
    h1 = _first_h1(body)

    if page_type == "paper":
        if not h1 or not CHINESE_RE.search(h1):
            warnings.append("paper H1 must contain Chinese")
        full_title = fm.get("full_title", "").strip("'\"")
        body_lines = body.strip().splitlines()
        h1_index = next((i for i, line in enumerate(body_lines) if line.startswith("# ")), -1)
        next_index = h1_index + 1
        while next_index < len(body_lines) and not body_lines[next_index].strip():
            next_index += 1
        expected_original = f"> **原题**：{full_title}"
        if next_index >= len(body_lines) or body_lines[next_index].strip() != expected_original:
            warnings.append("paper original-title line missing or mismatched")
    elif page_type in DESCRIPTIVE_H1_TYPES and (not h1 or not CHINESE_RE.search(h1)):
        warnings.append("descriptive H1 must contain Chinese")

    for match in re.finditer(r"^##+\s+(.+?)\s*$", body, re.MULTILINE):
        heading = match.group(1)
        if heading in LEGACY_LANGUAGE_HEADINGS:
            warnings.append(f"legacy heading: {heading}")
        elif (
            not CHINESE_RE.search(heading)
            and len(ENGLISH_WORD_RE.findall(heading)) >= 2
            and not re.search(r"\bvs\.?\b", heading, re.IGNORECASE)
        ):
            warnings.append(f"English section heading: {heading}")

    body_lines = body.splitlines()
    for index, line in enumerate(body_lines[:-1]):
        stripped = line.strip()
        next_line = body_lines[index + 1].strip()
        if (
            stripped.startswith("|")
            and stripped.endswith("|")
            and re.match(r"^\|?\s*:?-{3,}", next_line)
            and not CHINESE_RE.search(stripped)
            and len(ENGLISH_WORD_RE.findall(stripped)) >= 2
        ):
            warnings.append(f"English table header at line {index + 1}")

    if page_type == "paper" and re.search(
        r"^\|\s*Claim\s*\|\s*Evidence\s*\|", body, re.MULTILINE | re.IGNORECASE
    ):
        warnings.append("paper evidence table header must be Chinese")

    for line_no, line in _narrative_lines(body):
        words = ENGLISH_WORD_RE.findall(line)
        chinese = CHINESE_RE.findall(line)
        narrative_words = sum(word.lower() in ENGLISH_NARRATIVE_WORDS for word in words)
        # Compare word count with CJK characters rather than raw Latin characters:
        # a Chinese sentence containing several long API/system names is still Chinese prose.
        if (
            len(words) >= 10
            and (len(chinese) <= 4 or len(words) >= len(chinese) * 2)
            and narrative_words >= 2
            and re.search(r"[.!?](?:\s|$)", line)
        ):
            warnings.append(f"English narrative at line {line_no}")

    return warnings


def language_paths(paths, *, wiki: Path = WIKI, root: Path = ROOT) -> list[Path]:
    """Expand language-only inputs, always excluding unpublished reports."""
    candidates: list[Path] = []
    raw_paths = list(paths)
    if not raw_paths:
        candidates = list(wiki.rglob("*.md"))
    else:
        for raw in raw_paths:
            path = Path(raw)
            if not path.is_absolute():
                path = root / path
            if path.is_dir():
                candidates.extend(path.rglob("*.md"))
            elif path.suffix == ".md" and path.exists():
                candidates.append(path)
    reports = wiki / "reports"
    ignored_logs = {
        wiki / "log.md",
        wiki / "proposals" / "_log.md",
        wiki / "probes" / "_log.md",
    }
    return sorted(
        {
            path
            for path in candidates
            if reports not in path.parents and path not in ignored_logs
        }
    )


def extract_section(body: str, heading: str) -> str | None:
    """Extract content under a level-2 heading until the next level-2 heading."""
    marker = f"## {heading}"
    if marker not in body:
        return None
    start = body.index(marker) + len(marker)
    rest = body[start:]
    m = SECTION_RE.search(rest)
    return rest[: m.start()] if m else rest


def extract_paper_section(body: str, canonical_heading: str) -> str | None:
    """Extract a canonical paper section while accepting legacy heading aliases."""
    for heading in PAPER_SECTION_ALIASES.get(canonical_heading, (canonical_heading,)):
        section = extract_section(body, heading)
        if section is not None:
            return section
    return None


def check_paper_structure(text: str, fm: dict[str, str]) -> list[str]:
    body = strip_frontmatter(text)
    warnings: list[str] = []
    for section in PAPER_REQUIRED_SECTIONS:
        if extract_paper_section(body, section) is None:
            warnings.append(f"missing section: ## {section}")

    venue = fm.get("venue", "").strip('"\'')
    tags_raw = fm.get("tags", "")
    tag_set = {t.strip().strip("'\"") for t in re.findall(r"['\"]([^'\"]+)['\"]", tags_raw)}
    is_systems = venue in SYSTEMS_VENUES or bool(tag_set & SYSTEMS_TAGS)

    obs = extract_paper_section(body, "关键观察 / 隐含假设")
    if is_systems and obs is not None:
        bullets = [ln for ln in obs.splitlines() if ln.strip().startswith("-")]
        if len(bullets) < 2:
            warnings.append("systems paper: 关键观察 < 2 bullets")

    crit = extract_paper_section(body, "批判性分析")
    if is_systems and crit is not None:
        for sub in ("论证链条", "假设压力测试", "实验可信度"):
            if sub not in crit:
                warnings.append(f"systems paper: 批判性分析 missing `{sub}`")

    fut = extract_paper_section(body, "局限与后续工作")
    if fut is not None and not any(ln.strip().startswith("-") for ln in fut.splitlines()):
        warnings.append("局限与后续工作: no bullet items")

    return warnings


def has_nested_bold(line: str) -> bool:
    """Detect the observed malformed form where an outer bold label contains inner bold."""
    stripped = line.lstrip()
    if not stripped.startswith("- **") or stripped.count("**") <= 2:
        return False
    content = stripped[4:]
    first_close = content.find("**")
    return first_close >= 0 and ("：" in content[:first_close] or ":" in content[:first_close])


def split_markdown_table_row(line: str) -> list[str]:
    """Split a Markdown table row while preserving escaped wikilink aliases."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def check_paper_quality(text: str, fm: dict[str, str], *, page_stem: str | None = None) -> list[str]:
    """Check semantic-completion signals without pretending to verify correctness."""
    warnings: list[str] = []
    body = strip_frontmatter(text)
    authors = fm.get("authors", "").lower()
    placeholders = QUALITY["paper"]["placeholder_authors"]
    if any(re.search(rf"\b{re.escape(term.lower())}\b", authors) for term in placeholders):
        warnings.append("placeholder authors")

    for phrase in QUALITY["paper"]["unresolved_phrases"]:
        if phrase in body:
            warnings.append(f"unresolved evidence phrase: {phrase}")

    status = fm.get("review_status", "").strip("'\"")
    evidence_level = fm.get("evidence_level", "").strip("'\"")
    empirical_evidence = fm.get("empirical_evidence", "").strip("'\"")
    if status not in QUALITY["paper"]["review_status"]:
        warnings.append("invalid review_status")
    if evidence_level not in QUALITY["paper"]["evidence_level"]:
        warnings.append("invalid evidence_level")
    if status == "complete" and evidence_level != "full-text":
        warnings.append("complete page must use full-text evidence")
    if status == "complete" and not EVIDENCE_LOCATOR_RE.search(body):
        warnings.append("complete page has no evidence locator")

    experiments = extract_paper_section(body, "实验与结果") or ""
    evidence_fields = (
        RESULT_VALUE_RE.search(experiments),
        METRIC_RE.search(experiments),
        BASELINE_RE.search(experiments),
        BOUNDARY_RE.search(experiments),
    )
    if (
        status == "complete"
        and empirical_evidence != "none"
        and (not evidence_fields[0] or sum(bool(v) for v in evidence_fields) < 3)
    ):
        warnings.append("experiment result lacks required evidence fields")

    claim_map = extract_paper_section(body, "论断—证据表")
    if status == "complete" and claim_map is None:
        warnings.append("complete page missing Claim–Evidence Map")
    elif status == "complete":
        claim_map = claim_map or ""
        table_rows = [line for line in claim_map.splitlines() if line.strip().startswith("|")]
        header_markers = ("| Claim |", "| 论断 |")
        rows = [
            line
            for line in table_rows
            if not re.match(r"^\s*\|?\s*-+", line)
            and not any(marker in line for marker in header_markers)
        ]
        if not 2 <= len(rows) <= 5:
            warnings.append("Claim–Evidence Map must contain 2-5 claims")
        header = next(
            (line for line in table_rows if any(marker in line for marker in header_markers)),
            None,
        )
        if header:
            width = len(split_markdown_table_row(header))
            if width not in {4, 5} or any(
                len(split_markdown_table_row(row)) != width
                or any(not cell for cell in split_markdown_table_row(row))
                for row in rows
            ):
                warnings.append("malformed Claim–Evidence Map")
        else:
            warnings.append("malformed Claim–Evidence Map")

    if any(has_nested_bold(line) for line in body.splitlines()):
        warnings.append("nested bold markup")

    if page_stem and any(target == page_stem for target in WIKILINK_RE.findall(body)):
        warnings.append("paper self-link")
    return warnings


def record_report(log_path: Path, result: dict, *, enabled: bool) -> bool:
    """Record a lint run only after explicit opt-in."""
    if not enabled:
        return False
    today = datetime.date.today().isoformat()
    old = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    entry = (
        f"## [{today}] wiki-lint\n"
        f"- Broken: {result.get('broken', 0)} | Paper quality: {result.get('paper_quality', 0)}\n"
        "- 模式：record\n\n"
    )
    divider = re.search(r"^---\s*$", old, re.MULTILINE)
    if divider:
        insert_at = divider.end()
        new_text = old[:insert_at] + "\n\n" + entry + old[insert_at:].lstrip("\n")
    else:
        new_text = old + ("\n" if old and not old.endswith("\n") else "") + entry
    log_path.write_text(new_text, encoding="utf-8")
    return True


def has_actionable_issues(result: dict) -> bool:
    keys = (
        "hybrid",
        "watchlist_missing",
        "orphans",
        "fm_warnings",
        "fm_quote_warnings",
        "log_violations",
        "alias_conflicts",
        "paper_no_link",
        "paper_quality",
        "language_warnings",
        "naming_violations",
        "theme_warnings",
    )
    return any(result.get(key, 0) for key in keys)


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
    fixed_paths: set[Path] = set()

    for p in md_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        new_text = add_missing_last_updated(text, today=today)
        fm, fm_raw = parse_frontmatter(new_text)
        m = FM_BLOCK_RE.match(new_text)
        if not fm_raw or not m:
            continue
        new_fm_raw = fm_raw

        for field in WIKILINK_QUOTE_FIELDS:
            pattern = rf"^({field}:\s*)(\[\[.+?\]\])"
            new_fm_raw, n = re.subn(pattern, r'\1"\2"', new_fm_raw, flags=re.MULTILINE)
        quoted_text = f"---\n{new_fm_raw}\n---{new_text[m.end() :]}"
        if quoted_text != text:
            new_text = quoted_text
            p.write_text(new_text, encoding="utf-8")
            fixed_paths.add(p)

    index_path = WIKI / "index.md"
    index_text = index_path.read_text(encoding="utf-8", errors="replace") if index_path.exists() else ""
    paper_paths = {p.stem: p for p in (WIKI / "papers").glob("*.md")}
    for theme_path in sorted((WIKI / "themes").glob("*.md")):
        theme_text = theme_path.read_text(encoding="utf-8", errors="replace")
        paper_texts = {
            stem: path.read_text(encoding="utf-8", errors="replace")
            for stem, path in paper_paths.items()
        }
        new_theme, new_index, new_papers = sync_theme_metadata(
            theme_path.stem, theme_text, index_text, paper_texts
        )
        if new_theme != theme_text:
            new_theme = _replace_frontmatter_scalar(new_theme, "last_updated", today)
            theme_path.write_text(new_theme, encoding="utf-8")
            fixed_paths.add(theme_path)
        if new_index != index_text:
            index_text = re.sub(
                r"^> 最后更新：\d{4}-\d{2}-\d{2}$",
                f"> 最后更新：{today}",
                new_index,
                count=1,
                flags=re.MULTILINE,
            )
        for stem, new_paper_text in new_papers.items():
            paper_path = paper_paths[stem]
            old_paper_text = paper_texts[stem]
            if new_paper_text != old_paper_text:
                paper_path.write_text(new_paper_text, encoding="utf-8")
                fixed_paths.add(paper_path)

    if index_path.exists() and index_text != index_path.read_text(encoding="utf-8", errors="replace"):
        index_path.write_text(index_text, encoding="utf-8")
        fixed_paths.add(index_path)

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
            fixed_paths.add(log_path)

    return len(fixed_paths)


def run_lint(summary_only: bool = False, apply_fix: bool = False, record: bool = False) -> dict:
    md_files = language_paths([])
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
    paper_quality: list[tuple[str, list[str]]] = []
    language_warnings: list[tuple[str, list[str]]] = []
    naming_violations: list[str] = []
    theme_warnings: list[tuple[str, list[str]]] = []
    theme_candidates: list[tuple[str, list[str]]] = []

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
    probe_stems = (
        {p.stem for p in (WIKI / "probes").glob("*.md") if p.stem != "_log"}
        if (WIKI / "probes").exists()
        else set()
    )
    paper_frontmatters = {
        p.stem: parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))[0]
        for p in paper_files
    }

    themes_dir = WIKI / "themes"
    owned_member_tags: set[str] = set()
    if themes_dir.exists():
        for theme_path in sorted(themes_dir.glob("*.md")):
            theme_text = theme_path.read_text(encoding="utf-8", errors="replace")
            theme_fm, _ = parse_frontmatter(theme_text)
            member_tag = theme_fm.get("member_tag", "").strip("'\"")
            if _valid_member_tag(member_tag):
                owned_member_tags.add(member_tag)
            analysis = analyze_theme(
                theme_path.stem,
                theme_text,
                index_text=index_text,
                paper_frontmatters=paper_frontmatters,
            )
            rel = theme_path.relative_to(ROOT).as_posix()
            if analysis["warnings"]:
                theme_warnings.append((rel, analysis["warnings"]))
            if analysis["candidates"]:
                theme_candidates.append((rel, analysis["candidates"]))

    for stem, warnings in sorted(
        find_unowned_reserved_facet_tags(
            paper_frontmatters, owned_member_tags=owned_member_tags
        ).items()
    ):
        theme_warnings.append((f"wiki/papers/{stem}.md", warnings))

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

        if page_type == "proposal":
            for warning in check_proposal_evidence_frontmatter(fm, probe_stems=probe_stems):
                fm_warnings.append(f"`{rel}`: {warning}")

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
            quality = check_paper_quality(text, fm, page_stem=p.stem)
            if quality:
                paper_quality.append((rel, quality))

        language = check_language(text, fm, page_type=page_type)
        if language:
            language_warnings.append((rel, language))

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
    for log_name in ["wiki/log.md", "wiki/proposals/_log.md", "wiki/probes/_log.md"]:
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
        "paper_quality": len(paper_quality),
        "language_warnings": len(language_warnings),
        "naming_violations": len(naming_violations),
        "theme_warnings": len(theme_warnings),
        "theme_candidates": sum(len(candidates) for _, candidates in theme_candidates),
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
        "_paper_quality": paper_quality,
        "_language_warnings": language_warnings,
        "_naming_violations": naming_violations,
        "_theme_warnings": theme_warnings,
        "_theme_candidates": theme_candidates,
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
        print(f"- Paper 质量 warning: {result['paper_quality']}")
        print(f"- Language warnings: {result['language_warnings']}")
        print(f"- 命名违规: {result['naming_violations']}")
        print(f"- Theme warnings: {result['theme_warnings']}")
        print(f"- Theme candidates: {result['theme_candidates']}")
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

        print()
        print("### 11. Paper quality warnings (top 30)")
        for rel, warns in paper_quality[:30]:
            print(f"- `{rel}`: {', '.join(warns)}")
        if not paper_quality:
            print("- (none)")

        print()
        print("### 12. Language warnings (top 30)")
        for rel, warns in language_warnings[:30]:
            print(f"- `{rel}`: {', '.join(warns)}")
        if not language_warnings:
            print("- (none)")

        print()
        print("### 13. Theme policy warnings")
        for rel, warnings in theme_warnings:
            print(f"- `{rel}`: {', '.join(warnings)}")
        if not theme_warnings:
            print("- (none)")

        print()
        print("### 14. Theme candidates (informational)")
        for rel, candidates in theme_candidates:
            print(f"- `{rel}`: {', '.join(candidates)}")
        if not theme_candidates:
            print("- (none)")

    record_report(WIKI / "log.md", result, enabled=record)

    return result


def run_language_only(paths, *, summary_only: bool = False) -> dict:
    warnings: list[tuple[str, list[str]]] = []
    for path in language_paths(paths):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = parse_frontmatter(text)
        page_type = fm.get("type", "").strip("'\"")
        found = check_language(text, fm, page_type=page_type)
        if found:
            warnings.append((path.relative_to(ROOT).as_posix(), found))
    result = {"language_warnings": len(warnings), "_language_warnings": warnings}
    if summary_only:
        print(f"language_warnings={result['language_warnings']}")
    else:
        print(f"language_warnings={result['language_warnings']}")
        for rel, found in warnings:
            print(f"- `{rel}`: {', '.join(found)}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Wiki lint scanner")
    parser.add_argument("--summary-only", action="store_true", help="Print summary counts only")
    parser.add_argument("--fix", action="store_true", help="Apply minimal safe fixes")
    parser.add_argument("--record", action="store_true", help="Explicitly append the run to wiki/log.md")
    parser.add_argument(
        "--language-only",
        nargs="+",
        metavar="PATH",
        help="Run only language checks on one or more files/directories",
    )
    args = parser.parse_args()

    if args.language_only:
        result = run_language_only(args.language_only, summary_only=args.summary_only)
        return 1 if result["language_warnings"] else 0

    result = run_lint(summary_only=args.summary_only, apply_fix=args.fix, record=args.record)

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
            "paper_quality",
            "language_warnings",
            "naming_violations",
            "theme_warnings",
            "theme_candidates",
            "fixes_applied",
        ):
            print(f"{key}={result[key]}")

    # Non-zero exit on actionable issues.
    # Broken links are mostly prospective Obsidian stubs; paper structure is informational.
    return 1 if has_actionable_issues(result) else 0


if __name__ == "__main__":
    sys.exit(main())
