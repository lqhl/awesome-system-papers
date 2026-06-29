# awesome-system-papers

个人学术论文收藏库，整理和下载系统领域顶级会议的论文 PDF，并以 LLM 维护的 wiki 形式做跨论文综合，供学习研究使用。

---

## 仓库结构

```
awesome-system-papers/
├── papers/               # 论文 PDF (raw, immutable)
│   ├── ai-infra/        # AI 系统基础设施：训练/推理系统、显存/内存优化、分布式
│   ├── foundation/      # 开创性/里程碑工作
│   ├── agent/           # Agent：规划、记忆、RAG、多智能体
│   ├── ai4s/            # AI for Science / AI for AI：自动化研究、架构搜索
│   ├── finance/         # 金融领域应用
│   ├── time-series/     # 时间序列预测、量化因子
│   ├── osdi-2024/       # 会议论文 PDF（OSDI / ATC / NSDI / SOSP / MLSys / FAST）
│   ├── osdi-2025/
│   ├── atc-2024/
│   ├── atc-2025/
│   ├── nsdi-2024/
│   ├── nsdi-2025/
│   ├── sosp-2024/
│   ├── sosp-2025/
│   ├── mlsys-2024/
│   ├── mlsys-2025/
│   ├── mlsys-2026/
│   ├── fast-2024/
│   ├── fast-2025/
│   └── fast-2026/
├── markdowns/            # mineru 解析出的论文 Markdown + 图片 (raw, immutable)
├── wiki/                 # LLM 综合层：唯一的 LLM 生成层
│   ├── index.md
│   ├── log.md
│   ├── papers/           # 每篇论文一个简要 wiki 页（系统名/方法名命名）
│   ├── conferences/      # 会议综述（OSDI-2025.md 等）
│   ├── entities/         # 长期演化的系统/组织/benchmark
│   ├── concepts/         # 跨论文的技术/机制
│   ├── comparisons/      # 系统/方法对比页
│   ├── themes/           # 跨论文趋势 + 个人观点
│   └── proposals/        # 研究 idea 的提案 + probe（/proposal + /probe skill 生成）
│       ├── {Slug}.md     # Proposal 文档
│       ├── probes/       # 深度 landscape characterization（/probe 产物）
│       └── _log.md       # Proposal 层时间线（独立于 wiki/log.md，不发布）
├── scripts/              # 论文下载 + 解析脚本
├── inbox/                # 临时收件箱，新论文先放这里再分类（gitignored）
├── progress.md           # 下载进度记录
└── .venv/                # Python 虚拟环境
```

### 三层架构

| 层 | 角色 | 谁写 | 是否可变 |
|---|---|---|---|
| `papers/` | 论文 PDF | 下载脚本 / 用户 | 不可变 |
| `markdowns/` | mineru 解析的 markdown + 图片 | mineru 脚本 | 不可变（除非重跑 mineru） |
| `wiki/` | 跨论文综合（论文摘要、概念、实体、比较、主题） | LLM（wiki-* skills） | 可演化 |
| `wiki/proposals/` | 研究 idea 的提案 + 前置 probe（调研 → taste 评估 → 迭代 → 规划） | LLM（probe + proposal skills） | 可演化 |

**Wiki 是唯一的综合层**；`wiki/proposals/` 是面向未来的研究计划层，引用 wiki 但不被 wiki 反向引用（单向）。Proposals 随 wiki 发布到网站，probes 作为前置研究笔记一同发布。深度细节回 markdowns/PDF。

---

## 论文命名规范

| 类型 | 命名规则 | 示例 |
|------|---------|------|
| 会议目录 (USENIX) | `{conf}{year}-{lastname}[-{extra}].pdf` | `osdi25-zhang-tony.pdf`, `nsdi2024-agarwal-shubham.pdf`, `fast2025-brunmayr.pdf` |
| 会议目录 (MLSys) | `{hash}.pdf`（原始下载文件名） | `0badcb4e95306df76a719409155e46e8.pdf` |
| 会议目录 (SOSP) | `{proceeding_doi}.{article_doi}.pdf` | `3731569.3764795.pdf` |
| Topic 目录 | `{prefix}{year}-{firstauthor}-{keyword}.pdf`（见 [Topic 命名规则](#topic-命名规则)） | `sosp23-kwon-pagedattention.pdf`, `arxiv24-liu-flexgen.pdf` |

- 当同一作者有多篇论文时，用 `-{extra}` 区分（如 `nsdi2024-namyar-finding.pdf` vs `nsdi2024-namyar-solving.pdf`）
- 不要随意重命名 PDF 文件，以免破坏与外部数据源的对应关系

PDF 文件名是 raw layer 的标识符；wiki paper 页另用「系统名/方法名」命名（见「Wiki 命名规则」节），通过 frontmatter `source_pdf` 字段双向链接。

---

## 读取 PDF

Claude Code 的 `Read` 工具对 PDF 的处理是**把每页渲染成图像**交给多模态模型看，不是抽文本层：

- 能看到图、表、公式的视觉形式，但文字精度取决于视觉识别
- 每页约 1500-3000 token，长论文（20+ 页）直接 Read 会吃掉大量上下文
- 适用场景：快速浏览、看图、核对细节

大批量或需要精确文本时，优先用 mineru 把 PDF 转成 Markdown（见「PDF → Markdown 解析」章节），再 Read 生成的 `.md` + 按需 Read 独立图片，token 开销小一个量级。

python 相关依赖用 uv 安装和使用。可以用 `uv pip list` 列出现有的 python 包。

---

## 下载脚本

所有脚本在 `scripts/` 目录下。我们用 uv 管理 python 依赖。

### USENIX 论文（OSDI / ATC / NSDI / FAST）

```bash
uv run scripts/download_usenix_papers.py <conference> <year> [output_dir]
```

- 自动从会议 technical sessions 页面抓取论文
- 验证 PDF 有效性、断点续传、礼貌延迟
- 示例：`uv run scripts/download_usenix_papers.py osdi 2025 papers/osdi-2025`

### MLSys 论文

```bash
uv run scripts/download_mlsys_papers.py <year>
```

- 支持代理（从环境变量 `http_proxy` / `https_proxy` 自动读取）
- 并行下载

### SOSP 论文

```bash
uv run scripts/download_sosp_papers.py <year>
```

- ACM Digital Library 有反爬措施，使用 browser-tools/Chrome 绕过

---

## PDF → Markdown 解析

用 [MinerU](https://github.com/opendatalab/MinerU) 把 PDF 解析成 Markdown + 图片，便于下游（LLM 阅读、wiki 生成）按需访问。

### 工具链

- **MinerU**：开源的 PDF 解析工具链，识别布局、公式（MFR 模型）、表格，抽取图片
- 安装：`uv tool install --python 3.12 --with socksio "mineru[pipeline,mlx]"`，得到全局 `mineru` 和 `mineru-api` 两个命令。`socksio` 用于避免 shell 里有 SOCKS 代理变量时 `httpx` 直接报错；`mlx` 是 Mac 本地后端依赖。
- **`scripts/run_mineru.py`**：包装脚本，处理批量 + 并发 + 后处理，启动常驻 mineru-api 复用模型加载

### 脚本用法

```bash
uv run scripts/run_mineru.py <input_dir> <output_dir> [-j N] [-m {auto,txt,ocr}]
```

- `<input_dir>`：含 PDF 的目录（非递归）
- `<output_dir>`：输出目录，每个 PDF 产出 `{stem}/{stem}.md` + `{stem}/images/`
- `-j`：客户端并发数，默认 2
- `-m`：正文抽取方式，默认 `auto`；LaTeX 矢量 PDF 推荐 `txt`，更快更精确

示例：

```bash
uv run scripts/run_mineru.py papers/osdi-2025 markdowns/osdi-2025 -j 2 -m txt
```

脚本特性：
- 跳过目标已存在 `{stem}.md` 的 PDF，支持断点续跑
- 每 20s 心跳显示进度、平均耗时、ETA
- 子进程日志写到 `{output_dir}/{stem}/mineru.log`，成功时自动删除，失败时保留以便排查
- mineru-api 日志写到 `{output_dir}/.mineru-api.log`，可 `tail -f` 看 mineru 单页进度

### 输出结构

```
markdowns/osdi-2025/osdi25-gao/
├── osdi25-gao.md           # 论文正文 markdown，图片引用为 ![](images/{hash}.jpg)
└── images/                 # 所有抽取的图片（figure/complex table/rendered formula）
    ├── f2eb...cb.jpg
    └── ...
```

### method 选择

| 模式 | 正文来源 | 适用场景 |
|------|----------|----------|
| `-m txt` | PDF text layer 直读 | **推荐给 LaTeX 矢量 PDF**，如 OSDI/SOSP/MLSys 论文。精确、快（比 OCR 省 30-60s/篇） |
| `-m auto`（默认） | 由 mineru classify 自动判断，文本 PDF 走 text layer，扫描件走 OCR | 不确定 PDF 类型时用 |
| `-m ocr` | 全页 OCR | 扫描件，或 `-m txt` 出现严重字符错位时 |

**图片/表格/公式的识别不受 `-m` 影响**，走独立的视觉模型（Layout + WirelessTable/WiredTable + MFR），表格内单元格文字有独立 OCR 路径。仓库脚本在 Mac 上默认关闭公式/表格重模型以提高稳定性；需要高保真公式/表格时显式传 `--formula --table`。

### Mac 注意事项

- **MinerU 上游在 Mac 上把 api 并发硬编码为 1**（`mineru/cli/fast_api.py:248`），`-j N` 仅让客户端并发排队，api 仍串行。想真正并行需要 Linux + GPU
- **`hybrid-auto-engine` 在 Mac 上不可用**：会触发 MLX 线程 bug（[ml-explore/mlx#3078](https://github.com/ml-explore/mlx/issues/3078)），脚本已硬编码 `--backend pipeline`
- **Mac/MPS 路径不稳定**：MinerU 3.1.x 在 macOS 上默认选 MPS 时可能卡在 `DocAnalysis init`；`scripts/run_mineru.py` 默认设置 `MINERU_DEVICE_MODE=cpu`。CPU 路径慢一些（14-16 页论文约 3 分钟），但稳定。
- **CPU 路径也可能在 layout 后挂住**：若 wrapper 心跳一直显示 `进度 0/1`，必须看 `{output_dir}/.mineru-api.log` 的内部阶段；若日志已到 `Layout Predict: 100%` 后长时间只剩 `/tasks/... status=processing` 且 CPU 低占用，可尝试直接运行原生 `mineru -p <pdf> -o <tmp> --backend pipeline --method txt --formula false --table false`（不强制 `MINERU_DEVICE_MODE=cpu`），成功后手动搬回 `{stem}.md + images/`。
- **模型下载可能改坏配置**：`mineru-models-download` 会重写 `~/mineru.json` 的 `models-dir.pipeline`。若日志报 `ch_PP-OCRv5_rec_infer.pth is not existed`，先检查 `~/.cache/huggingface/hub/models--opendatalab--PDF-Extract-Kit-1.0/snapshots/*/models/OCR/paddleocr_torch/`，把 `~/mineru.json` 指向包含 `ch_PP-OCRv5_rec_infer.pth` 的完整 snapshot，并确保运行时带 `MINERU_MODEL_SOURCE=local`。MinerU 3.1.x 默认仍会走 HuggingFace；网络慢时会在 `DocAnalysis init` 看似卡死。
- **VLM fallback 很慢**：若 pipeline 在 `DocAnalysis init` 卡死，可用临时环境 `mineru[pipeline] + accelerate`（不装 `mlx` extra）让 `vlm-auto-engine` 落到 `transformers`，再设 `MINERU_DEVICE_MODE=mps` 试跑；该路径能产出 MinerU Markdown，但全篇可能因为数百个 block 抽取耗时数小时，只适合验证或少量页，不适合作为常规 ingest 路径。
- **代理变量会影响本地 api client**：如果 shell 有 `ALL_PROXY=socks5://...` 但 mineru tool env 没装 `socksio`，会报 `Using SOCKS proxy, but the 'socksio' package is not installed`。脚本会为 mineru 子进程清理代理变量，并要求安装时带 `--with socksio`。
- **公式/表格重模型可能导致初始化卡住**：Mac 上开启 `--formula --table` 可能卡在模型初始化。默认关闭；确实需要公式/表格结构化输出时单独重跑该论文并加大 `--timeout`。
- 内存：单 worker 加载 OCR 模型约 2 GB，16 GB 机器最多 `-j 2`，跑 `-j 8` 必 OOM

### `-m txt` 的已知瑕疵（OSDI 论文实测）

- **小数点偶尔丢失**："1.61×" → "1 61×"（PDF text stream 字符间距问题）
- **希腊字符参数顺序错位**："A(v,k,λ)-SBIBD" → "A (v k )-SBIBD...,,λ,,λ"（LaTeX 数学符号 span 位置错乱）
- **稀疏 0/1 矩阵识别失败**：MFR 模型局限，变成空 `\begin{array}...\end{array}`

这些对下游阅读理解影响不大（95% 内容正确），需要精确引用公式/数字时 fall back 到原 PDF 核对。

---

## Topic 分类规范

论文 PDF 按主题放在 `papers/` 下，分类清晰、扁平，不嵌套：

| 目录 | 范围 | 示例 |
|------|------|------|
| `papers/foundation/` | 开创性/里程碑工作，为后续研究奠定基础 | Attention Is All You Need, Batch Normalization |
| `papers/ai-infra/` | AI 系统基础设施：训练/推理系统、显存管理、分布式训练、编译器 | vLLM, DeepSpeed, FlexAI |
| `papers/agent/` | Agent 相关：规划、记忆、RAG、多智能体、具身智能 | AutoGPT, ReAct, Reflexion |
| `papers/ai4s/` | AI for Science / AI for AI：用 AI 自动化科学研究、架构搜索、自动化实验 | ASI-ARCH, AlphaEvolve |
| `papers/finance/` | 金融领域垂直应用 | 时间序列预测、量化因子 |
| `papers/time-series/` | 时间序列方法 | TimesNet, PatchTST |

- 同一 topic 下论文多了，再按需拆分子目录

### Topic 命名规则

Topic 目录下的 PDF 统一用 `{prefix}{year}-{firstauthor}-{keyword}.pdf` 格式，与 wiki paper 页的「系统名/方法名」命名无关，仅作为 raw layer 的文件标识符。

```
{prefix}{year}-{firstauthor}-{keyword}.pdf
```

- **prefix**：按发表状态三选一

  | 发表状态 | prefix | 示例 |
  |----------|--------|------|
  | 已发表在会议/期刊 | `{conf}`（小写缩写） | `sosp`, `osdi`, `neurips`, `icml`, `fast` |
  | 未发表，在 arXiv 上 | `arxiv` | `arxiv` |
  | 未发表，也不在 arXiv | `techreport` | `techreport` |

- **year**：两位年份，如 `23`、`24`
- **firstauthor**：第一作者姓，全小写
- **keyword**：1-3 个标题关键词，kebab-case，小写，去停用词
- 冲突时加 `-{extra}`（额外关键词或 `abc` 字母后缀）

Topic 目录下的 PDF 文件名在**所有 topic 目录间全局唯一**，方便将来在目录间移动时不会冲突。不与会议目录的命名规则混用。

---

## Wiki 层

Wiki 是仓库的唯一 LLM 综合层。所有跨论文知识、论文摘要、概念解释、对比、趋势都住在 `wiki/` 下。

### 子目录与角色

| 子目录 | 角色 | 命名 | 示例 |
|---|---|---|---|
| `wiki/papers/` | 每篇论文一个简要页 | `{Name}-{Conf}{Year}.md` | `vLLM-SOSP23.md`、`NanoFlow-OSDI25.md` |
| `wiki/conferences/` | 会议综述 | `{Conf}-{Year}.md` | `OSDI-2025.md`、`MLSys-2026.md` |
| `wiki/entities/` | 长期演化的系统/组织/benchmark | PascalCase 或 kebab-case | `vLLM.md`、`SGLang.md`、`MLE-bench.md` |
| `wiki/concepts/` | 跨论文技术/机制 | PascalCase 或 kebab-case | `KV-Cache.md`、`PagedAttention.md`、`MoE.md` |
| `wiki/comparisons/` | 系统/方法对比 | `{A}-vs-{B}[-vs-{C}].md` | `vLLM-vs-SGLang.md` |
| `wiki/themes/` | 跨论文趋势 + 个人观点 | PascalCase 或 kebab-case | `From-Collective-To-P2P.md` |

`wiki/index.md` 是内容目录（按 type 分组），`wiki/log.md` 是时间线（append-only）。

### 命名规则

#### 全局

- **Obsidian wikilink 在 vault 内查找文件名，与子目录无关**——所以 `wiki/` 内文件名必须**全局唯一**
- PascalCase 或 kebab-case，**保持原名大小写**（`vLLM` 保留小写 v）
- 不用空格、特殊字符、中文

#### Paper 页（命名 fallback 顺序）

1. **优先：系统名/产品名** → `vLLM-SOSP23.md`、`NanoFlow-OSDI25.md`、`SGLang-OSDI25.md`
2. **次选：方法名/技术名** → `PagedAttention-SOSP23.md`、`FlashAttention-NeurIPS22.md`
3. **末选：作者姓-主题** → `Kwon-LLMServing-SOSP23.md`
4. **冲突时**：加 `-{FirstAuthorLastname}` 后缀

会议年份后缀两位：`OSDI25`、`SOSP25`、`MLSys26`、`arXiv25`。

#### Entity 页 vs Paper 页

`vLLM-SOSP23.md`（论文页）vs `vLLM.md`（实体页）天然不冲突：

- `[[vLLM]]` → 实体页（系统的演化追踪）
- `[[vLLM-SOSP23]]` → 论文页（具体某篇）

### Frontmatter 字段

| 类型 | 必填字段 |
|---|---|
| `paper` | `type, name, full_title, authors, venue, year, tags, source_pdf, source_md` |
| `conference` | `type, venue, year, paper_count, first_generated, last_updated` |
| `entity` | `type, kind, aliases, status, last_updated` |
| `concept` | `type, aliases, last_updated` |
| `comparison` | `type, subjects, last_updated` |
| `theme` | `type, last_updated, tags` |

`aliases` 字段对 `wiki-update` 至关重要——所有可能的术语变体都列出（如 `KV-Cache.md` 的 aliases 含 `KV cache`、`KV Cache`、`kv-cache`）。

**Frontmatter wikilink 必须 quote**：任何 frontmatter 字段里的 wikilink（`source_pdf`、`source_md`、`parent`、`introduced_by`、`subjects` 等）必须用双引号包裹成字符串：`parent: "[[KV-Cache]]"`、`subjects: ["[[vLLM]]", "[[SGLang]]"]`。否则 YAML 解析为嵌套数组而非 link，Obsidian properties 面板不可点击。

### Wikilink 规则

- 所有内部链接用 Obsidian wikilink `[[Page]]` 或 `[[Page|显示]]`，**不写路径，不带 .md 后缀**
- 链接 PDF 源文件保留 .pdf 后缀：`[[sosp2023-kwon.pdf]]`
- 表格内 `|` 必须转义：`[[Page\|显示]]`
- **Paper 页内首次提到已存在 entity/concept 时必须 wikilink**；重复出现可不再重复链接
- **不回填旧 paper 页**——历史不变，由 `wiki-update` 处理新 paper 页时增量补

### 何时建 entity/concept 页

- **不自动建**——避免空壳页稀释 graph view
- **建议阈值**：concept 页需在 paper 页中 inbound ≥ 5；entity 页 inbound ≥ 3
- 由 `wiki-lint` 输出「缺页 watchlist」，人工决定是否升级
- 建页后，`wiki-update` 会自动在新 paper 页里补 wikilink

### 工作流

#### Ingest（新论文进入 wiki）

```
1. 论文 PDF 放到 papers/{conf-year} 或 papers/{topic}/
2. 用户跑 /wiki-paper papers/{dir}/{stem}.pdf
   → 若 markdown 不存在 → 自动 mineru
   → 写 wiki/papers/{Name}-{Conf}{Year}.md
   → 末尾自动调用 /wiki-update
3. /wiki-update 扫描新 paper 页
   → 给已知 entity/concept 补首次出现处的 wikilink
   → 更新被引 entity/concept 页的「相关论文」节
   → 在 wiki/log.md 追加条目
```

#### Conference / Topic 综述

```
/wiki-survey {dir}
  # dir 可以是 conference 目录（osdi-2025、mlsys-2026 ...）
  # 或 topic 目录（ai-infra、foundation、finance、autoresearch、time-series ...）
  → 确保所有 PDF 都有 markdown（mineru）和 wiki paper 页（wiki-paper）
  → 聚合所有 paper 页：
    - conference → wiki/conferences/{Conf}-{Year}.md
    - topic       → wiki/themes/{TopicPascalCase}.md
  → 更新 wiki/index.md
  → 在 wiki/log.md 追加条目
```

#### Query

```
/wiki-query <自然语言问题>
  → 读 wiki/index.md 找候选页
  → 读 entity/concept/conference/theme 页
  → 顺 wikilink 进 paper 页
  → 必要时 fall back 到 markdowns/
  → 输出带 wikilink 的答案（不存档，除非用户要求）
```

#### Lint

```
/wiki-lint [--fix]
  → 检查：broken link / 缺页 watchlist / orphan / frontmatter / log 格式 / aliases 冲突 / 命名违规
  → read-only 默认；--fix 仅做最小安全修补
```

### Log 条目格式

每条固定前缀以便 `grep "^## \[" wiki/log.md | head -20` 解析：

```markdown
## [YYYY-MM-DD] {Page or Action}
- bullet
- bullet
```

倒序排列，最新在上。

### 反模式（不做）

- ❌ 不引入 embeddings / qmd / MCP 搜索（v1 阶段）
- ❌ 不引入 Dataview 等非核心 Obsidian 插件
- ❌ 不自动建 entity/concept 页——必须达到 inbound 阈值且人工确认
- ❌ 不在 paper 页里 verbatim 抄论文段落——细节回 markdowns/PDF
- ❌ 不批量回填旧 paper 页的 wikilink——只在新生成时增量补
- ❌ 不用 `[text](path/to/file.md)` 形式的内部链接——必须 wikilink

---

## Proposals 层

`wiki/proposals/` 存放研究 idea 的提案文档。通过两个 skill 生成，**probe 是 proposal 的强制性前置步骤**：

1. **`/probe <topic>`** — 深度 landscape characterization。穷尽 wiki 内关联论文、补缺（下载+mineru+wiki page）、外部搜索、输出结构化 probe 文档到 `wiki/proposals/probes/`。
2. **`/proposal <probe-slug> [--hypotheses-only]`** — 基于 probe 写迭代式 proposal。从 probe 的 tensions/blanks 中提炼可证伪假设，用 taste rubric 做 self-challenge，至少一轮迭代后输出 `wiki/proposals/{Slug}.md`。

### 命名

- Probe: `wiki/proposals/probes/{Slug}.md`，kebab-case（如 `thinking-model-kv-cache`）
- Proposal: `wiki/proposals/{Slug}.md`，PascalCase（如 `ThinkingModelKVCache`）

冲突时加 `-{YYYYMM}` 后缀。

### 与 wiki 的关系

- proposal **引用** wiki（用 wikilink 指 paper / concept / entity 页），是单向消费者
- proposal/probe 现已纳入 `wiki/` 目录，随 Quartz 发布到网站
- proposal **不进** `wiki/index.md`（除非手动添加），**不被** `wiki-update` / `wiki-survey` 扫描
- `wiki-lint` 会检查 proposal/probe 的 frontmatter 和 wikilink，但不做语义判断
- proposal 引仓库内论文一律 wikilink；引外部 arxiv / 论文用标准 markdown link 到 URL
- **proposal / probe 相关操作不进 `wiki/log.md`**。proposal 层的时间线仅记录在 `wiki/proposals/_log.md`

### 统一 Frontmatter（Proposal）

```yaml
---
type: proposal
name: {Slug}
title: {一句话 idea 标题}
status: draft        # draft | refined | implementing | shipped | archived
created: {YYYY-MM-DD}
last_updated: {YYYY-MM-DD}
target_venue: "{venue gradient 描述}"
tags: [tag1, tag2]
related_papers: ["[[X-Conf25]]", ...]
related_concepts: ["[[Concept1]]", ...]
related_systems: ["[[System1]]", ...]
novelty: high
feasibility: medium
effort: medium
---
```

`related_*` 字段必须双引号包裹 wikilink；空列表写 `[]`。

### Taste Rubric（/proposal 自我评估用）

`/proposal` 在 V1 完成后必须用以下 5 个维度逐条 self-challenge，≥2 不通过即重写：

| 维度 | 问题 | 通过条件 |
|------|------|----------|
| **Workload 真实性** | 问题来自 production observation 还是人为构造？实验配置是实际部署会用的吗？ | 有可引用的 production 数据或至少一个公开 benchmark 能代表真实场景 |
| **Counterintuitive** | 有没有「现有认知是错的」的发现？还是只做了更好的 engineering？ | 有明确定义的「community wisdom」+ 可证伪的反例预测 |
| **10x vs 2x** | 是打开了新的 design space，还是挤最后 20% 性能？ | 如果成功，社区会改变对这个问题的思考方式，不仅仅是 15-30% 的性能改进 |
| **Model-proof** | 这个问题会随 model 进步自动消失吗？好的系统工作解决的是即使模型变强也存在的问题 | 能在至少 3 个模型上验证，且有论证说明白为什么这个问题在更强模型上依然存在（甚至更严重） |
| **Abstraction** | 是否提出了新抽象？还是在已有抽象上做优化？ | 如果没有新抽象，至少有一个明确的 counterintuitive finding——两者必居其一 |

### 反模式（不做）

- ❌ 不让同一个 agent 既当 creator 又当 critic——`/probe` 是 neutral 的 landscape characterization，`/proposal` 用 taste rubric 做 structured external challenge
- ❌ 不在 proposal 里 verbatim 抄相关论文 abstract——提炼成「与本 idea 的关系」一句话
- ❌ 不写 `[[Slug]](wiki/proposals/Slug.md)` 这种 wikilink + paren 混合
- ❌ 不写「研究 X」这种伪 milestone deliverable——必须可机器/客观判定的指标
- ❌ 不做单点 novelty/feasibility 评分后直接输出——必须先过 probe，再做 taste 自评，再迭代
- ❌ 被否定的 proposal 不删除——保留在 `wiki/proposals/_log.md` 的 evolution trace 中，未来可能重新审视

---

## 公开发布（Quartz + Cloudflare Pages）

`wiki/` 通过 [Quartz v4](https://quartz.jzhao.xyz/) 发布为静态站点，部署在 Cloudflare Pages。Quartz 工程独立放在 `quartz/` 子目录，不污染 `wiki/` 也不影响 Obsidian vault。

### 本地预览

```bash
cd quartz
npx quartz build --serve -d ../wiki    # 默认 :8080，可加 --port 8787
```

- `-d ../wiki` 告诉 Quartz content root 在仓库外；不要在 `quartz/content` 做 symlink（CI 跨平台易坏）
- 首次跑需 `npm install` 装 485 个依赖；`node_modules/`、`public/`、`.quartz-cache/` 均在 `.gitignore` 忽略

### Cloudflare Pages 配置（一次性）

Dashboard → Workers & Pages → Create → Pages → Connect to Git → 选 `lqhl/awesome-system-papers`：

| 字段 | 值 |
|---|---|
| Project name | `awesome-system-papers`（域名：`awesome-system-papers.pages.dev`） |
| Production branch | `main` |
| Root directory（Advanced） | `quartz` |
| Build command | `npm ci && npx quartz build -d ../wiki` |
| Build output directory | `public` |
| Environment variables | `NODE_VERSION=22`、`BASE_URL=awesome-system-papers.pages.dev` |

保存后 CF 立即跑第一次 build。之后每次 push 到 `main`，CF 自动拉代码 → `cd quartz && npm ci && npx quartz build -d ../wiki` → 把 `quartz/public` 推上 CDN。通常 2-3 分钟内网站刷新。

### 配置微调位置

- **站名 / 字体 / 颜色 / locale**：`quartz/quartz.config.ts` 的 `configuration` 对象
- **侧边栏 / 目录 / breadcrumb**：`quartz/quartz.layout.ts`
- **发布域名**：`baseUrl` 已经从环境变量 `BASE_URL` 读，只在 CF 里改就行，不必改代码
- **暂不发布某页**：在该页 frontmatter 加 `draft: true`（Quartz 的 RemoveDrafts 插件会跳过）
- **排除目录**：`quartz.config.ts` 的 `ignorePatterns`（默认 `private / templates / .obsidian`）

### 已知小问题

- 两处 LaTeX warning（全角括号在数学模式内），不影响渲染，忽略即可
- 全站构建约 10-15s，528 个静态输出文件

---

## 已覆盖的会议

| 会议 | 全称 | 年份 |
|------|------|------|
| OSDI | USENIX Symposium on Operating Systems Design and Implementation | 2024, 2025 |
| ATC | USENIX Annual Technical Conference | 2024, 2025 |
| NSDI | USENIX Symposium on Networked Systems Design and Implementation | 2024, 2025 |
| SOSP | ACM Symposium on Operating Systems Principles | 2024, 2025 |
| MLSys | Conference on Machine Learning and Systems | 2024, 2025, 2026 |
| FAST | USENIX Conference on File and Storage Technologies | 2024, 2025, 2026 |

---

## 链接格式

本仓库在 Obsidian 中使用，所有 Markdown 文件内的内部链接统一用 **Obsidian wikilink** 格式：

| 场景 | 格式 | 示例 |
|------|------|------|
| 链接到 wiki 页（有显示文字） | `[[Page\|显示文字]]` | `[[vLLM\|vLLM 系统]]` |
| 链接到 wiki 页（文字即文件名） | `[[Page]]` | `[[vLLM-SOSP23]]` |
| 链接到 PDF 源文件 | `[[filename.pdf]]` | `[[fast2025-jiao.pdf]]` |
| 链接到 markdown 源文件 | `[[md-stem]]` | `[[osdi25-zhu-kan]]` |
| 外部 URL | 保持标准 Markdown | `[arXiv](https://arxiv.org/abs/...)` |

- 内部链接**不写路径，只写文件名**（Obsidian 按文件名解析）
- `.md` 后缀省略；PDF 保留 `.pdf` 后缀
- 外部 http/https 链接保持原有 `[text](url)` 格式不变
- **YAML frontmatter 里的 wikilink 必须用双引号包裹**：`parent: "[[KV-Cache]]"`、`source_pdf: "[[xxx.pdf]]"`、`subjects: ["[[vLLM]]", "[[SGLang]]"]`。否则 YAML 把 `[[X]]` 解析为嵌套数组 `[[X]]`，Obsidian properties 面板显示成字面字符串而非可点击链接。正文里的 wikilink 不需要 quote
- **禁止 wikilink + 半角小括号混用**：`[[Page]](path/to/Page.md)` 这种把 wikilink 紧跟 markdown 链接 url 的写法是错的——`[[Page]]` 已经是有效链接，后面的 `(...)` 会被 markdown 解析器误判，导致渲染异常。需要补充注释时用全角括号 `[[Page]]（说明文字）`，或干脆去掉。生成 log 条目「`生成：[[X]]`」就够，不要再写 `（wiki/themes/X.md）` 这种冗余路径

---

## 通用规则

- 修改文档时直接输出最终版内容，不要保留任何修改痕迹。包括但不限于：文字标注（"新增"、"更新"、"与之前版本对比"）、删线对比（`~~旧内容~~ → 新内容`）、注释说明已删除/替换的内容。修改后的文档就是唯一版本。
- 在 Markdown 表格中使用 wikilink 时，必须转义 `|` 为 `\|`，写成 `[[filename\|显示文字]]`。未转义的 `|` 会被解析为表格列分隔符，导致列错位。非表格行的 wikilink 不需要转义。
- **不要用单个 `~` 表示约数**（如 `~10–20`）：Obsidian / Quartz 会把成对的 `~` 渲染成删除线。改用「约 10–20」或纯数字范围。比较符号也避免裸写 `<`/`>`（尤其表格内），改用「少于」「大于」或反引号包裹。
- 遇到可复现的错误或踩坑时（如格式问题、工具使用陷阱、易混淆的约定等），主动将对应的防范规则追加到 CLAUDE.md 的相应章节中，避免同类错误再次发生。
