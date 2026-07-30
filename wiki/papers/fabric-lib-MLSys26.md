---
type: paper
name: fabric-lib
full_title: "fabric-lib: RDMA Point-to-Point Communication for LLM Systems"
authors: [Nandor Licker, Kevin Hu, Vladimir Zaytsev, Lequn Chen]
venue: MLSys
year: 2026
tags: [rdma, p2p, disaggregation, moe, kv-cache, efa, connectx, perplexity]
source_pdf: "[[c51ce410c124a10e0db5e4b97fc2af39.pdf]]"
source_md: "[[c51ce410c124a10e0db5e4b97fc2af39]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# fabric-lib：LLM 系统的 RDMA 点对点通信（MLSys 2026）

> **原题**：fabric-lib: RDMA Point-to-Point Communication for LLM Systems

> **一句话总结**：fabric-lib 提供可靠无序 WRITEIMM/IMMCOUNTER P2P。ConnectX-7 与 EFA 的 WRITE microbenchmark 峰值为 **400Gbps**，但 small single writes 不饱和；特定 Kimi-K2-1T bf16→fp8 RL update 为 **1.2–1.3s**，不是所有 trillion-parameter updates 的固定时间。

## 问题与动机

[[NCCL]]/torch.distributed 擅长静态 collective（TP/DP/PP），但对 **动态成员**、异步初始化、非均匀 buffer（稀疏 MoE、分页 [[KV-Cache]]）不友好；SEND/RECV 原语存在但难拼出低延迟 P2P 管线。

云 [[RDMA]] 硬件分裂：NVIDIA ConnectX RC（可放松有序）vs AWS EFA SRD（天然无序）。DeepEP 依赖 ConnectX 独占的 GPUDirect Async（IBGDA）；NVSHMEM 在 EFA 上严重退化；[[Mooncake]]/NIXL EFA 支持滞后或初步。

**洞察**：两者均可提供 **reliable-but-unordered** 语义 → 用 IMMCOUNTER 而非传输有序性做完成同步。

## 关键观察 / 隐含假设

- **观察 1：完成通知不必依赖 message ordering——WRITEIMM 的 immediate 计数 + PCIe 序（payload 先于 immediate，同设备写有序）可在无序网络上保证 CPU/GPU 可见性。**
  - **依赖假设**：host-proxy 架构下 CPU 见 IMMCOUNT 后的 H2D/kernel launch 序于 NIC→GPU 数据写之后。
  - **可能失效场景**：错误 MR 注册或跨 NUMA 配置不当导致竞态；论文依赖 [[RDMA]]/PCIe 规范行为。

- **观察 2：EFA 单 NIC 100G，p5 需 4× NIC 聚合才满 400 Gbps；TransferEngine 须透明 shard/rotate WRITE。**
  - **依赖假设**：peer 间 NIC 数一致；domain worker pin 到正确 NUMA。
  - **可能失效场景**：异构 NIC 拓扑需额外均衡逻辑。

- **观察 3：集体式 RL 权重更新瓶颈在 training rank0 NIC；P2P 每 training GPU 直接 WRITE 到 inference GPU 可用满集群带宽。**
  - **证据强度**：**高**——Kimi-K2 1T / DeepSeek V3 671B / Qwen3 235B，256 train → 128 infer，**1.3s** vs 既有框架数十–数百秒。

- **假设 1：分页 KvCache + layer-wise UVM watcher 可在 CUDA Graph 下逐层 [[RDMA]]，无需显式 prefiller 完成消息。**
  - **依赖假设**：decoder 预知 transfer 次数，`expect_imm_count` 即可开 decode。

## 核心方法

**TransferEngine**（Rust）：每 GPU 一 worker，管理 1–4 DOMAIN（NIC）；API 含 `reg_mr`、`submit_send/recvs`、`submit_single_write`、`submit_paged_writes`、`submit_scatter`、`submit_barrier`、`alloc_uvm_watcher`。

**IMMCOUNTER**：per-immediate 原子计数，CQ 事件递增；回调或 flag 通知；替代有序假设。

**硬件优化**：
- EFA：libfabric、WR templating、强制有效 descriptor（immediate-only 零长写）。
- ConnectX-7：UD 握手建 RC QP；SEND/RECV 与 WRITE 分 QP 避免 completion 消费冲突；WR chaining（≤4）、`IBV_ACCESS_RELAXED_ORDERING`。

**用例**：
1. **KvCache transfer**：chunked prefill 每层 attention 后 UVM watcher 触发 `paged_writes`；GQA/MLA 布局与 sharding 适配；取消/心跳处理生产复杂度。
2. **RL weight update**：静态 schedule 映射 train→infer 参数；四段 pipeline（H2D、prepare、[[RDMA]]、barrier）重叠；FSDP mesh group 顺序。
3. **MoE dispatch/combine**：scatter/barrier 封装；ConnectX decode 延迟 ≥ DeepEP；EFA 首次可用 latency。

## 设计取舍

- **Host-proxy vs IBGDA**：放弃 GPU 发起 [[RDMA]] 以换 EFA 可移植；MoE 仍用 host 线程仍达 SOTA（ConnectX）。
- **无序语义 vs 简化 API**：用户须用 IMMCOUNTER 协调，无跨 op 有序保证。
- **开源**（Perplexity `pplx-garden`）vs 生态整合：需 inference engine（[[vLLM]]/[[SGLang]] 等）适配层。
- **仅 WRITE 路径优化**：READ/atomic 明确排除（延迟不适合）。

## 实验与结果

**指标、基线与边界**：WRITE bandwidth、weight-update wall-clock、TPOT/tokens/s、host dispatch latency；fabric-lib vs NIXL/SPDK-like baseline/pplx-kernels/DeepEP；single/paged writes、EFA/ConnectX、specified RL/MoE/KvCache setups（§7）。

- ConnectX-7/EFA peak **400Gbps**；single WRITE 要至少 **16MiB** 饱和，256KiB 时 EFA/ConnectX 为 **54/116Gbps**（§7.1，Fig.8/Table2）。
- Kimi-K2-1T 256 bf16 training GPUs→128 fp8 inference GPUs：**1.2–1.3s**，full tensor **518ms**、rank sync **357ms**（§5、§7.3）。
- Qwen3-235B/H200 TP4 layer-by-layer KvCache transfer 可被计算隐藏；1024 pages 尚不饱和 RDMA，非零 TTFT 保证（§7.2，Table3）。
- DeepSeek-V3 MTP decode：EFA 比 pplx-kernels **3–6×** tokens/s；ConnectX-7 与 DeepEP match/slightly exceed（§7.4）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| peak bandwidth 有 write-size 边界 | 400Gbps；16MiB vs256KiB54/116Gbps | single/paged WRITE、CX7/EFA、vs NIXL | §7.1 Fig.8/Table2 | high |
| RL update 为特定 parallelism 配置 | 1.2–1.3s、518/357ms | Kimi-K2 256→128、bf16→fp8 | §5，§7.3 Table5 | high |
| Kv transfer 被计算隐藏限于指定 engine | 1024 pages未饱和 | Qwen3-235B/H200 TP4、32KiB/128-token pages | §7.2 Table3 | high |
| MoE 结果按 fabric/baseline 区分 | EFA3–6×；CX7 match/slightly exceed | DeepSeek-V3 MTP decode、EP=DP64 | §7.4 | high |
| host proxy dispatch 有 EP 相关开销 | first WRITE<1.5µs，post<10/<28µs | EP64、p50、CX7/EFA | §7.4.6 Tables8–9 | high |

## 批判性分析

### 论证链条

论文从 LLM 新兴 workload（[[Disaggregation]] inference、[[MoE]] dispatch、异步 RL 权重推送）对 **动态成员、非均匀 buffer、单向突发写** 的需求出发，论证 [[NCCL]]/torch.distributed 的静态 collective 不够用，而现有 P2P 方案（DeepEP、NVSHMEM、[[Mooncake]]、NIXL）被 **multi-cloud [[RDMA]] 碎片化**割裂——ConnectX 独占 IBGDA、EFA 上 NVSHMEM 退化。核心洞察是 ConnectX RC 与 EFA SRD 均可提供 **reliable-but-unordered** 语义，故用 WRITEIMM + **IMMCOUNTER** 替代传输有序性做完成同步，在 host-proxy 架构下换得 **ConnectX-7 与 EFA 双栈可移植**。三条生产用例（分页 [[KV-Cache]] 逐层 [[RDMA]]、万亿参数 RL **1.3s** 权重推送、MoE decode 媲美 DeepEP）闭合「抽象 → 实现 → 部署」链条。定位是 **collective 补充层**，非 [[NCCL]] 替代品——适合 membership 动态、稀疏/分页、单向突发写；需 inference engine（[[vLLM]]/[[SGLang]] 等）适配层集成。

### 假设压力测试

- **IMMCOUNTER 正确性假设**：PCIe 序保证 payload 先于 immediate，CPU/GPU 见计数后的 H2D/kernel launch 序于 NIC→GPU 数据写之后；**失效场景**为错误 MR 注册、跨 NUMA 配置不当或违反规范的竞态。
- **Host-proxy vs IBGDA**：放弃 GPU 发起 [[RDMA]] 以换 EFA 可移植；**压力点**在 ConnectX 极限延迟可能仍逊于 DeepEP GPU-initiated，MoE 等延迟敏感路径存在天花板。
- **EFA 多 NIC 假设**：peer 间 NIC 数一致，TransferEngine 透明 shard/rotate 可满 **400 Gbps**；**失效场景**为异构 NIC 拓扑需额外均衡。
- **KvCache 无显式完成消息假设**：分页 KvCache + layer-wise UVM watcher + `expect_imm_count` 可在 CUDA Graph 下工作；**压力点**在 cancel、heartbeat、MR 生命周期等生产运维复杂度，正文轻量、细节在附录。
- **生态竞争假设**：相对 NIXL v0.6.1+ EFA 支持、[[Mooncake]] Store 等方案的差异化仍成立；**随时间变化**，外推需关注上游生态追赶；Perplexity 内部栈，外部复现依赖 ConnectX-7/EFA 硬件。

### 实验可信度

- **带宽 claim**：ConnectX-7 与 EFA 均达 **400 Gbps** 峰值，直接支撑双栈可移植叙事；RL 万亿级模型 **1.3s**（256 train → 128 infer）相对既有框架数十–数百秒，证据强度高、生产场景具体。
- **MoE/KvCache**：ConnectX decode 延迟 competitive with DeepEP、EFA 上首个 viable MoE P2P、生产 [[Disaggregation]] 全 CUDA Graph——覆盖 inference/train/MoE 三角，但 MoE 对比维度与 workload 细节有限，EFA 路径缺乏与 DeepEP 同等的长期生产数据。
- **可重复性**：开源 Perplexity `pplx-garden`，但 RL/KvCache case 绑定内部调度与 [[vLLM]]/[[TensorRT-LLM]] 集成栈，独立团队复现门槛高。
- **遗漏风险**：READ/atomic 明确排除；fault-tolerance 形式化与自动化 schedule 生成未验证；与 [[Mooncake]] Store、3FS 等分布式 KV 协同仅 future work 提及。

## 局限与后续工作

- GPU-initiated 路径在支持硬件上的可选后端。
- 更多 cloud NIC（eRDMA、Google Falcon）验证。
- 与 [[Mooncake]] Store、3FS 等分布式 KV 存储协同。
- 自动化 schedule 生成与 fault-tolerance 形式化。

## 相关

- **Disaggregation**：[[DistServe]]、Splitwise、[[Mooncake]]
- **MoE 通信**：DeepEP、NVSHMEM
- **硬件**：ConnectX-7、AWS EFA、[[RDMA]]、GPUDirect
- **集成**：[[vLLM]]、[[SGLang]]、[[TensorRT-LLM]]、RL 框架（veRL、OpenRLHF）
