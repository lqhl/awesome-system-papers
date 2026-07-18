import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("linker.py")
SPEC = importlib.util.spec_from_file_location("wiki_linker", MODULE_PATH)
linker = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(linker)


class LinkerTests(unittest.TestCase):
    def test_parses_unquoted_frontmatter_aliases(self):
        self.assertEqual(
            ["KV cache", "KV Cache", "kv-cache"],
            linker.parse_aliases("aliases: [KV cache, KV Cache, kv-cache]"),
        )

    def test_links_special_character_alias(self):
        text = "---\ntype: paper\n---\n\n## 核心方法\n\nC++ runtime uses KV cache.\n"
        updated, changes = linker.link_text(text, {"C++": "Cpp", "KV cache": "KV-Cache"})
        self.assertIn("[[Cpp|C++]]", updated)
        self.assertIn("[[KV-Cache|KV cache]]", updated)
        self.assertEqual(2, len(changes))

    def test_skips_frontmatter_code_and_existing_links(self):
        text = '''---
aliases: [KV cache]
---

`KV cache`

```
KV cache
```

[[KV-Cache|KV cache]] is linked; KV cache appears again.
'''
        updated, changes = linker.link_text(text, {"KV cache": "KV-Cache"})
        self.assertEqual(text, updated)
        self.assertEqual([], changes)

    def test_prefers_high_value_section(self):
        text = '''---
type: paper
---

## 问题与动机

KV cache appears here.

## Critical Analysis

KV cache is fragile here.
'''
        updated, _ = linker.link_text(text, {"KV cache": "KV-Cache"})
        self.assertIn("KV cache appears here", updated)
        self.assertIn("[[KV-Cache|KV cache]] is fragile here", updated)

    def test_does_not_match_inside_longer_identifier(self):
        text = "## 核心方法\n\nMoE and MoEGL are different.\n"
        updated, _ = linker.link_text(text, {"MoE": "MoE"})
        self.assertIn("[[MoE|MoE]] and MoEGL", updated)


if __name__ == "__main__":
    unittest.main()
