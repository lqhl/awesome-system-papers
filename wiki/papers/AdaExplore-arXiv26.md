---
type: paper
name: AdaExplore
full_title: "AdaExplore: Failure-Driven Adaptation and Diversity-Preserving Search for Efficient Kernel Generation"
authors: [Weihua Du, Jingming Zhuo, Yixin Dong, Andre Wang He, Weiwei Sun, et al.]
venue: arXiv
year: 2026
tags: [gpu-kernels, coding-agent, test-time-adaptation, search, triton, area/ai-infra, domain/auto-research]
source_pdf: "[[arxiv26-du-adaexplore.pdf]]"
source_md: "[[arxiv26-du-adaexplore]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# AdaExplore：失败驱动适应与保多样性 Kernel 搜索（arXiv 2026）

> **原题**：AdaExplore: Failure-Driven Adaptation and Diversity-Preserving Search for Efficient Kernel Generation

> **一句话总结**：AdaExplore 将 Triton kernel agent 分成“从合成失败提炼跨任务 validity skills”和“在 candidate tree 上交替局部修补/结构再生成”两阶段；GPT-5-mini 在 KernelBench L2/L3 的 100-step 搜索中分别达到 3.12×/1.72× PyTorch speedup，并在 FlashInfer-Bench 上验证对生产 shape 的迁移。

## 问题与动机

现有 kernel agent 多把每个问题独立处理，execution feedback 只用于当前 patch，无法积累 DSL validity knowledge；纯 iterative refinement 又容易围绕一个结构陷入局部最优。Triton 训练语料较少、约束严格且性能面非光滑，使 correctness 与 exploration 同时成为瓶颈（§1、§3）。

## 关键观察 / 隐含假设

- **观察 1：失败可以压缩成跨任务规则。** AdaExplore 从 L1 合成任务的 compiler/runtime failure 中归纳 skill memory，加入不同模型与搜索 baseline 后能提高 L2 correctness（表 2）。
  - **依赖假设**：训练合成任务覆盖测试 DSL failure mode，且 [[LLM|LLM]] 提炼的规则不会过度限制合法优化。
- **观察 2：局部 patch 与结构 regeneration 需要同时存在。** tree search 在 improvement/stagnation 后选择 refine 或 regenerate，并用 execution signature 与代码差异保持 diversity（§3.4）。
  - **可能失效场景**：运行噪声大或 evaluation 很贵时，100-step tree expansion 成本可能超过收益。
- **假设 1：[[PyTorch|PyTorch]] eager speedup 可代表 kernel 优化质量。** 主实验以 clipped speedup 和 Fast@p 衡量。
  - **证据强度**：中；附录用 [[FlashInfer-Bench-MLSys26]] 强 baseline 补充，但主榜仍可能受弱 reference 影响。

## 核心方法

Adapt 阶段先生成 L1-like Triton tasks，运行候选并把重复失败聚成自然语言 skills；后续 prompt 按错误相关性检索这些规则。Explore 阶段维护 candidate tree，每个 node 含代码、runtime、反馈和 lineage，交替做局部 edit 与大结构重生成，并避免重复 execution signature（§3.3–3.4）。

评分同时要求 correctness 与 runtime；实验将 GPT-5-mini 与 single-pass、parallel sampling、iterative refinement、DR. Kernel 和 OpenEvolve 比较，并单独消融 skill memory、action 与 node selection（§4–5）。

## 设计取舍

- **跨任务 skill 换规则陈旧风险**：规则提高可行率，但 compiler/hardware 更新后可能排除新 idiom。
- **tree diversity 换 evaluation 成本**：结构探索避免 local optimum，却需要保存和重测更多候选。
- **无训练适应换 prompt 依赖**：不更新权重，部署简单；收益可能随 base model 和 context policy 改变。
- **边界条件**：主实验为 A6000 1500 MHz、Triton、KernelBench L2/L3；不是 CUDA/PTX 或多 GPU kernel。

## 实验与结果

- 在 100 steps 下，KernelBench L2/L3 best kernel 相对 PyTorch eager 平均 speedup 为 3.12×/1.72×；论文同时报告 Accuracy、Fast@1.2 和 Fast@2，speedup clip 为 10（表 1）。
- Cross-task skill memory 在多种模型/搜索方式上提高 L2 correctness，说明收益不只来自 AdaExplore tree policy（表 2）。
- FlashInfer-Bench 附录使用真实 serving shapes 与专家 CUDA baseline；结果显示方法仍能提高正确率与速度，但优势弱于对 eager PyTorch 的主实验（Appendix B）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 失败记忆能跨 kernel task 改善 correctness | 表 2 多 baseline 有/无 memory | 合成 L1→KernelBench L2 | 中 |
| diversity-preserving search 优于局部 refinement | 表 1、§5 action ablation | GPT-5-mini、A6000、固定步数 | 中 |
| 方法适合生产 kernel | Appendix B FlashInfer-Bench | 有真实 shape，但任务与硬件范围有限 | 中 |

## 批判性分析

### 论证链条

论文把 correctness knowledge 与 performance exploration 分开，且通过 memory/action ablation 支撑两部分贡献。薄弱点是主 headline 相对 PyTorch eager，无法说明距离专家 kernel 或 hardware roofline 多远；FlashInfer-Bench 补测缩小但没有消除这一差距。

### 假设压力测试

当 task 间 API/硬件差异大时，共享 failure skill 可能 negative transfer；当最优解要求先退化或跨多个文件重构时，以当前 node runtime 驱动的选择也可能过早剪枝。

### 实验可信度

baseline 类型较全，并报告 capped metric 与 correctness。仍缺跨 GPU 代际、跨 DSL、多个 base LLM、总 token/美元以及独立重跑方差。

### 系统性缺陷

agent-generated kernel 的 sandbox、reward hacking、功耗和 driver fault 没有像 SOL-ExecBench 那样成为主设计；skill memory 的版本、冲突和撤销语义也未定义。

## 局限与后续工作

- **局限 1**：结论主要绑定 Triton、A6000 与 KernelBench。
- **后续工作 1**：在 H100/B200、Triton/CUDA/TileLang 上交叉训练/测试 skill memory，报告 transfer matrix 和错误规则撤销率。
- **后续工作 2**：用硬件 SOL 与专家库 baseline 取代单一 eager speedup，加入 reward-hacking audit。

## 相关

- **相关概念**：[[GPU-Kernels]]、[[Evolutionary-Search]]
- **相关工作**：[[FlashInfer-Bench-MLSys26]]、[[AVO-arXiv26]]

