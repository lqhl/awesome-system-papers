---
type: paper
name: FuseLink
full_title: "Enabling Efficient GPU Communication over Multiple NICs with FuseLink"
authors: [Zhenghang Ren, Yuxuan Li, Zilong Wang, Xinyang Huang, Wenxue Li, et al.]
venue: OSDI
year: 2025
tags: [gpu-communication, rdma, nccl, multi-nic, nvlink]
source_pdf: "[[osdi25-ren.pdf]]"
source_md: "[[osdi25-ren]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 使用 FuseLink 在多个 NIC 上实现高效 GPU 通信（OSDI 2025）

> **原题**：Enabling Efficient GPU Communication over Multiple NICs with FuseLink

> **一句话总结**：GPU-NIC 静态绑定在 [[Disaggregation]] LLM serving、[[MoE]] [[Expert-Parallelism]]、DLRM 等动态流量下 NIC 利用率仅 13–82%，FuseLink 用 NVLink 运行时中继聚合多 NIC 为「融合链路」，两机 GPU 带宽 212 GB/s，TTFT 快 2.73×。

## 问题与动机

ML 集群常 GPU:NIC=1:1 PCIe 直连，仅 3D 均衡训练能吃满。Disaggregated serving、MoE all-to-all、DLRM embedding 传输导致 hot-spot NIC 与 idle NIC 并存——平均利用率 13–53%（serving）、29–65%（MoE）、59–82%（DLRM）。NCCL 仅用 NVLink 绕过**单**条 suboptimal PCIe 到**固定** indirect NIC，无法动态聚合多 NIC 带宽。

## 关键观察 / 隐含假设

- **观察 1**：动态流量不满足「直连 NIC + 并发传输 + 等量流量」三条件→性能被最忙 GPU-NIC 对 bound（Table 1）。
  - **依赖假设**：8×Hopper + 8×400G NIC + 八 lane NVLink 代表未来大型 AI 机框（NVL72 类）。
  - **可能失效场景**：流量已均衡的 [[Tensor-Parallelism]] 训练；NVLink 拓扑不全连通。
- **观察 2**：ML 消息少连接、大块分片——使运行时 NIC 调度 + NVLink relay 可行；D1 内存 remap relay 比 D2 CPU async copy 间接 NIC 吞吐更高。
  - **依赖假设**：CUDA 统一 VA 支持 buffer remap；receiver credit 带 idle NIC 信息。
  - **可能失效场景**：极短消息 remap 摊销差；多租户同时抢 indirect NIC 时 interruption-free 策略保守降利用率。
- **假设 1**：集成 NCCL 替换默认网络层即可无应用改动受益。
  - **证据强度**：强；端到端 LLM/MoE/DLRM 验证。

## 核心方法

**架构**：sender 监控本地 NIC 负载 + receiver credit 中的 idle NIC；选最优 NIC 集；via NVLink remap 将 network buffer 映射到 router GPU 再 RDMA。

**四组件**：高效 relay（§4.1 D1 remap）、无中断 relay（§4.2 仅 idle 时用 indirect NIC）、降 NIC 争用（§4.3 优先级）、高效调度（§4.4 credit+负载）。

**部署**：RDMA 原语独立网络层；NCCL 插件式集成。

## 设计取舍

- **取舍 1**：不用 traffic spraying 到所有 NIC——避免打断 peer 直连 NIC 通信（Figure 7）。
- **取舍 2**：relay buffer 占用 router GPU 显存——OOM 风险用 best-effort 限制缓解。
- **边界条件**：Nvidia NCCL 栈；八 NIC 400G 实验机。

## 实验与结果

- 两机 GPU 带宽：212 GB/s（超八 lane NVLink 理论）；相对 baseline 4.31×（Table 2 组件累加）。
- LLM serving TTFT：1.04–2.73×；MoE 训练 1.3×；DLRM 1.2×。
- 多租户容器：比 TGS 多收割 2.74× GPU 资源且保 SLO。
- NIC 利用率：接近「理想全 NIC 可用」曲线（Figure 2a）。

## 批判性分析

### 论证链条

「静态绑定→动态调度+NVLink 缝合内外网」对 imbalance 观察准确。D1 vs D2 benchmark 支撑 remap 选择，非拍脑袋。NCCL 集成降低采纳门槛——系统论文完整度高。

### 假设压力测试

- **已证明**：三类代表性 dynamic ML workload 端到端加速；microbenchmark 组件分解可信。
- **可能失效**：全机所有 GPU 同时打满 inter-server 时「idle NIC」消失；AMD/非 NVLink 平台需重做 relay；PCIe root 争用上限仍存。
- **论文未覆盖**：与 UCX/MPI 通用栈对比；WAN 多跳；安全/租户隔离下的 credit 伪造。

### 实验可信度

真实 400G NIC + Hopper；trace-driven serving。理想利用率曲线是估算非实测上限。部分 speedup 在流量较轻时接近 1.04× 下限。

### 系统性缺陷

依赖 NVLink + CUDA VA；router GPU 显存/带宽副作用；调度复杂度；非 Nvidia 生态移植成本高；论文未量化 remap 失败/回退路径。

## 局限与后续工作

- **局限 1**：Nvidia/NCCL 绑定；router OOM 与争用需运维策略。
- **局限 2**：全员通信时增益收窄。
- **Future work 1**：NVL72 规模全机仿真与生产 trace 长期 NIC 利用率。
- **Future work 2**：与 [[Disaggregation]] prefill/decode 调度器协同的 credit 协议。

## 相关

- **相关概念**：[[RDMA]]、[[MoE]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]、[[Disaggregation]]
- **同类系统**：NCCL、UCX、TGS
- **同会议**：[[OSDI-2025]]
