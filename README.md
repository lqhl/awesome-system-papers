# awesome-system-papers

个人学术论文收藏库。下载系统领域顶级会议的论文 PDF，并以 LLM 维护的 wiki 形式做跨论文综合，供学习研究使用。

## 三层架构

| 层 | 角色 | 说明 |
|---|---|---|
| `papers/` | 论文 PDF | raw layer，按会议-年份或 topic 分目录 |
| `markdowns/` | mineru 解析的 markdown + 图片 | LLM 读论文的低成本入口 |
| `wiki/` | 跨论文综合 | 唯一的 LLM 生成层：论文摘要、概念、实体、比较、趋势 |

## 内容

- **论文 PDF**：按 topic 或会议-年份目录存放于 `papers/` 下
- **Wiki**：在 `wiki/` 下维护
  - `wiki/papers/`：每篇论文一页简要 wiki（用系统名/方法名命名，如 `vLLM-SOSP23.md`）
  - `wiki/conferences/`：会议综述
  - `wiki/entities/`：系统/组织/benchmark 长期演化追踪
  - `wiki/concepts/`：跨论文技术/机制
  - `wiki/comparisons/`：系统/方法对比
  - `wiki/themes/`：跨论文趋势 + 个人观点
- **自动化脚本**：`scripts/` 下，从各会议官网下载 PDF；mineru 把 PDF 转 markdown
- **Claude Code skills**：`.claude/skills/wiki-*` 维护 wiki

## 目录结构

```
awesome-system-papers/
├── papers/               # 论文 PDF (raw)
│   ├── ai-infra/        # AI 系统基础设施
│   ├── foundation/      # 开创性工作
│   ├── agent/           # Agent
│   ├── ai4s/            # AI for Science
│   ├── finance/         # 金融
│   ├── time-series/     # 时间序列
│   ├── osdi-2024/       # 会议论文
│   ├── osdi-2025/
│   ├── ...              # ATC / NSDI / SOSP / MLSys / FAST 各年
├── markdowns/            # mineru 解析的 markdown (raw)
├── wiki/                 # LLM 综合层
│   ├── index.md
│   ├── log.md
│   ├── papers/
│   ├── conferences/
│   ├── entities/
│   ├── concepts/
│   ├── comparisons/
│   └── themes/
├── scripts/              # 下载 + 解析脚本
└── inbox/                # 临时收件箱（gitignored）
```

## 已覆盖的会议

| 会议 | 年份 |
|------|------|
| OSDI | 2024, 2025 |
| ATC | 2024, 2025 |
| NSDI | 2024, 2025 |
| SOSP | 2024, 2025 |
| MLSys | 2024, 2025, 2026 |
| FAST | 2024, 2025, 2026 |

> 论文仅供个人学习研究使用，请遵守各会议/出版社的使用条款。
