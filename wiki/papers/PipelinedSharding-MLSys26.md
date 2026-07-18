---
type: paper
name: PipelinedSharding
full_title: "EFFICIENT, VRAM-CONSTRAINED XLM INFERENCE ON CLIENTS"
authors: [Aditya Ukarande, Deep Shekhar, Marc Blackstein, Ram Rangan]
venue: MLSys
year: 2026
tags: [client-inference, vram, llm-serving, llama-cpp, vlm]
source_pdf: "[[eb160de1de89d9058fcb0b968dbbbd68.pdf]]"
source_md: "[[eb160de1de89d9058fcb0b968dbbbd68]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# EFFICIENT, VRAM-CONSTRAINED XLM INFERENCE ON CLIENTS (MLSys 2026)

> **一句话总结**：客户端 VRAM 预算远小于磁盘权重时，Pipelined Sharding 用 profile-guided token-tier 调度在 GPU/CPU/PCIe 间执行 shard；相对逐配置调优的 llama.cpp baseline，TTFT/TPS/E2EL 平均提升 2×/3.7×/2×，并让 77GB-on-disk 的 qwen235b 在 2G VRAM（论文定义为 2,000MB）下达到 7.7 TPS（§6–7，Fig. 2，Table 4）。

## 问题与动机

游戏/边缘 [[LLM]]/VLM（NVIDIA IGI SDK、Cosmos-Reason1）需在用户指定 VRAM 上限内交互式推理。权重远大于 VRAM，需 CPU RAM + PCIe 流式。llama.cpp 手动 CPU offload 在 MoE/KV 竞争时 TTFT 差；高分辨率 VLM 常 OOM。

## 关键观察 / 隐含假设

- **观察 1：context phase（高 token 数）与 decode phase（KV 膨胀）最优执行计划不同——token tier 应用 Static GPU-only vs Dynamic oversubscribe。**
  - **依赖假设**：benchmark profile 驱动 schedule cost model 准确。
  - **可能失效场景**：极短 prompt+长 decode 边界需在线重选 plan。

- **观察 2：在 2G VRAM（2,000MB）下，qwen235b（77GB on disk）在 1K context 达到 7.7 TPS / 2.5 秒 TTFT，在 16K context 达到 5.2 TPS / 28.8 秒 TTFT（§7，Table 4）。**
  - **依赖假设**：CPU RAM 足以容纳模型总内存需求，且 host/device 传输不会成为不可接受的瓶颈。
  - **可能失效场景**：较慢 PCIe、内存带宽或多应用 host-RAM contention。

- **观察 3：VLMOpt + pipelined sharding 使 CR1 从 vLLM 的 20G VRAM 需求降到 2G，可运行 480p–1440p image workload（§7，Table 7–8）。**
  - **依赖假设**：llama.cpp 多模态路径；vLLM baseline 多模态效率异常需知。
  - **可能失效场景**：视频输入 llama.cpp 未支持（论文仅 image）。

- **假设 1**：batch 大于 1 时 token-tier 仍可扩展，batch-wide TPS 平均 2.3×（最高 8.2×，§7，Fig. 7）。
  - **证据强度**：**强**——多 VRAM budget/ctx/batch 矩阵。

## 核心方法

**Pipelined sharding**：按层/子层 shard 在 GPU 驻留与 CPU 流式间流水线；scheduler 依 token tier、ctx len、VRAM budget 选 plan。

**VLMOpt**：将 vision weights offload 到 CPU，对 vision FlashAttention/Q 做 tiling，并分离 vision 与 language allocation lifetime，以降低峰值 VRAM（§5）。

**实现**：llama.cpp b6097 之上；面向 IGI SDK/CR1 产品路径。

## 设计取舍

- **自动 scheduler vs 手动 knob**：赢得鲁棒性，profile 前期成本。
- **CPU offload 全量 KV vs 选择性**：动态 oversubscribe 换 PCIe 压力。
- **llama.cpp vs vLLM**：客户端可部署性优先，非 datacenter 吞吐记录。
- **边界条件**：RTX 5090/4090 等 client GPU；MoE 大模型为主。

## 实验与结果

- **Interactive LLM**：相对针对每个 model/VRAM 组合选择最大可行 `-ngl` 的 llama.cpp b6097 baseline，TTFT 平均/最高提升 2×/6.7×，TPS 为 3.7×/30×，E2EL 为 2×/4.3×（§6–7，Fig. 2；cli3 RTX 5090、16-core EPYC、256GB RAM；四个模型、1K–64K context、2G–32G VRAM、batch 1、16 CPU threads）。
- **qwen235b raw result**：77GB-on-disk 的 qwen235b 在 cli3 的 2G VRAM 下，1K context 为 7.7 TPS / 2.5 秒 TTFT，16K context 为 5.2 TPS / 28.8 秒 TTFT；论文的 interactive threshold 为 5 TPS（§2、§7，Table 2/4；2G=2,000MB）。
- **Planner accuracy**：在 GPU-only、Static、Dynamic 三类 schedule 的 105 个配置上，planner 与 exhaustive measured oracle 的最优选择 105/105 一致；单计划 latency prediction 的 median error 约 10%，oracle winners 为 76/19/10（§7，Fig. 4；cli3、两个模型、PCIe Gen3/Gen5、1/16 CPU threads、4K/16K contexts）。
- **VLM feasibility**：CR1 的可运行 VRAM 从 vLLM baseline 的 20G 降至 2G；cli3 的 1440p E2EL 为 18.7 秒@2G，而 vLLM 为 9.5 秒@20G（§5、§7，Table 7–8；CR1、480p–1440p、cli2/cli3、仅 image）。论文指出 vLLM multimodal handling 有异常，因此这里仅作 VRAM feasibility 对照。
- **Batched inference**：相对各自 unified/non-unified KV 的 llama.cpp baseline，batch-wide TPS 平均提升 2.3×，unified KV 最高 8.2×、non-unified 最高 5.2×；qwen30b 在 1K context、batch 64 时达到 289 TPS（§7，Table 9，Fig. 7；cli3、两个模型、batch 4/16/64、4G/8G/16G VRAM）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Pipelined sharding 相对逐配置调优的 llama.cpp baseline 提高 TTFT/TPS/E2EL | §6–7, Fig. 2 | cli3；4 models；1K–64K contexts；2G–32G VRAM；batch 1 | strong |
| qwen235b 在 2G VRAM 下、1K/16K context 均超过 5 TPS threshold | §2, §7, Table 2/4 | qwen3-235B-A22B q2_k；cli3；batch 1；16 CPU threads；2G=2,000MB | strong |
| Planner 在 105 个配置上与 exhaustive oracle 的选择完全一致 | §7, Fig. 4 | cli3；2 models；PCIe Gen3/Gen5；1/16 threads；4K/16K contexts | strong |
| VLMOpt 将 CR1 的可运行 VRAM 从 20G 降至 2G | §5, §7, Table 7/8 | CR1；480p–1440p images；cli2/cli3；跨框架仅作 feasibility 对照 | strong |
| Batched inference 相对对应 llama.cpp baseline 平均提升 2.3× TPS | §7, Table 9, Fig. 7 | cli3；2 models；batch 4/16/64；4G/8G/16G VRAM | strong |

## Critical Analysis

### 论证链条

VRAM≪模型 → token-phase heterogeneity → profiled pipelined sharding + VLMOpt → 极端预算可交互，工程链条扎实。

### 假设压力测试

Apple Silicon/统一内存路径不同；多应用并发争用 host RAM 未测。这些是读者对未覆盖环境的外推，不是论文结论。

### 实验可信度

artifact 提供 Table 4 / Fig. 2 等复现脚本，并以论文值的 90% 为 PASS threshold；这不代表本页已在本地复现实验。vLLM 对比受其多模态实现异常影响。

### 系统性缺陷

论文未讨论安全模型权重流式、功耗热节流、Windows 驱动差异。

## 局限与 Future Work

- **局限 1**：视频 多模态未覆盖。
- **局限 2**：强依赖 llama.cpp 生态。
- **读者建议 1**：评估与 Windows GPU memory budget API 的集成；论文未将其列为 future work。
- **读者建议 2**：探索 disaggregated 云辅助 client offload；论文未覆盖该方向。

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[VLM]]、[[Edge-Inference]]
- **同类系统**：llama.cpp、IGI SDK
- **同会议**：[[MLSys-2026]]
