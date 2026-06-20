---
type: paper
name: Katz
full_title: "Katz: Efficient Workflow Serving for Diffusion Models with Many Adapters"
authors: [Suyi Li, Lingyun Yang, Xiaoxiao Jiang, Hanfeng Lu, Dakai An, et al.]
venue: ATC
year: 2025
tags: [diffusion-model, controlnet, lora, t2i-serving, adapter-serving]
source_pdf: "[[atc2025-li-suyi-katz.pdf]]"
source_md: "[[atc2025-li-suyi-katz]]"
---

# Katz: Efficient Workflow Serving for Diffusion Models with Many Adapters (ATC 2025)

> **一句话总结**：基于生产 trace 发现 ControlNet 偏斜且 compute-heavy、LoRA 长尾且 loading-bound，Katz 用 ControlNet-as-a-Service（缓存+并行）、bounded async LoRA loading（K=10 步重叠）和 CFG latent parallelism 把 adapter 移出 critical path，在 H800 上相对 Diffusers 最高 7.8× 降延迟、1.7× 提吞吐，75 人 user study 确认无质量损失。

## 问题与动机

生产级 text-to-image（T2I）服务不是单独跑一个 base [[Diffusion-Model]]，而是 **base + 多 [[ControlNet]] + 多 [[LoRA]]** 的 workflow：ControlNet 用参考图控制构图，LoRA 控制风格。阿里生产平台 20 天 50 万+ 请求 trace 显示 **>98% 请求至少 1 个 ControlNet、>95% 至少 1 个 LoRA**，约 70% 同时用 2+ 个 ControlNet。adapter 引入两类延迟：按需从存储加载（平均每次请求加载占端到端延迟 **37%**），以及 ControlNet 的额外计算（H800 上加 1 个 ControlNet 让 SDXL 从 2.9s 涨到 4.5s，**1.6×**）。

全量预缓存不可行：SDXL 场景下约 **150 个 ControlNet**（各 ~3 GiB）和 **14,500 个 LoRA**（各几百 MiB）。现有系统（[[Diffusers]]、[[Nirvana-NSDI24|Nirvana]]、[[DistriFusion-CVPR24|DistriFusion]]）主要优化 base model 推理，对多 adapter workflow 的系统性优化几乎空白。Katz 针对「**生产 T2I workflow + 海量 adapter**」这一部署形态提出端到端 serving 系统。

## 关键观察 / 隐含假设

- **观察 1：ControlNet 与 LoRA 的瓶颈形态完全不同，不能共用一套优化策略。**
  - **依赖假设**：ControlNet 数量少（~141 个）、访问高度偏斜（top 9–11% 占 95–98% 调用）、单个体积大且 compute-heavy；LoRA 数量多（~7000+）、长尾分布（99.8% 单个占比 <1%）、compute-light 但 loading/patching 主导。
  - **可能失效场景**：若未来 adapter 生态转向少量通用 LoRA 或 ControlNet 长尾化（用户自定义 adapter 爆发），缓存策略与 BAL 的收益会显著变化。
- **观察 2：LoRA 的视觉效果主要在 denoising 后期才显现，前期 steps 可安全省略 LoRA。**
  - **依赖假设**：前 K 步（论文 profile 得 K=10）有无 LoRA 的 latent cosine similarity >0.99，对应 semantics-planning 阶段；artistic-planning 阶段才需要 LoRA。
  - **可能失效场景**：某些 LoRA 若在前几步就强干预构图（论文主要用 papercut/filmic 等风格 LoRA 验证），或 denoising step 数/scheduler 改变，最优 K 需重 profile。
- **观察 3：扩散推理 batching 几乎无收益，生产固定 batch=1；CFG 占 base model >90% 时间，latent batching 反而慢。**
  - **依赖假设**：单张 1024×1024 SDXL 已饱和高端 GPU（676T FLOPS）；条件/无条件 denoising 无依赖，拆开并行比 batch 在同一 GPU 更高效。
  - **可能失效场景**：更强 GPU 或更小分辨率模型可能重新获得 batching 收益；DiT 类模型 step 结构变化可能影响 CFG 占比。
- **假设 1**：请求间隔足够长（>1s），in-place LoRA patch 后有时间在下个请求前 patch off，无需 PEFT 的 create-and-replace 层。
  - **证据强度**：**中**——生产 trace 统计支持，但高 QPS 多租户并发下是否仍成立论文未充分讨论。

## 核心方法

Katz 在 [[Diffusers]] 之上实现，核心思路是把 adapter 开销从 Eq.(1) 的串行加载+逐步计算，压缩到近似 Eq.(2) 的「text encoder + optimized base × S steps + VAE」。

**ControlNet-as-a-Service**：将 [[ControlNet]] 从 base UNet 解耦，部署为独立可伸缩微服务，专属 GPU。利用偏斜 popularity 仅缓存 top-5~8 个高频 ControlNet 消除 loading；每步 denoising 中 UNet encoder 与 ControlNet(s) **并行执行**，仅在 UNet decoder 进入前同步一次（NVLink 下 108 MiB 传输 <1ms）。多 base model 可共享同一 ControlNet 服务。慢链路（10 Gbps）下利用相邻 step ControlNet 输出 cosine similarity >0.99，采用 **pipelined async parallelization** 用 stale output 隐藏通信。

**Bounded Asynchronous LoRA Loading (BAL)**：请求到达后异步从存储加载 [[LoRA]]，同时 base model 先跑至多 K 步无 LoRA 的 semantics-planning；K+1 步前 LoRA 必须 patch 完成（否则阻塞等待）。配合 **in-place weight merge** 替代 PEFT create-and-replace（单 LoRA 341 MiB 的 patching 从 ~2s 降到可忽略），将 LoRA loading+patching 总开销压到 ~230ms。

**Latent parallelism for [[Classifier-Free-Guidance|CFG]]**：每步将 latent 复制为 conditioned/unconditioned 两份，分别在两个 GPU 上并行 denoising 后加权聚合，替代 latent batching。同样应用于 ControlNet 内部 CFG。叠加 CUDA Graph 分段、融合 GEGLU/GroupNorm+SiLU 等 kernel 优化。

典型 1C/1L 配置用 **4 GPU**（base 2 + ControlNet 2）。实现 5.5k 行 Python + 2.4k 行 C++/CUDA；LoRA loading 走独立进程 + shared memory。深度细节见 [[atc2025-li-suyi-katz]]。

## 设计取舍

- **多 GPU 换单请求延迟**：ControlNet 并行、CFG latent parallelism 都需额外 GPU；0C/0L 场景下 KATZ 与 DistriFusion 的 **per-GPU 吞吐反而不如单 GPU Nirvana-20**（后者以质量损失为代价）。
- **质量-延迟 bound**：BAL 的 K 是离线 profile 的保守上界，过大 K 可能损质量、过小 K 无法 hide loading；async ControlNet pipeline 在慢链路上故意使用 t-1 步 stale feature，依赖逐步变化极小的假设。
- **Serving 专用 patch 路径**：放弃 PEFT 的训练友好性（独立 LoRA 层、快速 un-patch），换取 in-place merge 的延迟与显存；不适合需要在线 fine-tune 的场景。
- **边界条件**：在 NVLink/IB 高速互联、adapter 配置符合生产 trace（1–3C、1–2L）、batch=1 的 latency-sensitive T2I 服务中最优；论文未讨论 request scheduling、动态扩缩容、多租户排队。

## 实验与结果

- **生产 characterization**：阿里两个 T2I 服务 20 天 trace；ControlNet LRU top-5/8 可消除 loading miss，LoRA 即使大 cache 仍高 miss（节点请求数与 unique LoRA 数线性相关）。
- **端到端延迟**（H800，PartiPrompts P2，batch=1，无排队）：相对 Diffusers 最高 **7.8×**、相对 DistriFusion **5.7×**；adapter 增多时 KATZ 延迟近乎平稳，Diffusers 线性增长。0C/0L 下 latent parallelism + kernel 优化带来 **1.7×** vs Diffusers。
- **微基准**：ControlNet-as-a-Service 单独最高 **2.2×**（3C 时实测 2.2× vs Gustafson 理论 2.35×）；LoRA 优化后开销 ~230ms；latent parallelism 在 H800/A100/A10 分别 **1.36×/1.58×/1.71×**。
- **吞吐**：GPU-minute 图像数最高 **1.7×**（多 adapter 配置）；无 adapter 时因双 GPU 未饱和而落后。
- **质量**：CLIP/FID/SSIM 与 Diffusers 相当；75 人 user study 接受率均为 **70%**（Nirvana-10 仅 <50%）。DiT（SD3、Hunyuan-DiT）上三类设计均有效。

## Critical Analysis

### 论证链条

论文从生产 trace characterization → 分 adapter 类型施策 → 微基准 + 端到端 + 质量验证，逻辑链条完整。最强证据是 **adapter 增多时延迟曲线平坦**（Fig. 14），直接支撑「移出 critical path」的核心 claim。薄弱环节在于：端到端实验用 PartiPrompts 而非 trace replay，workload 代表性弱于 §3 characterization；且不同配置下 **GPU 数量不等**（如 2C/2L 时 KATZ 6 GPU vs DistriFusion 8 GPU），跨系统对比需结合 GPU 成本解读。

### 假设压力测试

- **LoRA 长尾 + 远程存储**：BAL 在 loading >K 步 base 执行时间时需阻塞，极端冷启动或超大 LoRA 可能回退到同步路径——论文在 A100/H800 上显示 K=10 通常足够，但未测跨地域对象存储。
- **ControlNet 并行**：依赖 ControlNet 与 UNet encoder 计算量相近；若未来 ControlNet 架构变轻或数量远超 GPU 数，并行收益递减。async pipeline 在 similarity 阈值以下可能损质量，论文仅在 10 Gbps 链路上验证。
- **已证明 vs 推断**：「无质量损失」对 sync ControlNet 并行和 BAL 有 CLIP/FID/SSIM + user study 支持；async ControlNet 仅有小样本 CLIP 33.5 vs 33.7 和视觉对比，统计功效有限。

### 实验可信度

- Baseline 选取合理：Diffusers 为 lossless 参考，Nirvana/DistriFusion 为强 base-model 优化系统；公平性上 DistriFusion 被扩展支持 ControlNet 且 GPU 数 ≥ KATZ。
- Ablation 分层清晰（§9.3–9.5 分别 isolate 三个设计），支撑设计分解。
- 缺口：无生产 trace replay 端到端实验；无 tail latency / P99 报告（仅平均延迟）；多租户并发、adapter 版本热更新、故障恢复 **论文未讨论**。

### 系统性缺陷

- **资源效率**：latency 优化以多 GPU 为代价，0C/0L 吞吐不如单 GPU 方案；未给出「每美元延迟」或「每瓦特图像数」分析。
- **运维复杂度**：ControlNet 微服务、跨 GPU 同步、LoRA 加载进程、CUDA Graph 按分辨率维护——部署与可观测性成本显著高于单进程 Diffusers，论文未量化。
- **调度正交性**：论文明确 per-request latency 优化与 request scheduling / dynamic scaling 正交可组合，但本身不解决负载峰值、adapter 版本管理、SLO 隔离。

## 局限与 Future Work

- **局限 1**：characterization 与系统均来自阿里 T2I 平台，adapter 分布、存储层次（remote distributed cache）、硬件（H800/NVLink）高度特定；结论外推到 Midjourney 式闭源栈或 edge 部署需谨慎。
- **局限 2**：K 对每对 (base model, LoRA) 离线 profile，14,500 个 LoRA 全量 profile 成本未讨论；新 LoRA 上线时的 cold-start 策略缺失。
- **局限 3**：batch=1 假设贯穿设计与评估；未探索未来 GPU 算力过剩时的 batching + adapter 共存。
- **Future work 1**：**trace-driven replay benchmark**——用生产请求序列（含 adapter 组合、到达间隔）测 P50/P99 延迟与 GPU 利用率，验证 BAL 在高 QPS 下是否仍 hide loading。
- **Future work 2**：**per-LoRA adaptive K**——在线监测 latent similarity 曲线或 LoRA 元数据，动态选择 K 而非全局固定 10，在风格类 vs 构图类 LoRA 间自动切换。
- **Future work 3**：与 [[Toppings-ATC25|Toppings]] 等 LLM adapter serving、以及 AlpaServe/Shepherd 类调度系统结合，测量「Katz 单请求优化 + 集群调度」的端到端 SLO。

## 相关

- **相关概念**：[[Diffusion-Model]]、[[ControlNet]]、[[LoRA]]、[[Classifier-Free-Guidance]]、[[Adapter-Serving]]
- **同类系统**：[[Diffusers]]、[[Nirvana-NSDI24|Nirvana]]、[[DistriFusion-CVPR24|DistriFusion]]、[[Punica-MLSys24|Punica]]、[[S-LoRA-MLSys23|S-LoRA]]
- **同会议**：[[ATC-2025]]
- **对比**：[[Toppings-ATC25|Toppings]]（同作者团队，LLM LoRA serving 用 CPU 掩盖 loading，与 Katz 的 diffusion BAL 形成 interesting 对照）