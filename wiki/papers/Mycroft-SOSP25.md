---
type: paper
name: Mycroft
full_title: "Mycroft: Tracing Dependencies in Collective Communication Towards Reliable LLM Training"
authors: [Yangtao Deng, Lei Zhang, Qinlong Wang, Xiaoyun Zhi, Xinlei Zhang, et al.]
venue: SOSP
year: 2025
tags: [llm-training, reliability, distributed-tracing, collective-communication, nccl]
source_pdf: "[[3731569.3764848.pdf]]"
source_md: "[[3731569.3764848]]"
---

# Mycroft: Tracing Dependencies in Collective Communication Towards Reliable LLM Training (SOSP 2025)

> **一句话总结**:通过 NCCL 侧的 flow-level + chunk-level 轻量 instrumentation 暴露 CCL 内部 control/data 依赖,在 ByteDance 生产上部署 6 个月,90% 情况下 15 秒内检测异常、60% 情况下 20 秒内定位 root cause GPU。

## 问题

LLM 训练万级 GPU 训数周数月,Microsoft 每 45 分钟一次故障、Meta Llama 3 54 天 419 次中断、ByteDance 每天至少一次故障。跑 DP+PP+TP 混合并行时,gray failure(无报警的 stuck,如 ReduceScatter 卡住)和 fail-slow 常常导致 NCCL 10 分钟 timeout 才被发现,期间 GPU 空转、根因难查。

现有观测工具分三档都不够:(1) **Op-level**(Kineto、[[Chakra]]、GREYHOUND)在 PyTorch API 层看 op 起止时间,op 卡住时没有内部状态;(2) **Kernel-level**(Nsight、NPKit、NVRx、XPUTIMER)靠 CUDA profiler,开销大(NPKit 让总线带宽掉 2/3),且仍不能看到 RDMA/网络内部;(3) **RDMA-level**(Aegis)只看 work request 统计,跟不上异常跨 GPU 的传播。

## 核心方法

**Coll-level tracing 两粒度**:(1) **Flow-level**——NCCL 的一个 CollOp 的多个 flow(QP、网络路径)单独追踪,因为 LLM 训练的网络拓扑是 flow 级定义的,flow 间短时 jitter/congestion 在 op 聚合下不可见;(2) **Chunk-level**——最小传输单元(几 MB)不记时间戳(太贵),而是周期性聚合系统状态(GPU_ready、RDMA_transmitted、RDMA_done 计数),在短时间窗内量化 CPU/GPU/RDMA 组件的 operational 进度。

**轻量 instrumentation + trigger**:NCCL proxy 线程里插桩,采样 IP 列表周期性查询 "最近 T 内有无 CollOp 完成 / 吞吐是否腰斩 / op 间隔是否翻倍",触发后才进入详细 dependency 分析,平时几乎零开销。

**Dependency-driven root cause analysis**:建模三类依赖——intra-node(CPU/GPU/NIC/PCIe 控制流)、inter-node(ring/tree topology 的上下游 synchronization,例如 AllGather 中 rank 0 慢导致 rank 1-2 级联延迟)、computation-communication(ReduceScatter/AllReduce 的 Reduce kernel 被同节点 workload 挤占)。发现某 op stuck 后沿这些依赖反向 traversal,锁定 culprit rank。

## 关键结果

- ByteDance 部署 6+ 个月,100% 成功率检测 Coll 级问题
- 90% case 15 秒内检测异常,60% case 20 秒内定位到 root-cause GPU
- 开销显著低于 XPUTIMER、NVRx 等,32× A100 测试床验证
- 故障注入实验覆盖常见硬件/软件问题,全部能检测 + 定位

## 相关

- **相关概念**:[[NCCL]]、[[RDMA]]、[[Collective-Communication]]、[[Distributed-Tracing]]、[[Fail-Slow]]
- **同类系统**:[[Chakra]]、XPUTIMER、Aegis、NVRx、NPKit、Nsight
- **同会议**:[[SOSP-2025]]
