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
        "- 在 ShareGPT 轨迹、A100、OPT-13B 上，吞吐比 Orca 高 **2.2×**（图 6）。"
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

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 吞吐有所提高 | 图 6 / §6.2 | A100、OPT-13B、ShareGPT | 强 |
| 尾延迟仍受控制 | 表 2 | A100、ShareGPT | 中 |

## 批判性分析

### 论证链条
Closed.
### 假设压力测试
Bounded.
### 实验可信度
Credible.
### 系统性缺陷
Cost.

## 局限与后续工作

- **后续工作 1**：测量尾延迟。
'''


class ProposalEvidenceTests(unittest.TestCase):
    def test_probe_backed_requires_wikilink_source_probe(self):
        self.assertEqual(
            [],
            lint.check_proposal_evidence_frontmatter(
                {
                    "evidence_mode": "probe-backed",
                    "source_probe": '"[[thinking-model-kv-cache]]"',
                }
            ),
        )

    def test_probe_backed_without_source_is_rejected(self):
        self.assertIn(
            "probe-backed proposal missing source_probe",
            lint.check_proposal_evidence_frontmatter({"evidence_mode": "probe-backed"}),
        )

    def test_probe_backed_source_must_exist_in_probe_directory(self):
        self.assertIn(
            "source_probe target does not exist in wiki/probes: missing-probe",
            lint.check_proposal_evidence_frontmatter(
                {
                    "evidence_mode": "probe-backed",
                    "source_probe": '"[[missing-probe]]"',
                },
                probe_stems={"known-probe"},
            ),
        )

    def test_scoped_omits_source_probe(self):
        self.assertEqual(
            [], lint.check_proposal_evidence_frontmatter({"evidence_mode": "scoped"})
        )
        self.assertIn(
            "scoped proposal should omit source_probe",
            lint.check_proposal_evidence_frontmatter(
                {"evidence_mode": "scoped", "source_probe": '"[[unused]]"'}
            ),
        )

    def test_invalid_evidence_mode_is_rejected(self):
        self.assertIn(
            "invalid evidence_mode: exhaustive",
            lint.check_proposal_evidence_frontmatter({"evidence_mode": "exhaustive"}),
        )


class PaperQualityTests(unittest.TestCase):
    def test_complete_page_passes_quality_gate(self):
        fm, _ = lint.parse_frontmatter(paper_text())
        self.assertEqual([], lint.check_paper_quality(paper_text(), fm))

    def test_legacy_english_headings_remain_compatible(self):
        text = (
            paper_text()
            .replace("## 论断—证据表", "## Claim–Evidence Map")
            .replace("| 论断 | 证据 | 评测边界 | 置信度 |", "| Claim | Evidence | Evaluation boundary | Confidence |")
            .replace("## 批判性分析", "## Critical Analysis")
            .replace("## 局限与后续工作", "## 局限与 Future Work")
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertEqual([], lint.check_paper_structure(text, fm))
        self.assertEqual([], lint.check_paper_quality(text, fm))

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

    def test_chinese_evidence_vocabulary_counts(self):
        text = paper_text(
            experiments="- 在 129 个合成任务上，成功率为 **63.57%**，比 LLM-SR 的 28.16% 更高（表 1）。"
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("experiment result lacks required evidence fields", lint.check_paper_quality(text, fm))

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
        ).replace("图 6 / §6.2", "main experiment").replace("表 2", "secondary experiment")
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("complete page has no evidence locator", lint.check_paper_quality(text, fm))

    def test_claim_evidence_map_requires_two_to_five_rows(self):
        text = paper_text().replace(
            "| 吞吐有所提高 | 图 6 / §6.2 | A100、OPT-13B、ShareGPT | 强 |",
            "| 论断一 | 图 6 / §6.2 | A100 | 强 |\n"
            "| 论断二 | 表 2 | ShareGPT | 中 |\n"
            "| 论断三 | §7.1 | OPT-13B | 弱 |\n"
            "| 论断四 | 图 8 | A100 | 强 |\n"
            "| 论断五 | 表 4 | ShareGPT | 中 |\n"
            "| 论断六 | §8 | OPT-13B | 弱 |",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn("Claim–Evidence Map must contain 2-5 claims", lint.check_paper_quality(text, fm))

    def test_claim_evidence_map_accepts_five_columns_and_escaped_wikilinks(self):
        text = paper_text().replace(
            "| 论断 | 证据 | 评测边界 | 置信度 |\n"
            "|---|---|---|---|\n"
            "| 吞吐有所提高 | 图 6 / §6.2 | A100、OPT-13B、ShareGPT | 强 |\n"
            "| 尾延迟仍受控制 | 表 2 | A100、ShareGPT | 中 |",
            "| 论断 | 证据 | 评测边界 | 定位 | 置信度 |\n"
            "|---|---|---|---|---|\n"
            "| 吞吐有所提高 | 图 6 / §6.2 | [[vLLM\\|vLLM]]、A100 | §6.2 | 强 |\n"
            "| 尾延迟仍受控制 | 表 2 | A100、ShareGPT | 表 2 | 中 |",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("malformed Claim–Evidence Map", lint.check_paper_quality(text, fm))

    def test_claim_evidence_map_rejects_inconsistent_columns(self):
        text = paper_text().replace(
            "| 尾延迟仍受控制 | 表 2 | A100、ShareGPT | 中 |",
            "| 尾延迟仍受控制 | 表 2 | A100、ShareGPT |",
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
        text = text.replace("## 论断—证据表", "## 摘要证据")
        fm, _ = lint.parse_frontmatter(text)
        self.assertNotIn("experiment result lacks required evidence fields", lint.check_paper_quality(text, fm))

    def test_paper_quality_is_actionable(self):
        self.assertTrue(lint.has_actionable_issues({"paper_quality": 1}))


class LanguageTests(unittest.TestCase):
    def chinese_paper(self):
        return paper_text().replace(
            "# Example\n",
            "# Example：按需容器分区（OSDI 2025）\n\n> **原题**：Example Paper\n",
        )

    def test_chinese_h1_and_matching_original_title_pass(self):
        text = self.chinese_paper()
        fm, _ = lint.parse_frontmatter(text)
        self.assertEqual([], lint.check_language(text, fm, page_type="paper"))

    def test_paper_requires_chinese_h1_and_original_title(self):
        text = paper_text()
        fm, _ = lint.parse_frontmatter(text)
        warnings = lint.check_language(text, fm, page_type="paper")
        self.assertIn("paper H1 must contain Chinese", warnings)
        self.assertIn("paper original-title line missing or mismatched", warnings)

    def test_original_title_must_immediately_follow_h1(self):
        text = self.chinese_paper().replace(
            "# Example：按需容器分区（OSDI 2025）\n\n> **原题**：Example Paper",
            "# Example：按需容器分区（OSDI 2025）\n\n先插入其他正文。\n\n> **原题**：Example Paper",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn(
            "paper original-title line missing or mismatched",
            lint.check_language(text, fm, page_type="paper"),
        )

    def test_legacy_headings_and_english_evidence_header_are_rejected(self):
        text = self.chinese_paper().replace("## 批判性分析", "## Critical Analysis")
        text = text.replace("## 局限与后续工作", "## 局限与 Future Work")
        text = text.replace("## 论断—证据表", "## Claim–Evidence Map")
        text = text.replace(
            "| 论断 | 证据 | 评测边界 | 置信度 |",
            "| Claim | Evidence | Evaluation boundary | Confidence |",
        )
        fm, _ = lint.parse_frontmatter(text)
        warnings = lint.check_language(text, fm, page_type="paper")
        self.assertTrue(any("legacy heading" in warning for warning in warnings))
        self.assertIn("paper evidence table header must be Chinese", warnings)

    def test_long_english_narrative_is_rejected(self):
        text = self.chinese_paper().replace(
            "Problem.",
            "This paragraph explains the complete system design using ordinary English prose and should be translated into Chinese.",
        )
        fm, _ = lint.parse_frontmatter(text)
        warnings = lint.check_language(text, fm, page_type="paper")
        self.assertTrue(any("English narrative" in warning for warning in warnings))

    def test_frontmatter_original_title_code_math_url_and_names_are_exempt(self):
        text = self.chinese_paper().replace(
            "Method with [[ExampleConcept]].",
            "方法调用 CUDA Graph、HTTP API 和 GPT-4o。\n\n"
            "```python\nresult = client.responses.create(model='gpt-4o')\n```\n\n"
            "$$ throughput = tokens / second $$\n\n"
            "资料：https://example.com/a-long-english-url-path",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertEqual([], lint.check_language(text, fm, page_type="paper"))

    def test_proper_name_lists_and_vs_headings_are_exempt(self):
        text = self.chinese_paper().replace(
            "Method with [[ExampleConcept]].",
            "## 4.2 vs Libra（ICLR 2026）\n\n"
            "- **对比方法**：DenseFormer、mHC、Hyper-Connections、Highway Networks、"
            "DeepNorm、SiameseNorm、MRLA、Sliding-Window Aggregation",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertEqual([], lint.check_language(text, fm, page_type="paper"))

    def test_chinese_sentence_with_many_technical_names_is_exempt(self):
        text = self.chinese_paper().replace(
            "Method with [[ExampleConcept]].",
            "DGL 的 eShuffle+SpMMve 比 cuSPARSE-native SpMMveT 慢 1.64x；"
            "GraphPy 对比 TC-GNN、FeatGraph、cuSPARSE、Huang et al. 分别更快。",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertEqual([], lint.check_language(text, fm, page_type="paper"))

    def test_descriptive_non_paper_h1_must_be_chinese(self):
        text = "---\ntype: theme\n---\n\n# Future Storage Systems\n\n中文正文。\n"
        fm, _ = lint.parse_frontmatter(text)
        self.assertIn(
            "descriptive H1 must contain Chinese",
            lint.check_language(text, fm, page_type="theme"),
        )

    def test_non_paper_section_and_table_headers_must_be_chinese(self):
        text = (
            "---\ntype: concept\n---\n\n# CUDA Graph\n\n"
            "## Design Tradeoffs\n\n"
            "| System | Main mechanism | Evaluation boundary |\n"
            "|---|---|---|\n"
            "| CUDA Graph | capture | H100 |\n"
        )
        fm, _ = lint.parse_frontmatter(text)
        warnings = lint.check_language(text, fm, page_type="concept")
        self.assertTrue(any("English section heading" in warning for warning in warnings))
        self.assertTrue(any("English table header" in warning for warning in warnings))

    def test_table_data_cells_are_not_treated_as_narrative(self):
        text = self.chinese_paper().replace(
            "| 吞吐有所提高 | 图 6 / §6.2 | A100、OPT-13B、ShareGPT | 强 |",
            "| Throughput improves against the production baseline in this exact measured configuration. | Fig. 6 / §6.2 | A100 | strong |",
        )
        fm, _ = lint.parse_frontmatter(text)
        self.assertEqual([], lint.check_language(text, fm, page_type="paper"))

    def test_language_warnings_are_actionable(self):
        self.assertTrue(lint.has_actionable_issues({"language_warnings": 1}))

    def test_language_paths_exclude_reports_and_accept_explicit_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            (wiki / "papers").mkdir(parents=True)
            (wiki / "reports").mkdir()
            paper = wiki / "papers" / "A.md"
            report = wiki / "reports" / "R.md"
            log = wiki / "log.md"
            paper.write_text("# A\n", encoding="utf-8")
            report.write_text("# R\n", encoding="utf-8")
            log.write_text("# Log\n", encoding="utf-8")
            self.assertEqual([paper], lint.language_paths([], wiki=wiki, root=Path(tmp)))
            self.assertEqual([paper], lint.language_paths([paper], wiki=wiki, root=Path(tmp)))


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


class ThemePolicyTests(unittest.TestCase):
    def theme_text(self, *, count=2, kind="area", member_tag="area/example"):
        return f'''---
type: theme
topic: Example
theme_kind: {kind}
member_tag: {member_tag}
paper_count: {count}
first_generated: 2026-08-18
last_updated: 2026-08-18
tags: [topic-overview]
---

# 示例主题综述

## 核心论文

- [[Alpha-OSDI25\\|Alpha]] 与 [[Beta-SOSP25|Beta]]
- [[Alpha-OSDI25]] 重复引用

## 邻接资料

- [[Gamma-MLSys26]] 不计入核心集合
'''

    def paper_meta(self, *tags):
        return {"tags": "[" + ", ".join(tags) + "]"}

    def test_core_members_are_unique_and_adjacent_links_are_ignored(self):
        result = lint.extract_theme_members(
            self.theme_text(), {"Alpha-OSDI25", "Beta-SOSP25", "Gamma-MLSys26"}
        )
        self.assertEqual(["Alpha-OSDI25", "Beta-SOSP25"], result["members"])
        self.assertEqual(["Alpha-OSDI25"], result["duplicates"])
        self.assertEqual([], result["unresolved"])

    def test_missing_core_heading_is_reported(self):
        result = lint.extract_theme_members(
            self.theme_text().replace("## 核心论文", "## 论文列表"),
            {"Alpha-OSDI25", "Beta-SOSP25", "Gamma-MLSys26"},
        )
        self.assertFalse(result["has_core_section"])
        self.assertEqual([], result["members"])

    def test_unresolved_core_wikilink_is_reported(self):
        text = self.theme_text().replace(
            "[[Beta-SOSP25|Beta]]", "[[Missing-SOSP25|Missing]]"
        )
        result = lint.extract_theme_members(text, {"Alpha-OSDI25"})
        self.assertEqual(["Missing-SOSP25"], result["unresolved"])

    def test_theme_schema_count_index_and_member_tags_are_checked(self):
        analysis = lint.analyze_theme(
            "Example",
            self.theme_text(count=3),
            index_text="- [[Example]] — 4 篇 | 示例\n",
            paper_frontmatters={
                "Alpha-OSDI25": self.paper_meta("systems", "area/example"),
                "Beta-SOSP25": self.paper_meta("systems"),
                "Tagged-FAST25": self.paper_meta("area/example"),
            },
        )
        self.assertIn("duplicate core member: Alpha-OSDI25", analysis["warnings"])
        self.assertIn("paper_count 3 != core member count 2", analysis["warnings"])
        self.assertIn("index count 4 != core member count 2", analysis["warnings"])
        self.assertIn("member missing tag: Beta-SOSP25 -> area/example", analysis["warnings"])
        self.assertEqual(["Tagged-FAST25"], analysis["candidates"])

    def test_theme_kind_and_member_tag_are_validated(self):
        analysis = lint.analyze_theme(
            "Example",
            self.theme_text(kind="tree", member_tag="topic/example"),
            index_text="- [[Example]] — 2 篇 | 示例\n",
            paper_frontmatters={
                "Alpha-OSDI25": self.paper_meta("topic/example"),
                "Beta-SOSP25": self.paper_meta("topic/example"),
            },
        )
        self.assertIn("invalid theme_kind: tree", analysis["warnings"])
        self.assertIn("invalid member_tag: topic/example", analysis["warnings"])

    def test_overlapping_membership_is_not_a_theme_error(self):
        first = lint.analyze_theme(
            "Example",
            self.theme_text(),
            index_text="- [[Example]] — 2 篇 | 示例\n",
            paper_frontmatters={
                "Alpha-OSDI25": self.paper_meta("area/example", "concern/other"),
                "Beta-SOSP25": self.paper_meta("area/example"),
            },
        )
        self.assertFalse(any("multiple" in warning for warning in first["warnings"]))

    def test_candidate_tags_recall_nonmembers_without_enrolling_them(self):
        text = self.theme_text().replace(
            "member_tag: area/example",
            "member_tag: area/example\ncandidate_tags: [long-horizon, long-horizon-agent]",
        )
        analysis = lint.analyze_theme(
            "Example",
            text,
            index_text="- [[Example]] — 2 篇 | 示例\n",
            paper_frontmatters={
                "Alpha-OSDI25": self.paper_meta("area/example"),
                "Beta-SOSP25": self.paper_meta("area/example"),
                "Candidate-FAST25": self.paper_meta("long-horizon-agent"),
            },
        )
        self.assertEqual(["Candidate-FAST25"], analysis["candidates"])
        self.assertNotIn("Candidate-FAST25", analysis["members"])

    def test_unowned_reserved_facet_tags_are_reported(self):
        warnings = lint.find_unowned_reserved_facet_tags(
            {
                "Alpha-OSDI25": self.paper_meta("systems", "area/example"),
                "Beta-SOSP25": self.paper_meta("concern/retired-theme"),
                "Gamma-MLSys26": self.paper_meta("long-horizon"),
            },
            owned_member_tags={"area/example"},
        )
        self.assertEqual(
            {"Beta-SOSP25": ["reserved facet tag has no owning theme: concern/retired-theme"]},
            warnings,
        )

    def test_safe_sync_appends_tag_and_updates_counts(self):
        papers = {
            "Alpha-OSDI25": "---\ntype: paper\ntags: [systems, area/example]\nlast_reviewed: 2026-08-01\n---\n",
            "Beta-SOSP25": "---\ntype: paper\ntags: [systems]\nlast_reviewed: 2026-08-01\n---\n",
        }
        theme, index, updated_papers = lint.sync_theme_metadata(
            "Example",
            self.theme_text(count=3).replace("- [[Alpha-OSDI25]] 重复引用\n", ""),
            "- [[Example]] — 4 篇 | 示例\n",
            papers,
        )
        self.assertIn("paper_count: 2", theme)
        self.assertIn("[[Example]] — 2 篇", index)
        self.assertIn("tags: [systems, area/example]", updated_papers["Beta-SOSP25"])
        self.assertNotIn("last_updated:", updated_papers["Beta-SOSP25"])
        self.assertEqual(papers["Alpha-OSDI25"], updated_papers["Alpha-OSDI25"])

    def test_safe_sync_skips_ambiguous_or_invalid_themes(self):
        papers = {
            "Alpha-OSDI25": "---\ntype: paper\ntags: [systems]\nlast_reviewed: 2026-08-01\n---\n",
            "Beta-SOSP25": "---\ntype: paper\ntags: [systems]\nlast_reviewed: 2026-08-01\n---\n",
        }
        duplicate_theme = self.theme_text(count=3)
        invalid_tag_theme = self.theme_text(count=3, member_tag="topic/example").replace(
            "- [[Alpha-OSDI25]] 重复引用\n", ""
        )
        invalid_kind_theme = self.theme_text(count=3, kind="tree").replace(
            "- [[Alpha-OSDI25]] 重复引用\n", ""
        )
        for theme_text in (duplicate_theme, invalid_tag_theme, invalid_kind_theme):
            synced = lint.sync_theme_metadata(
                "Example", theme_text, "- [[Example]] — 4 篇 | 示例\n", papers
            )
            self.assertEqual((theme_text, "- [[Example]] — 4 篇 | 示例\n", papers), synced)

    def test_generic_fix_does_not_add_last_updated_to_papers(self):
        text = "---\ntype: paper\ntags: [systems]\nlast_reviewed: 2026-08-01\n---\n"
        self.assertEqual(text, lint.add_missing_last_updated(text, today="2026-08-18"))


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
