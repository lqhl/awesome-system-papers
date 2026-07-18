import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("lint.py")
SPEC = importlib.util.spec_from_file_location("wiki_lint", MODULE_PATH)
lint = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lint)


def paper_text(*, authors="[Alice Smith, Bob Jones]", experiments=None, evidence=None):
    experiments = experiments or (
        "- 在 ShareGPT trace、A100、OPT-13B 上，吞吐比 Orca 高 **2.2×**（Fig. 6）。"
    )
    evidence = evidence or "- **观察 1**：KV 利用率低（§3.2，Fig. 2）。\n- **假设 1**：batch 可继续扩大。"
    return f'''---
type: paper
name: Example
full_title: Example Paper
authors: {authors}
venue: OSDI
year: 2025
tags: [systems]
source_pdf: "[[example.pdf]]"
source_md: "[[example]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-12
---

# Example

## 问题与动机

Problem.

## 关键观察 / 隐含假设

{evidence}

## 核心方法

Method with [[ExampleConcept]].

## 设计取舍

- Tradeoff.

## 实验与结果

{experiments}

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Throughput improves | Fig. 6 / §6.2 | A100, OPT-13B, ShareGPT | strong |
| Tail latency remains bounded | Table 2 | A100, ShareGPT | medium |

## Critical Analysis

### 论证链条
Closed.
### 假设压力测试
Bounded.
### 实验可信度
Credible.
### 系统性缺陷
Cost.

## 局限与 Future Work

- **Future work 1**：Measure tail latency.
'''


class PaperQualityTests(unittest.TestCase):
    def test_complete_page_passes_quality_gate(self):
        fm, _ = lint.parse_frontmatter(paper_text())
        self.assertEqual([], lint.check_paper_quality(paper_text(), fm))

    def test_placeholder_author_is_rejected(self):
        text = paper_text(authors="[Matrix authors]")
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("placeholder authors", lint.check_paper_quality(text, fm))

    def test_unresolved_evidence_phrase_is_rejected(self):
        text = paper_text(experiments="- 具体倍数见原文实验节。")
        fm, _ = lint.parse_frontmatter(text)
        warnings = lint.check_paper_quality(text, fm)
        self.assertTrue(any("unresolved evidence phrase" in w for w in warnings))

    def test_experiment_requires_metric_number_baseline_and_boundary(self):
        text = paper_text(experiments="- 系统性能得到提升。")
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("experiment result lacks required evidence fields", lint.check_paper_quality(text, fm))

    def test_model_size_does_not_count_as_a_result_value(self):
        text = paper_text(experiments="- 在 OPT-13B 上，吞吐比 Orca 更高。")
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("experiment result lacks required evidence fields", lint.check_paper_quality(text, fm))

    def test_complete_descriptive_work_can_declare_no_empirical_evidence(self):
        text = paper_text(experiments="- 原文明确不包含数值实验（§1）。")
        text = text.replace("evidence_level: full-text", "evidence_level: full-text\nempirical_evidence: none")
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("experiment result lacks required evidence fields", lint.check_paper_quality(text, fm))

    def test_complete_page_requires_evidence_locator(self):
        text = paper_text(
            evidence="- **观察 1**：KV 利用率低。\n- **假设 1**：batch 可继续扩大。",
            experiments="- 在 ShareGPT trace、A100、OPT-13B 上，吞吐比 Orca 高 **2.2×**。",
        ).replace("Fig. 6 / §6.2", "main experiment").replace("Table 2", "secondary experiment")
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("complete page has no evidence locator", lint.check_paper_quality(text, fm))

    def test_claim_evidence_map_requires_two_to_five_rows(self):
        text = paper_text().replace(
            "| Throughput improves | Fig. 6 / §6.2 | A100, OPT-13B, ShareGPT | strong |",
            "| Claim one | Fig. 6 / §6.2 | A100 | strong |\n"
            "| Claim two | Table 2 | ShareGPT | medium |\n"
            "| Claim three | §7.1 | OPT-13B | weak |\n"
            "| Claim four | Fig. 8 | A100 | strong |\n"
            "| Claim five | Table 4 | ShareGPT | medium |\n"
            "| Claim six | §8 | OPT-13B | weak |",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("Claim–Evidence Map must contain 2-5 claims", lint.check_paper_quality(text, fm))

    def test_claim_evidence_map_accepts_five_columns_and_escaped_wikilinks(self):
        text = paper_text().replace(
            "| Claim | Evidence | Evaluation boundary | Confidence |\n"
            "|---|---|---|---|\n"
            "| Throughput improves | Fig. 6 / §6.2 | A100, OPT-13B, ShareGPT | strong |\n"
            "| Tail latency remains bounded | Table 2 | A100, ShareGPT | medium |",
            "| Claim | Evidence | Evaluation boundary | Locator | Confidence |\n"
            "|---|---|---|---|---|\n"
            "| Throughput improves | Fig. 6 / §6.2 | [[vLLM\\|vLLM]], A100 | §6.2 | strong |\n"
            "| Tail latency remains bounded | Table 2 | A100, ShareGPT | Table 2 | medium |",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("malformed Claim–Evidence Map", lint.check_paper_quality(text, fm))

    def test_claim_evidence_map_rejects_inconsistent_columns(self):
        text = paper_text().replace(
            "| Tail latency remains bounded | Table 2 | A100, ShareGPT | medium |",
            "| Tail latency remains bounded | Table 2 | A100, ShareGPT |",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("malformed Claim–Evidence Map", lint.check_paper_quality(text, fm))

    def test_nested_bold_and_actual_self_link_are_rejected(self):
        text = paper_text().replace(
            "- **观察 1**：KV 利用率低（§3.2，Fig. 2）。",
            "- **观察 1：KV 利用率 **20%**（§3.2，Fig. 2）。**",
        ).replace("[[ExampleConcept]]", "[[Example]]")
        fm, _ = lint.parse_frontmatter(text)
        warnings = lint.check_paper_quality(text, fm, page_stem="Example")
        self.assertIn("nested bold markup", warnings)
        self.assertIn("paper self-link", warnings)

    def test_entity_with_same_short_name_is_not_a_self_link(self):
        text = paper_text().replace("[[ExampleConcept]]", "[[Example]]")
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("paper self-link", lint.check_paper_quality(text, fm, page_stem="Example-OSDI25"))

    def test_multiple_separate_bold_spans_are_valid(self):
        text = paper_text().replace(
            "- **观察 1**：KV 利用率低（§3.2，Fig. 2）。",
            "- **观察 1**：方法保持 **exactness**（§3.2，Fig. 2）。",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("nested bold markup", lint.check_paper_quality(text, fm))

    def test_abstract_only_does_not_require_full_experiment_evidence(self):
        text = paper_text(experiments="- 摘要声称系统性能提升。")
        text = text.replace("review_status: complete", "review_status: abstract-only")
        text = text.replace("evidence_level: full-text", "evidence_level: abstract")
        text = text.replace("## Claim–Evidence Map", "## 摘要证据")
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("experiment result lacks required evidence fields", lint.check_paper_quality(text, fm))

    def test_paper_quality_is_actionable(self):
        self.assertTrue(lint.has_actionable_issues({"paper_quality": 1}))


class RecordTests(unittest.TestCase):
    def test_report_is_not_recorded_without_explicit_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "log.md"
            log_path.write_text("# Log\n", encoding="utf-8")
            lint.record_report(log_path, {"broken": 1}, enabled=False)
            self.assertEqual("# Log\n", log_path.read_text(encoding="utf-8"))

    def test_report_is_recorded_after_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "log.md"
            log_path.write_text("# Wiki Log\n\nFormat notes.\n\n---\n\n## [2026-01-01] Old\n", encoding="utf-8")
            lint.record_report(log_path, {"broken": 1, "paper_quality": 2}, enabled=True)
            text = log_path.read_text(encoding="utf-8")
            self.assertIn("Broken: 1 | Paper quality: 2", text)
            self.assertTrue(text.startswith("# Wiki Log\n"))
            self.assertLess(text.index("wiki-lint"), text.index("## [2026-01-01] Old"))


class LinkClassificationTests(unittest.TestCase):
    def test_parses_unquoted_aliases(self):
        self.assertEqual(
            ["KV cache", "KV Cache", "kv-cache"],
            lint.parse_aliases("aliases: [KV cache, KV Cache, kv-cache]"),
        )

    def test_table_wikilink_does_not_include_escape_backslash(self):
        self.assertEqual(
            ["vLLM-SOSP23"],
            lint.WIKILINK_RE.findall("| [[vLLM-SOSP23\\|vLLM]] |"),
        )

    def test_missing_pdf_is_source_broken(self):
        result = lint.classify_unresolved_target(
            "missing.pdf", inbound=1, known_stems=set(), decisions={}
        )
        self.assertEqual("source-broken", result["category"])

    def test_close_existing_stem_is_rename_or_typo(self):
        result = lint.classify_unresolved_target(
            "Paged-Attention", inbound=2, known_stems={"PagedAttention"}, decisions={}
        )
        self.assertEqual("rename-or-typo", result["category"])
        self.assertEqual("PagedAttention", result["suggestion"])

    def test_similar_but_distinct_acronyms_are_not_typos(self):
        result = lint.classify_unresolved_target(
            "LLVM", inbound=12, known_stems={"LLM"}, decisions={}
        )
        self.assertNotEqual("rename-or-typo", result["category"])

    def test_high_inbound_target_is_candidate(self):
        result = lint.classify_unresolved_target(
            "New-Mechanism", inbound=5, known_stems=set(), decisions={}
        )
        self.assertEqual("candidate-concept/entity", result["category"])

    def test_low_inbound_target_is_intentional_until_promoted(self):
        result = lint.classify_unresolved_target(
            "One-Off-Term", inbound=1, known_stems=set(), decisions={}
        )
        self.assertEqual("external-or-intentional", result["category"])

    def test_manual_decision_overrides_heuristics(self):
        result = lint.classify_unresolved_target(
            "One-Off-Term",
            inbound=1,
            known_stems=set(),
            decisions={
                "One-Off-Term": {
                    "category": "candidate-concept/entity",
                    "decision": "defer",
                    "rationale": "Needs a stable, paper-backed scope first.",
                }
            },
        )
        self.assertEqual("candidate-concept/entity", result["category"])
        self.assertEqual("defer", result["decision"])
        self.assertEqual("Needs a stable, paper-backed scope first.", result["rationale"])


if __name__ == "__main__":
    unittest.main()
