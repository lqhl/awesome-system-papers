---
type: paper
name: PyLO
full_title: "PyLO: Towards Accessible Learned Optimizers in PyTorch"
authors: [Paul Janson, Benjamin Therien, Quentin Anthony, Xiaolong Huang, Abhinav Moudgil, Eugene Belilovsky]
venue: MLSys
year: 2026
tags: [learned-optimization, pytorch, cuda, velo, training, systems]
source_pdf: "[[c45147dee729311ef5b5c3003946c48f.pdf]]"
source_md: "[[c45147dee729311ef5b5c3003946c48f]]"
---

# PyLO: Towards Accessible Learned Optimizers in PyTorch (MLSys 2026)

> **一句话总结**：VeLO 等 SOTA learned optimizer 困在 JAX meta-training 生态；PyLO 提供 `torch.optim.Optimizer` 接口 + HuggingFace Hub 权重 + 融合 CUDA kernel（small fc lopt / VeLO），ViT-B/16 bs32 优化器步从 **39/50 → 206/191 samples/s**，相对 JAX 实现 **>2×**，并支持 weight decay/LR schedule 组合。

## 问题与动机

Learned optimization（LO）用元学习训练「优化器网络」替代 Adam 等手工规则；VeLO（4000 TPU-months meta-train）可超 NadamW，但社区 **~80% PyTorch** 用户难以接入：Google `learned_optimization` 偏 meta-training、缺 PyTorch 路径、无 Hub 化权重共享、逐步 MLP 推理开销巨大。

PyLO 目标：**部署而非 meta-train**——decouple 预训练 LO 权重与使用侧，降低 per-step 开销。

## 关键观察 / 隐含假设

- **观察 1：朴素 PyTorch LO 步对 \(m×n\) 参数张量物化 \(mn×d_{feat}\) 特征、74–252 kernel launches/张量，内存带宽成瓶颈（Fig. 4）。**
  - **依赖假设**：每个参数元素独立过小 MLP（VeLO/small fc lopt 架构）无法受益于标准 nn.Linear batching。
  - **可能失效场景**：极大单层（width 4096+ depth 深）仍可能 OOM——Fig. 6 有缺失点。

- **观察 2：两阶段融合 kernel——Pass1 寄存器内算特征并归约平方统计（O(d_feat) 共享内存）；Pass2 加载归一化因子、内联 MLP、写回参数——可将 launch 降至 30–114，消除 \(mn×d_{feat}\) 临时缓冲。**
  - **证据强度**：**高**——ViT-B/16 优化器步 **86–88%** 降幅 vs naive CUDA。

- **观察 3：LO 步开销随 batch 增大相对 forward/backward 摊薄；大模型训练更「值得」试 LO。**
  - **可能失效场景**：小 batch 微调场景 optimizer 仍可能占可观比例。

- **假设 1：Hub 分发 meta-trained 权重 + 标准 PyTorch modifier（WD、schedule）足以触发社区采用，无需开放 meta-training 全栈。**
  - **依赖假设**：现有 VeLO/small fc lopt 权重泛化到用户任务。

## 核心方法

**四模块架构**：
- `pylo.optim`：状态、特征、步进，兼容 `state_dict`。
- `pylo.models`：LO 网络 + **HuggingFace Hub** 拉取/发布权重。
- `pylo.csrc`：双 kernel 融合（特征统计 + apply LO）。
- `PyLO-Examples`（独立 repo）：FineWeb EDU、ImageNet 等评测脚本。

**CUDA 设计**：寄存器驻留 \(d_{feat}≈39\) 特征与 MLP 激活；warp shuffle + block reduce 求 normalization；`__ldg` 读 MLP 权重；数值与 naive 等价。

**互操作**：`torch.optim` 式 API 叠加 weight decay、LR scheduler——实验显示简单 modifier 可 **显著** 提升 LO 表现（论文 §1 贡献 5）。

## 设计取舍

- **仅 inference-time LO vs 含 meta-training**：代码量小、依赖少，但不解决「训练新 LO」门槛。
- **融合 kernel vs PyTorch compile**：手写 CUDA 针对 per-parameter MLP 访存模式，通用 compile 难达同等带宽利用。
- **数据 parallel 分布 optimizer 步**：多卡可进一步摊薄 LO 计算，增加通信与实现复杂度。
- **VeLO 泛化**：meta-train 分布外任务仍可能需调 modifier 或失败——论文 benchmark 聚焦 ViT/GPT-2 预训练。

## 实验与结果

**ViT-B/16 @ A100 bs32**（Fig. 1）：small fc lopt **39.36→205.59** samples/s；VeLO **49.73→191.18** samples/s。

**相对 JAX**（Fig. 5，GPT-2 系列）：CUDA PyLO 逐步时间随模型增大仍低于 JAX 编译路径，**>2×** 步速优势。

**MLP 微基准**（Fig. 6）：相对 naive **~10×** 步速降幅（1-layer/256-wide/4096-wide 配置）。

**训练质量**：附录与 examples 报告 LO 在 FineWeb/ImageNet 上与 Adam 等对比（细节见 PyLO-Examples）。

## Critical Analysis

**强项**：直击 LO 采纳的 **工程真瓶颈**（框架、权重共享、kernel），而非又一个 meta-learning 算法；融合 kernel 设计清晰（带宽主导、两 pass、无特征物化），对其它 per-element 小网络场景可迁移。

**弱点**：未证明 VeLO 在广泛生产任务上稳定 beat 调优 AdamW；LO 仍增加步时——小模型/小 batch 不划算；依赖外部 meta-trained 权重，生态仍集中於 Google；多 GPU optimizer 分片仅初步讨论。

**定位**：降低「试用 VeLO」成本，不是取代 Hand-tuned optimizer 的理论工作。

## 局限与 Future Work

- 更多 Hub 权重、训练分布文档与 failure mode 指南。
- FSDP/ZeRO 与 LO 状态分片。
- `torch.compile` 与自定义 op 长期维护。
- 更大规模 LLM pretrain 端到端 LO 经济性研究。

## 相关

- **Learned opt**：VeLO、small fc lopt、Open-L2O、Google learned_optimization
- **Stack**：[[PyTorch]]、HuggingFace Hub、CUDA
- **对比**：Adam、NadamW、Optax/JAX