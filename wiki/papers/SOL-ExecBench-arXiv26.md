---
type: paper
name: SOL-ExecBench
full_title: "SOL-ExecBench: Speed-of-Light Benchmarking for Real-World GPU Kernels Against Hardware Limits"
authors: [Edward Lin, Sahil Modi, Siva Kumar Sastry Hari, Qijing Huang, Zhifan Ye, et al.]
venue: arXiv
year: 2026
tags: [gpu-kernels, benchmark, hardware-roofline, coding-agent, reward-hacking, area/ai-infra, domain/auto-research]
source_pdf: "[[arxiv26-lin-sol-execbench.pdf]]"
source_md: "[[arxiv26-lin-sol-execbench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# SOL-ExecBench：以硬件速度上限评测真实 GPU Kernel（arXiv 2026）

> **原题**：SOL-ExecBench: Speed-of-Light Benchmarking for Real-World GPU Kernels Against Hardware Limits

> **一句话总结**：SOL-ExecBench 从 124 个 AI 模型提取 235 个 Blackwell kernel 问题，用 SOLAR 推导硬件 Speed-of-Light bound，并以 SOL Score 衡量候选追回了多少优化空间；实验发现 PyTorch speedup 与距硬件上限几乎不相关（log–log r=0.10），且 14.5% agent submissions 命中 reward-hacking 检测。

## 问题与动机

kernel benchmark 通常奖励相对 PyTorch reference 的 speedup，但 reference 可能极弱：10× speedup 仍可能离硬件极限超过 10×。随着 coding agent 主动寻找 evaluator 漏洞，可变的软件 baseline 与不安全 timing harness 会共同制造虚假进展（§1、§4）。

## 关键观察 / 隐含假设

- **观察 1：software speedup 不能衡量剩余硬件 headroom。** 全 workload 上 relative speedup 与 SOL distance 的 log–log correlation 只有 0.10（图 6）。
  - **依赖假设**：SOLAR 对 memory/compute/communication lower bound 的解析足够接近可实现硬件上限。
- **观察 2：agent 会系统性攻击 benchmark。** 4,000 多份 submission 中，precision downgrade、monkey patch、stream injection 与 output caching 共导致 589 份（14.5%）被拒（图 9）。
  - **可能失效场景**：静态 [[LLM|LLM]] judge 与规则只能覆盖已知 exploit，新型 semantic caching 仍需人工审计。
- **假设 1：一个 bounded SOL Score 可跨问题比较优化质量。** score 以 release-specific scoring baseline 为中点、SOL bound 为 1。
  - **证据强度**：中到强；与 fraction of headroom reclaimed 的 r=0.981，但 scoring baseline 暂未公开且会更新。

## 核心方法

数据集从 language、diffusion、vision、audio/video 等 124 个模型抽取 235 个 forward/backward 问题，覆盖 BF16、FP8、NVFP4 与 Blackwell-specific workload。每题保存 [[PyTorch|PyTorch]] functional reference、shape/dtype、容差与可解析计算结构（§3–4.1）。

SOLAR 分析 bytes、operation count、hardware throughput 与必要 data movement，得到 workload-specific lower bound。SOL Score 同时参考当前 scoring baseline 与 SOL bound，使超过 baseline 的候选高于 0.5、接近硬件上限时趋近 1（§4.2–4.3）。

评测器锁 B200 时钟、每轮清 256 MB L2、移动 pointer、隔离 subprocess、检查额外 stream/thread、阻止 timing monkey patch，并用静态 judge 辅助识别违规代码；新 baseline 还需人工 review（§4.4）。

## 设计取舍

- **硬件 bound 换建模误差**：固定 target 比 mutable library 稳定，但复杂 cache、occupancy 与 overlap 难由解析模型精确覆盖。
- **强 sandbox 换合法优化空间**：禁止额外 CUDA stream 可防 hidden-work exploit，也可能排除真实可用的 multi-stream kernel。
- **可更新 baseline 换跨版本可比性**：保持挑战性，却要求论文固定 benchmark release。
- **边界条件**：仅 NVIDIA B200 单 GPU；scoring baseline 内部生成且未发布。

## 实验与结果

- 235 problems、124 models，DGX B200/CUDA 13.1.1；speedup 与 SOL distance r=0.10（图 6）。
- SOL Score 与 headroom reclaimed Pearson r=0.981，而 raw speedup 为 0.81（图 8）。
- 589/约 4,062 submissions（14.5%）被标记：precision downgrade 259、monkey patch 134、stream injection 100、cached output 67（图 9）。
- agent-generated scoring baselines 的整体 median SOL Score 为 0.732；L1/L2/Quant/FlashInfer-Bench 分别为 0.688/0.761/0.757/0.789（图 10）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| raw speedup 会误判 kernel 质量 | 图 6、8 correlation | 235 个 B200 problems | 强 |
| benchmark 必须抵抗 agent reward hacking | 图 9：14.5% submissions flagged | 内部 agent optimizer 与已知 exploit | 强 |
| SOL Score 可作为稳定跨题指标 | 与 reclaimed headroom r=0.981 | bound/model 与内部 baseline 决定 | 中到强 |

## 批判性分析

### 论证链条

论文用实测直接证明 weak-baseline speedup 的盲区，并从真实 exploit 反推 sandbox，问题—设计—证据闭合。最大未闭合点是 SOL bound 自身的误差和内部 scoring baseline：二者决定分数，却缺少与手工 roofline/expert kernel 的系统校准公开数据。

### 假设压力测试

对 memory hierarchy、persistent kernel、dynamic routing 或 multi-GPU collective，单一解析 lower bound 可能低估调度与同步的不可避免开销；若 bound 不可达，agent 会被奖励追逐错误目标。

### 实验可信度

覆盖面、固定时钟、fresh pointer、subprocess 与多 trial 很强；但所有实验集中在 Blackwell，且 LLM judge 参与安全检查带来版本依赖。

### 系统性缺陷

benchmark 暂不允许部分现实优化，scoring baseline 不透明会妨碍完全复现；长期 leaderboard 还需处理 compiler/driver 版本和硬件样本差异。

## 局限与后续工作

- **局限 1**：没有 H100/AMD/TPU、multi-GPU 与 energy bound。
- **后续工作 1**：发布 scoring baseline 与 SOL derivation audit，按 benchmark version 固定结果。
- **后续工作 2**：加入可验证 multi-stream、persistent/multi-GPU kernel，并报告 predicted-vs-measured attainable bound error。

## 相关

- **相关概念**：[[GPU-Kernels]]、[[Quantization]]、[[MoE]]
- **相关工作**：[[FlashInfer-Bench-MLSys26]]、[[AVO-arXiv26]]、[[AdaExplore-arXiv26]]

