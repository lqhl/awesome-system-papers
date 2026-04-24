---
type: paper
name: AlphaEvolve
full_title: "AlphaEvolve: A coding agent for scientific and algorithmic discovery"
authors: [Alexander Novikov, Ngân Vũ, Marvin Eisenberger, Emilien Dupont, Po-Sen Huang, et al.]
venue: arXiv
year: 2025
tags: [auto-research, evolutionary-coding, llm-agent, algorithm-discovery, superoptimization]
source_pdf: "[[2506.13131v1.pdf]]"
source_md: "[[2506.13131v1]]"
---

# AlphaEvolve: A coding agent for scientific and algorithmic discovery (arXiv 2025)

> **一句话总结**:DeepMind 的进化式 coding agent,用 Gemini 2.0 Flash/Pro ensemble 对整份代码文件做 LLM 指导的进化搜索,发现了 56 年来首个优于 Strassen 的 4×4 复矩阵乘法(48 次标量乘法,原 49),在 50+ 数学开放问题上 75% 重现 SOTA、20% 超越 SOTA(含 Erdős minimum overlap、11 维 kissing number 593 球);部署到 Google 基础设施后,Borg 调度平均回收 0.7% fleet-wide 计算资源、Gemini kernel 加速 23%(训练总时长减 1%)、FlashAttention GPU kernel 提速 32%。

## 问题

自动化科学/算法发现长期依赖 handcrafted 进化算子或专用 search 系统(AlphaTensor、AlphaDev),而 LLM 虽然擅长 coding 但单次 prompt 难以做长链 ideation/backtracking。前作 [[FunSearch-Nature24]] 证明了 LLM-guided evolution 在构造型数学问题(如 cap set)上的潜力,但局限明显:只能进化单个 Python 函数(10-20 行)、单一目标、百万级 LLM sample、context 极简、用小模型无法受益于 SOTA LLM。如何把这一范式规模化到真实复杂问题——完整代码库、多语言、多目标、耗时评估——是核心挑战。

## 核心方法

AlphaEvolve 是一个异步进化 pipeline,围绕**"LLM 改代码 → 自动评估 → 存数据库 → 再采样"**的循环:

- **Task specification**:用户提供初始代码 + 一个 Python `evaluate` 函数(返回 metric dict),用 `# EVOLVE-BLOCK-START/END` 注释标记可进化段。可以进化整份文件、任意语言,最长几百行代码;`evaluate` 可以跑几秒到 100+ compute-hour(并行化)。
- **Prompt sampling**:每个 prompt 由 program database 采样的多条历史解 + system 指令构成,支持 explicit context(pdf、literature)、stochastic formatting 多样化模板、rendered evaluation results、以及 **meta prompt evolution**——元 prompt 本身也在独立数据库里被进化。
- **Creative generation**:LLM 输出以 `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` diff 块形式的修改。**Gemini 2.0 Flash + Gemini 2.0 Pro ensemble**:Flash 高吞吐多候选,Pro 偶尔给出高质量飞跃。
- **Evaluation**:支持 evaluation cascade(从易到难分阶段,差的早停)、LLM-generated feedback(评估 simplicity 等难量化属性)、parallelized evaluation。**多目标优化**既是内在目标,也能通过把不同结构的"好解"放进 prompt 提升单目标发现。
- **Evolution database**:MAP-Elites + island-based population 混合,平衡 exploration/exploitation,避免进化坍缩。
- **Distributed pipeline**:asyncio controller + LLM samplers + evaluation nodes,throughput-oriented。

vs [[FunSearch-Nature24]]:整文件 vs 单函数、任意语言 vs Python、受益于 SOTA LLM、rich context、多目标、样本效率高(thousands 而非 millions)、evaluation 可长至小时级。

相比 concurrent 工作:[[AI-Scientist-v2-arXiv25]] 生成完整 paper、[[Auto-Research-arXiv25]] 是 vision blueprint、[[MLR-Bench-arXiv25]] 是 benchmark;AlphaEvolve 刻意把 scope 收在"**有 automated evaluator 的问题**"上,用 programmatic 评估避免 LLM hallucination,从而能跑超长进化轨迹做出真突破。与 Google AI Co-Scientist(自然语言假设评估)是互补路径。

## 关键结果

- **矩阵乘法**:从一个简单的梯度下降 tensor decomposition 程序出发,在 14 个 (m,n,p) 张量 rank 问题上超越 SOTA;**4×4 复矩阵 48 次标量乘法**,56 年来对 Strassen (1969) 在 characteristic-0 field 上的首次严格改进。
- **数学开放问题**:50+ 问题 / 5+ 分支(analysis、combinatorics、number theory、geometry),75% 匹配已知最优、**20% 刷新 SOTA**;包含 Erdős minimum overlap 新上界、**11 维 kissing number 从 592 提升到 593**、多个 packing/Heilbronn 变体新结果;问题由 Terence Tao 等数学家建议。
- **Borg 数据中心调度**:进化出极简启发式,在 Google 全部 fleet 部署后平均**回收 0.7% 原本 stranded 的计算资源**;被选用而非 DRL 方案,因代码解可解释、可调试。
- **Gemini kernel tiling**:AlphaEvolve 自动搜出的 Pallas tiling 启发式,相对 expert 启发式**平均 23% kernel 加速**、Gemini 总训练时间减 1%;工程耗时从数月降到数天,标志性地"Gemini 自我优化"。
- **TPU 电路 RTL**:对已高度优化的 Verilog 矩阵乘单元找到一处 bit 简化,已由 TPU 设计师验证,并入下代 TPU,是 Gemini 首次直接改进 TPU 算术电路。
- **XLA IR / FlashAttention**:直接编辑编译器生成的 IR,**FlashAttention kernel 在目标推理 config 上提速 32%**,前后处理部分提速 15%,numerical correctness 经随机输入 + 专家验证。
- **Ablations**:evolutionary loop、prompt context、meta-prompt evolution、full-file evolution、强 LLM ensemble 每项都显著贡献;小模型 only 或 no-evolution 显著下降。

## 相关

- **相关概念**:LLM-guided evolution、superoptimization、MAP-Elites、island-based population、tensor decomposition、code diff protocol、meta prompt evolution
- **同类系统**:[[FunSearch-Nature24]]、[[AI-Scientist-v2-arXiv25]]、[[Auto-Research-arXiv25]]、[[MLR-Bench-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[MLAgentBench-ICML24]]、[[OpenHands-ICLR25]]
- **同主题**:[[Auto-Research]]
