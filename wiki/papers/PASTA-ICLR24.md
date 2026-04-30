---
type: paper
name: PASTA
full_title: "Tell Your Model Where to Attend: Post-hoc Attention Steering for LLMs"
authors: [Qingru Zhang, Chandan Singh, Liyuan Liu, Xiaodong Liu, Bin Yu, Jianfeng Gao, Tuo Zhao]
venue: ICLR
year: 2024
tags: [attention-steering, llm-inference, kv-cache, post-hoc, model-profiling]
source_pdf: "[[iclr24-zhang-pasta.pdf]]"
source_md: "[[iclr24-zhang-pasta]]"
---

# PASTA: Post-hoc Attention Steering for LLMs (ICLR 2024)

> **一句话总结**：用户指定 prompt 中的重点片段（如指令、新事实），PASTA 在推理时 post-hoc 地找到一小撮 attention head 并对它们做精确的 attention score 重加权（highlighted token 权重放大、其他缩水），不改模型参数，在 instruction following / long context / knowledge conflict 三类场景全面提升，Llama-7B 上平均 accuracy 提升 22%。

## 问题

LLM 在处理长 context、复杂指令和知识冲突（context 中含与预训练矛盾的新事实）时经常「跟丢」用户意图。人类阅读时用加粗/斜体标识重点，但 LLM 只能读取纯文本——即使加了 markdown 强调标记，LLM 也往往捕捉不到这些弱信号。

## 核心方法

PASTA 由两个组件构成：

**1. Post-hoc Attention Steering（推理时）**：给定用户指定的重点 token 集合 $\mathcal{G}$，对选定的 attention head $(l,h)$ 的 attention score 做乘法重加权：

$$[\mathcal{T}(\mathbf{A})]_{ij} = \begin{cases} \alpha A_{ij}/C_i & \text{if } j \in \mathcal{G}^- \\ A_{ij}/C_i & \text{otherwise} \end{cases}$$

即把非重点 token 的 attention 乘以 $\alpha$（$0 \le \alpha < 1$），再重新归一化——等价于把重点 token 的 attention 放大 $1/\alpha$。选择乘法而非加法的原因是保留重点 token 之间的注意力大小差异。

**2. Multi-task Model Profiling（一次性离线）**：不是所有 attention head 都适合被 steering。PASTA 在多个任务上对每个 head 单独跑 steering 并评估表现，取多任务 top-k 交集作为模型级别的 steering head profile——只需做一次，对新任务也有效。

## 关键结果

- **Llama-7B** 在 4 个挑战性任务上平均 accuracy **提升 22%**（vs few-shot prompting）
- JSON Formatting：格式准确率 + 预测准确率均大幅提升
- Pronouns Changing：复杂指令跟随能力显著增强
- CounterFact：知识冲突场景下新事实的引导更准确（efficacy score + paraphrase score）
- BiasBios：长 context 中关键信息（首句的职业信息）被更有效利用
- **只修改 attention score，不碰模型权重**，与任何 LLM inference pipeline 兼容

## 相关

- **相关概念**：[[Attention]]、[[KV-Cache]]、Multi-Head Attention
- **后继工作**：AutoPASTA（自动找重点 token）、[[LLMSteer-NeurIPSW24|LLMSteer]]（prefix-caching 兼容的 query-independent steering）
- **同类方向**：activation steering、representation engineering、inference-time intervention
- **同会议**：ICLR 2024
