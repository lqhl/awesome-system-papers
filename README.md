# awesome-system-papers

系统领域顶会论文收藏 + MinerU 解析 + Agent 维护的跨论文 wiki。Clone 后即可交给 coding agent 阅读、综合、扩展。

**[GitHub](https://github.com/lqhl/awesome-system-papers)** · **[在线 Wiki](https://papers.lqhl.me)** · **[Wiki 目录](wiki/index.md)**

---

## 为什么需要 MinerU 层

Coding agent（Claude Code、Codex、Pi、Grok Build 等）默认用视觉方式读 PDF——把每页渲染成图像交给多模态模型，而不是抽取文本层。一篇 20 页的 OSDI 论文直接 Read，往往消耗数万 token，公式和小数点还容易识别错。

本仓库的核心工程决策是：**PDF 不直接给 agent 读，先过 MinerU 转成 `markdowns/`**。

| 方式 | token 开销 | 文本精度 | 适用场景 |
|------|-----------|---------|---------|
| Agent 直接 Read PDF | ~1500–3000 / 页 | 依赖视觉识别，公式/数字易错 | 快速看图、核对个别细节 |
| 读 MinerU 产出的 `.md` | 同篇论文约降一个数量级 | 正文 95%+ 精确（LaTeX 矢量 PDF） | 批量阅读、写 wiki、做综合 |

仓库已批量解析 900+ 篇论文到 `markdowns/`。新增论文跑：

```bash
uv run scripts/run_mineru.py papers/osdi-2025 markdowns/osdi-2025 -j 2 -m txt
```

LaTeX 矢量 PDF（OSDI / SOSP / MLSys 等）推荐 `-m txt`，比 OCR 更快更准。细节见 [AGENTS.md](AGENTS.md#pdf--markdown-解析)。

---

## Agent-ready：Clone 即开即用

本 repo 不只是论文列表，而是一套 **agent 可维护的知识库**：

- **[AGENTS.md](AGENTS.md)** — 仓库约定：目录结构、命名规范、wikilink 规则、工具链说明
- **[`.claude/skills/`](.claude/skills/)** — 可复用的维护流水线：

| Skill | 用途 |
|-------|------|
| `wiki-paper` | 读单篇论文，生成含 Critical Analysis 的 wiki 页 |
| `wiki-update` | 新 paper 页写入后，更新概念/实体反向链接 |
| `wiki-survey` | 聚合会议或 topic 目录，写综述页 |
| `wiki-query` | 在 wiki 图谱中回答自然语言问题 |
| `wiki-lint` | 健康检查：断链、orphan、frontmatter |
| `probe` / `proposal` | 研究 idea 的 landscape 调研与提案 |

把 repo clone 到本地，在 agent 会话里直接说：

```
/wiki-paper papers/osdi-2025/osdi25-gao.pdf
/wiki-query KV cache 在 MLSys 2026 的趋势是什么？
/wiki-survey mlsys-2026
```

Agent 会自动加载 `AGENTS.md` 和 skills，按同一套约定维护 wiki。**Fork 后改主题、加论文、换综述角度，agent 都能接着干**——不需要你重新写 prompt 工程。

---

## 三层架构

```
papers/  ──MinerU──▶  markdowns/  ──Agent+skills──▶  wiki/  ──Quartz──▶  在线站点
  PDF                  md + 图片                    综合层
```

| 层 | 角色 | 谁写 | 可变 |
|---|---|---|---|
| `papers/` | 论文 PDF（raw） | 下载脚本 / 用户 | 不可变 |
| `markdowns/` | MinerU 解析的 markdown + 图片 | `scripts/run_mineru.py` | 不可变（除非重跑） |
| `wiki/` | 跨论文综合：paper 页、概念、实体、会议综述、主题 | Agent + skills | 可演化 |

`wiki/` 是唯一的 LLM 生成层。每篇 paper wiki 含**关键观察 / 隐含假设 / Critical Analysis**，不是摘要复读。深度细节回 `markdowns/` 或原 PDF。

---

## 内容规模

| 类别 | 数量 |
|------|------|
| 论文 PDF | 968 |
| Paper wiki 页 | 442 |
| 会议综述 | 5（OSDI-2025、SOSP-2025、ATC-2025、MLSys-2026、FAST-2026） |
| 概念页 | 26（KV-Cache、MoE、Disaggregation、PagedAttention …） |
| 实体页 | 8（vLLM、SGLang、DeepSpeed、Mooncake …） |
| 主题综述 | 4（AI-Infra、Foundation、Auto-Research、Finance） |

### 已覆盖会议

| 会议 | 年份 |
|------|------|
| OSDI | 2024, 2025 |
| ATC | 2024, 2025 |
| NSDI | 2024, 2025 |
| SOSP | 2024, 2025 |
| MLSys | 2024, 2025, 2026 |
| FAST | 2024, 2025, 2026 |

另有 topic 目录：`ai-infra`、`foundation`、`autoresearch`、`finance` 等。

---

## 本地预览与自托管

Wiki 通过 [Quartz v4](https://quartz.jzhao.xyz/) 发布为静态站点，不绑定特定托管商：

```bash
git clone https://github.com/lqhl/awesome-system-papers.git
cd awesome-system-papers/quartz
npm install
npx quartz build --serve -d ../wiki    # 默认 http://localhost:8080
```

Fork 后改 `wiki/` 内容，本地 build 即可预览自己的版本。Cloudflare Pages 部署配置见 [AGENTS.md](AGENTS.md#公开发布quartz--cloudflare-pages)。

---

## 工具链

```bash
# 下载 USENIX 论文（OSDI / ATC / NSDI / FAST）
uv run scripts/download_usenix_papers.py osdi 2025 papers/osdi-2025

# 下载 MLSys 论文
uv run scripts/download_mlsys_papers.py 2026

# 下载 SOSP 论文
uv run scripts/download_sosp_papers.py 2025

# PDF → Markdown（MinerU）
uv run scripts/run_mineru.py papers/osdi-2025 markdowns/osdi-2025 -j 2 -m txt
```

Python 依赖用 [uv](https://docs.astral.sh/uv/) 管理。命名规范、wikilink 规则、Mac 上 MinerU 注意事项等完整约定见 [AGENTS.md](AGENTS.md)。

---

## 目录结构

```
awesome-system-papers/
├── papers/               # 论文 PDF (raw, immutable)
├── markdowns/            # MinerU 解析的 markdown + 图片 (raw, immutable)
├── wiki/                 # LLM 综合层 (evolvable)
│   ├── index.md          # 内容目录
│   ├── papers/           # 每篇论文一页
│   ├── conferences/      # 会议综述
│   ├── entities/         # 系统/组织/benchmark
│   ├── concepts/         # 跨论文技术/机制
│   ├── themes/           # 跨论文趋势
│   └── proposals/        # 研究提案 + probe
├── scripts/              # 下载 + MinerU 解析脚本
├── .claude/skills/       # Agent 维护流水线
├── AGENTS.md             # Agent 约定（→ CLAUDE.md）
└── quartz/               # 静态站点构建
```

---

## 参与

- **Star / Issue** — 反馈缺失论文、wiki 错误或改进建议
- **PR** — 欢迎脚本改进、wiki 修正、新 topic 扩展
- 深度维护约定和 skill 用法见 [AGENTS.md](AGENTS.md)

---

## 免责声明

论文 PDF 版权归各会议/出版社所有，本仓库仅供学习研究使用，请遵守相应使用条款。下载和使用时请自行判断合规性。