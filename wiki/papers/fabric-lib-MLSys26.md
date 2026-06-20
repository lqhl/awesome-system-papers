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
---

# fabric-lib: RDMA Point-to-Point Communication for LLM Systems (MLSys 2026)

> **一句话总结**：LLM 新兴模式（disaggregated inference、[[MoE]] dispatch、异步 RL 权重推送）需要灵活 P2P，但 DeepEP/NVSHMEM/Mooncake/NIXL 等多锁 ConnectX 或缺 EFA 支持；fabric-lib 抽象 **可靠无序** 语义的 WRITEIMM + **IMMCOUNTER** 完成通知，ConnectX-7 与 AWS EFA 均达 **400 Gbps** 峰值，生产验证 KvCache 迁移、**1.3s** 万亿参数 RL 权重更新、MoE decode 延迟媲美/超越 DeepEP（EFA 首个可用实现）。

## 问题与动机

[[NCCL]]/torch.distributed 擅长静态 collective（TP/DP/PP），但对 **动态成员**、异步初始化、非均匀 buffer（稀疏 MoE、分页 [[KV-Cache]]）不友好；SEND/RECV 原语存在但难拼出低延迟 P2P 管线。

云 RDMA 硬件分裂：NVIDIA ConnectX RC（可放松有序）vs AWS EFA SRD（天然无序）。DeepEP 依赖 ConnectX 独占的 GPUDirect Async（IBGDA）；NVSHMEM 在 EFA 上严重退化；Mooncake/NIXL EFA 支持滞后或初步。

**洞察**：两者均可提供 **reliable-but-unordered** 语义 → 用 IMMCOUNTER 而非传输有序性做完成同步。

## 关键观察 / 隐含假设

- **观察 1：完成通知不必依赖 message ordering——WRITEIMM 的 immediate 计数 + PCIe 序（payload 先于 immediate，同设备写有序）可在无序网络上保证 CPU/GPU 可见性。**
  - **依赖假设**：host-proxy 架构下 CPU 见 IMMCOUNT 后的 H2D/kernel launch 序于 NIC→GPU 数据写之后。
  - **可能失效场景**：错误 MR 注册或跨 NUMA 配置不当导致竞态；论文依赖 RDMA/PCIe 规范行为。

- **观察 2：EFA 单 NIC 100G，p5 需 **4×** NIC 聚合才满 **400 Gbps**；TransferEngine 须透明 shard/rotate WRITE。**
  - **依赖假设**：peer 间 NIC 数一致；domain worker pin 到正确 NUMA。
  - **可能失效场景**：异构 NIC 拓扑需额外均衡逻辑。

- **观察 3：集体式 RL 权重更新瓶颈在 training rank0 NIC；P2P 每 training GPU 直接 WRITE 到 inference GPU 可用满集群带宽。**
  - **证据强度**：**高**——Kimi-K2 1T / DeepSeek V3 671B / Qwen3 235B，256 train → 128 infer，**1.3s** vs 既有框架数十–数百秒。

- **假设 1：分页 KvCache + layer-wise UVM watcher 可在 CUDA Graph 下逐层 RDMA，无需显式 prefiller 完成消息。**
  - **依赖假设**：decoder 预知 transfer 次数，`expect_imm_count` 即可开 decode。

## 核心方法

**TransferEngine**（Rust）：每 GPU 一 worker，管理 1–4 DOMAIN（NIC）；API 含 `reg_mr`、`submit_send/recvs`、`submit_single_write`、`submit_paged_writes`、`submit_scatter`、`submit_barrier`、`alloc_uvm_watcher`。

**IMMCOUNTER**：per-immediate 原子计数，CQ 事件递增；回调或 flag 通知；替代有序假设。

**硬件优化**：
- EFA：libfabric、WR templating、强制有效 descriptor（immediate-only 零长写）。
- ConnectX-7：UD 握手建 RC QP；SEND/RECV 与 WRITE 分 QP 避免 completion 消费冲突；WR chaining（≤4）、`IBV_ACCESS_RELAXED_ORDERING`。

**用例**：
1. **KvCache transfer**：chunked prefill 每层 attention 后 UVM watcher 触发 `paged_writes`；GQA/MLA 布局与 sharding 适配；取消/心跳处理生产复杂度。
2. **RL weight update**：静态 schedule 映射 train→infer 参数；四段 pipeline（H2D、prepare、RDMA、barrier）重叠；FSDP mesh group 顺序。
3. **MoE dispatch/combine**：scatter/barrier 封装；ConnectX decode 延迟 ≥ DeepEP；EFA 首次可用 latency。

## 设计取舍

- **Host-proxy vs IBGDA**：放弃 GPU 发起 RDMA 以换 EFA 可移植；MoE 仍用 host 线程仍达 SOTA（ConnectX）。
- **无序语义 vs 简化 API**：用户须用 IMMCOUNTER 协调，无跨 op 有序保证。
- **开源**（Perplexity `pplx-garden`）vs 生态整合：需 inference engine（[[vLLM]]/[[SGLang]] 等）适配层。
- **仅 WRITE 路径优化**：READ/atomic 明确排除（延迟不适合）。

## 实验与结果

- **峰值带宽**：ConnectX-7 与 EFA 均 **400 Gbps**。
- **RL**：万亿级模型跨机 **1.3s** 权重推送（bf16 train → fp8 infer）。
- **MoE**：ConnectX-7 decode 延迟 competitive with DeepEP；EFA 上首个 viable MoE P2P。
- **KvCache**：EFA 生产 disaggregated inference，全 CUDA Graph，layer-by-layer 低延迟。

## Critical Analysis

**强项**：直面 **multi-cloud RDMA 碎片化**这一 LLM infra 真问题；IMMCOUNTER 是把 ConnectX/EFA 共性提炼成可移植抽象的好例子；三个 production case 覆盖 inference/train/MoE 三角。

**弱点**：IBGDA 路径放弃可能在 ConnectX 上极限延迟仍逊于 DeepEP GPU-initiated；运维复杂度（cancel、heartbeat、MR 生命周期）主要在附录；与 NIXL v0.6.1+ EFA 支持的竞争关系随时间变化；论文 Perplexity 内部栈，外部复现需硬件。

**定位**：collective 的补充层，不是 NCCL 替代品——适合 membership 动态、稀疏/分页、单向突发写。

## 局限与 Future Work

- GPU-initiated 路径在支持硬件上的可选后端。
- 更多 cloud NIC（eRDMA、Google Falcon）验证。
- 与 Mooncake Store、3FS 等分布式 KV 存储协同。
- 自动化 schedule 生成与 fault-tolerance 形式化。

## 相关

- **Disaggregation**：[[DistServe]]、Splitwise、[[Mooncake]]
- **MoE 通信**：DeepEP、NVSHMEM
- **硬件**：ConnectX-7、AWS EFA、RDMA、GPUDirect
- **集成**：[[vLLM]]、[[SGLang]]、TensorRT-LLM、RL 框架（veRL、OpenRLHF）