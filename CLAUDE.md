# awesome-system-papers

个人学术论文收藏库，整理和下载系统领域顶级会议的论文 PDF，供学习研究使用。

---

## 仓库结构

```
awesome-system-papers/
├── scripts/               # 论文下载 + 解析脚本
├── reports/               # 论文分析报告，按 topic 或 conference-year 分类
├── markdowns/             # mineru 解析出的论文 Markdown + 图片，按会议-年份分
├── inbox/                 # 临时收件箱，新论文放这里整理（gitignored）
├── papers/                # 论文 PDF
│   ├── ai-infra/         # AI 系统基础设施：训练/推理系统、显存/内存优化、分布式
│   ├── foundation/       # 开创性/里程碑工作
│   ├── agent/            # Agent：规划、记忆、RAG、多智能体
│   ├── ai4s/             # AI for Science / AI for AI：自动化研究、架构搜索
│   ├── finance/          # 金融领域应用
│   ├── osdi-2024/        # 会议论文 PDF（OSDI / ATC / NSDI / SOSP / MLSys / FAST）
│   ├── osdi-2025/
│   ├── atc-2024/
│   ├── atc-2025/
│   ├── nsdi-2024/
│   ├── nsdi-2025/
│   ├── sosp-2024/
│   ├── sosp-2025/
│   ├── mlsys-2024/
│   ├── mlsys-2025/
│   ├── fast-2024/
│   └── fast-2025/
├── progress.md            # 下载进度记录
└── .venv/                 # Python 虚拟环境
```

---

## 论文命名规范

| 会议 | 命名规则 | 示例 |
|------|---------|------|
| USENIX (OSDI/ATC/NSDI/FAST) | `{conf}{year}-{lastname}[-{extra}].pdf` | `osdi25-zhang-tony.pdf`, `nsdi2024-agarwal-shubham.pdf`, `fast2025-brunmayr.pdf` |
| MLSys | `{hash}.pdf`（原始下载文件名） | `0badcb4e95306df76a719409155e46e8.pdf` |
| SOSP | `{proceeding_doi}.{article_doi}.pdf` | `3731569.3764795.pdf` |

- 当同一作者有多篇论文时，用 `-{extra}` 区分（如 `nsdi2024-namyar-finding.pdf` vs `nsdi2024-namyar-solving.pdf`）
- 不要随意重命名 PDF 文件，以免破坏与外部数据源的对应关系

---

## 读取 PDF

Claude Code 的 `Read` 工具对 PDF 的处理是**把每页渲染成图像**交给多模态模型看,不是抽文本层:

- 能看到图、表、公式的视觉形式,但文字精度取决于视觉识别
- 每页约 1500-3000 token,长论文(20+ 页)直接 Read 会吃掉大量上下文
- 适用场景:快速浏览、看图、核对细节

大批量或需要精确文本时,优先用 mineru 把 PDF 转成 Markdown(见"PDF → Markdown 解析"章节),再 Read 生成的 `.md` + 按需 Read 独立图片,token 开销小一个量级。

python 相关依赖用 uv 安装和使用。可以用 `uv pip list` 列出现有的 python 包。

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

用 [MinerU](https://github.com/opendatalab/MinerU) 把 PDF 解析成 Markdown + 图片,便于下游(LLM 阅读、自动报告)按需访问。

### 工具链

- **MinerU**：开源的 PDF 解析工具链,识别布局、公式(MFR 模型)、表格,抽取图片
- 安装:`uv tool install --python 3.12 "mineru[pipeline]"`,得到全局 `mineru` 和 `mineru-api` 两个命令
- **`scripts/run_mineru.py`**：包装脚本,处理批量 + 并发 + 后处理,启动常驻 mineru-api 复用模型加载

### 脚本用法

```bash
uv run scripts/run_mineru.py <input_dir> <output_dir> [-j N] [-m {auto,txt,ocr}]
```

- `<input_dir>`：含 PDF 的目录(非递归)
- `<output_dir>`：输出目录,每个 PDF 产出 `{stem}/{stem}.md` + `{stem}/images/`
- `-j`：客户端并发数,默认 2
- `-m`：正文抽取方式,默认 `auto`;LaTeX 矢量 PDF 推荐 `txt`,更快更精确

示例:

```bash
uv run scripts/run_mineru.py papers/osdi-2025 markdowns/osdi-2025 -j 2 -m txt
```

脚本特性:
- 跳过目标已存在 `{stem}.md` 的 PDF,支持断点续跑
- 每 20s 心跳显示进度、平均耗时、ETA
- 子进程日志写到 `{output_dir}/{stem}/mineru.log`,成功时自动删除,失败时保留以便排查
- mineru-api 日志写到 `{output_dir}/.mineru-api.log`,可 `tail -f` 看 mineru 单页进度

### 输出结构

```
markdowns/osdi-2025/osdi25-gao/
├── osdi25-gao.md           # 论文正文 markdown,图片引用为 ![](images/{hash}.jpg)
└── images/                 # 所有抽取的图片(figure/complex table/rendered formula)
    ├── f2eb...cb.jpg
    └── ...
```

### method 选择

| 模式 | 正文来源 | 适用场景 |
|------|----------|----------|
| `-m txt` | PDF text layer 直读 | **推荐给 LaTeX 矢量 PDF**,如 OSDI/SOSP/MLSys 论文。精确、快(比 OCR 省 30-60s/篇) |
| `-m auto`(默认) | 由 mineru classify 自动判断,文本 PDF 走 text layer,扫描件走 OCR | 不确定 PDF 类型时用 |
| `-m ocr` | 全页 OCR | 扫描件,或 `-m txt` 出现严重字符错位时 |

**图片/表格/公式的识别不受 `-m` 影响**,走独立的视觉模型(Layout + WirelessTable/WiredTable + MFR),表格内单元格文字有独立 OCR 路径。

### Mac 注意事项

- **MinerU 上游在 Mac 上把 api 并发硬编码为 1**(`mineru/cli/fast_api.py:248`),`-j N` 仅让客户端并发排队,api 仍串行。想真正并行需要 Linux + GPU
- **`hybrid-auto-engine` 在 Mac 上不可用**:会触发 MLX 线程 bug([ml-explore/mlx#3078](https://github.com/ml-explore/mlx/issues/3078)),脚本已硬编码 `--backend pipeline`
- 内存:单 worker 加载 OCR 模型约 2 GB,16 GB 机器最多 `-j 2`,跑 `-j 8` 必 OOM

### `-m txt` 的已知瑕疵(OSDI 论文实测)

- **小数点偶尔丢失**:"1.61×" → "1 61×"(PDF text stream 字符间距问题)
- **希腊字符参数顺序错位**:"A(v,k,λ)-SBIBD" → "A (v k )-SBIBD...,,λ,,λ"(LaTeX 数学符号 span 位置错乱)
- **稀疏 0/1 矩阵识别失败**:MFR 模型局限,变成空 `\begin{array}...\end{array}`

这些对下游阅读理解影响不大(95% 内容正确),需要精确引用公式/数字时 fall back 到原 PDF 核对。

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

- 每个 topic 目录下维护 `README.md` 作为索引，与 `reports/{topic}/README.md` 对应
- 论文移动前先确认 PDF 内容，文件名保留原样（arXiv ID 或原文件名）
- 同一 topic 下论文多了，再按需拆分子目录

---

## 报告撰写规范

报告按 topic 或「会议-年份」分类：

- **Topic 报告**：`reports/{topic}/`，如 `reports/ai-infra/README.md`
- **会议报告**：`reports/{conference}-{year}/`，如 `reports/osdi-2025/README.md`

```
reports/
├── README.md                     # 全局索引
├── ai-infra/
│   ├── README.md                  # 综述与论文索引
│   └── 2603.15031v1.md
├── foundation/
│   ├── README.md
│   └── 1706.03762v7.md
├── finance/
│   ├── README.md
│   └── 2412.09880v1.md
├── osdi-2025/
│   ├── README.md
│   └── osdi25-zhang-tony.md
└── ...
```

### `README.md` 综述文档

每个目录维护一个 `README.md`：

- **Topic**：`papers/{topic}/README.md` + `reports/{topic}/README.md` 同步维护，作为该主题的综述与论文索引
- **会议**：`reports/{conference}-{year}/README.md`，包含会议概述（主题分布、研究趋势）、论文列表、重点推荐

### 单篇论文报告

- 文件名与对应 PDF 文件名保持一致（不含 `.pdf` 后缀）
- 报告结构参考：
  1. 论文基本信息（标题、作者、会议、链接）
  2. 研究问题与动机
  3. 核心设计与方法
  4. 主要贡献
  5. 关键实验结果
  6. 局限性 / 未来工作
  7. 个人评注

---

## 已覆盖的会议

| 会议 | 全称 | 年份 |
|------|------|------|
| OSDI | USENIX Symposium on Operating Systems Design and Implementation | 2024, 2025 |
| ATC | USENIX Annual Technical Conference | 2024, 2025 |
| NSDI | USENIX Symposium on Networked Systems Design and Implementation | 2024, 2025 |
| SOSP | ACM Symposium on Operating Systems Principles | 2024, 2025 |
| MLSys | Conference on Machine Learning and Systems | 2024, 2025 |
| FAST | USENIX Conference on File and Storage Technologies | 2024, 2025 |

---

## 链接格式

本仓库在 Obsidian 中使用，所有 Markdown 文件内的内部链接统一用 **Obsidian wikilink** 格式：

| 场景 | 格式 | 示例 |
|------|------|------|
| 链接到报告（有显示文字） | `[[filename\|显示文字]]` | `[[osdi25-zhu-kan\|NanoFlow]]` |
| 链接到报告（文字即文件名） | `[[filename]]` | `[[osdi25-zhu-kan]]` |
| 链接到 PDF（源文件字段） | `[[filename.pdf]]` | `[[fast2025-jiao.pdf]]` |
| 外部 URL | 保持标准 Markdown | `[arXiv](https://arxiv.org/abs/...)` |

- 内部链接**不写路径，只写文件名**（Obsidian 按文件名解析）
- `.md` 后缀省略；PDF 保留 `.pdf` 后缀
- 外部 http/https 链接保持原有 `[text](url)` 格式不变

---

## 通用规则

- 修改文档时直接输出最终版内容，不要保留任何修改痕迹。包括但不限于：文字标注（"新增"、"更新"、"与之前版本对比"）、删线对比（`~~旧内容~~ → 新内容`）、注释说明已删除/替换的内容。修改后的文档就是唯一版本。
- 在 Markdown 表格中使用 wikilink 时，必须转义 `|` 为 `\|`，写成 `[[filename\|显示文字]]`。未转义的 `|` 会被解析为表格列分隔符，导致列错位。非表格行的 wikilink 不需要转义。
- 遇到可复现的错误或踩坑时（如格式问题、工具使用陷阱、易混淆的约定等），主动将对应的防范规则追加到 CLAUDE.md 的相应章节中，避免同类错误再次发生。
