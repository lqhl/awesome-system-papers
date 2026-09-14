import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("repair_manifest.py")
SPEC = importlib.util.spec_from_file_location("repair_manifest", MODULE_PATH)
manifest = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(manifest)


def page(*, authors="[Alice Smith]", experiment=None, locator=True, filler="x" * 4500, empirical=None):
    experiment = experiment or "- 吞吐比 Baseline 高 2.2×，A100/ShareGPT（Fig. 6）。"
    loc = "§3.2" if locator else "measurement"
    return f'''---
type: paper
name: Example
authors: {authors}
source_pdf: "[[example.pdf]]"
source_md: "[[example]]"
{f'empirical_evidence: {empirical}' if empirical else ''}
---
## 问题与动机
{filler}
## 关键观察 / 隐含假设
- 观察来自 {loc}。
## 核心方法
Method.
## 实验与结果
{experiment}
## 批判性分析
### 论证链条
Closed.
### 假设压力测试
Bounded.
### 实验可信度
Credible.
## 局限与后续工作
- measurable.
'''


class ClassificationTests(unittest.TestCase):
    def test_placeholder_author_is_invalid(self):
        result = manifest.classify_page(page(authors="[Matrix authors]"), source_ok=True)
        self.assertEqual("invalid", result["recommended_status"])

    def test_unresolved_short_page_is_abstract_only(self):
        text = page(experiment="- 具体倍数见原文。", filler="short")
        result = manifest.classify_page(text, source_ok=True)
        self.assertEqual("abstract-only", result["recommended_status"])

    def test_missing_locator_is_needs_review(self):
        result = manifest.classify_page(
            page(
                locator=False,
                experiment="- 吞吐比 Baseline 高 2.2×，A100/ShareGPT。",
            ),
            source_ok=True,
        )
        self.assertEqual("needs-review", result["recommended_status"])

    def test_strong_existing_note_is_complete_candidate(self):
        result = manifest.classify_page(page(), source_ok=True)
        self.assertEqual("complete", result["recommended_status"])
        self.assertIn("add-quality-frontmatter", result["repair_actions"])
        self.assertIn("build-claim-evidence-map", result["repair_actions"])

    def test_chinese_claim_evidence_map_is_recognized(self):
        text = page() + """
## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 吞吐提高 | 图 6 | A100、ShareGPT | 强 |
| 尾延迟受控 | 表 2 | A100、ShareGPT | 中 |
"""
        result = manifest.classify_page(text, source_ok=True)
        self.assertNotIn("build-claim-evidence-map", result["repair_actions"])

    def test_legacy_claim_evidence_map_is_recognized(self):
        text = page() + """
## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Throughput improves | Fig. 6 | A100, ShareGPT | strong |
| Tail latency remains bounded | Table 2 | A100, ShareGPT | medium |
"""
        result = manifest.classify_page(text, source_ok=True)
        self.assertNotIn("build-claim-evidence-map", result["repair_actions"])

    def test_descriptive_work_with_no_empirical_evidence_is_complete_candidate(self):
        result = manifest.classify_page(
            page(experiment="- 原文明确没有数值实验。", empirical="none"),
            source_ok=True,
        )
        self.assertEqual("complete", result["recommended_status"])

    def test_missing_source_is_invalid(self):
        result = manifest.classify_page(page(), source_ok=False)
        self.assertEqual("invalid", result["recommended_status"])


if __name__ == "__main__":
    unittest.main()
