---
type: paper
name: Mycroft
full_title: "Mycroft: Tracing Dependencies in Collective Communication Towards Reliable LLM Training"
authors: [Yangtao Deng, Lei Zhang, Qinlong Wang, Xiaoyun Zhi, Xinlei Zhang, Zhuo Jiang, Haohan Xu, Lei Wang, Zuquan Song, Gaohong Liu, Yang Bai, Shuguang Wang, Wencong Xiao, Jianxi Ye, Minlan Yu, Hong Xu]
venue: SOSP
year: 2025
tags: [llm-training, collective-communication, tracing, nccl, reliability]
source_pdf: "[[3731569.3764848.pdf]]"
source_md: "[[3731569.3764848]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# Mycroft: Tracing Dependencies in Collective Communication Towards Reliable LLM Training (SOSP 2025)

> **一句话总结**：在 [[NCCL]] collective 内部做轻量依赖追踪，**90%** 异常 **15s** 内检出、**60%** **20s** 内定位根因 GPU，字节生产部署 6 个月 Coll 级问题检出率 **100%**。

## 问题与动机

LLM 训练依赖 [[Data-Parallelism]]/[[Tensor-Parallelism]]/[[Pipeline-Parallelism]] 下大量 CollOp（ReduceScatter、AllGather…）。CCL 是黑盒：gray failure（通信 hang）和 fail-slow 只表现为全局 timeout 或均匀降速，难定位 culprit rank。Op-level（Kineto）、kernel-level（Nsight）、RDMA-level（Aegis）粒度不足或开销过大。

## 关键观察 / 隐含假设

- **观察 1**：CollOp 内部 control/data dependency（chunk、channel、algorithm step）携带足够信息做根因定位，且可在低开销下采样追踪。
  - **依赖假设**：训练框架 Coll 调用模式相对固定；instrumentation 不破坏 NCCL 性能路径。
  - **可能失效场景**：自定义 MSCCL 算法、频繁 algorithm 切换；极短 CollOp 追踪粒度不足。
  - **证据强度**：强——生产 6 个月 + fault injection 双验证。
- **观察 2**：gray failure 在 Op-level 超时前，内部 state 已停滞，Coll-level trace 可提前 **15s** 级检测。
  - **依赖假设**：trigger 机制能识别 stall pattern 而非仅 wall-clock timeout。
  - **可能失效场景**：缓慢 degrade 而非完全 stall，需与 MFU 监控联合。
  - **证据强度**：中——90%/60% 统计，case study 补充。
- **假设 1**：依赖驱动的 RCA 无需全量 CUDA timeline 即可定位 GPU/NIC。
  - **证据强度**：强——比 NPKit（带宽降 2/3）等低开销。

## 核心方法

Mycroft：轻量分布式 tracing + dependency-driven root cause analysis。

- 捕获 Coll 内部 state 与 chunk 级依赖
- Trigger 机制在异常模式时启动细粒度 trace
- 聚合多 rank trace 做 distributed analysis

与 ByteDance 其他 debug 系统（如 [[ByteRobust]] 栈）集成。

## 设计取舍

- **取舍 1**：Coll-level 专精，不替代 Op/kernel 全栈 profiler。
- **取舍 2**：需 CCL 源码或 hook 点合作（NCCL/RCCL）。
- **边界条件**：NCCL 系 Coll；自定义通信库需重新插桩。

## 实验与结果

- 32×A100 testbed：开销低于 GREYHOUND 等且 observability 更强
- Fault injection：多种 HW/SW 故障可检测+定位
- 生产（2024.10 起）：Coll 问题 **100%** 检出；**90%** <15s 检测、**60%** <20s 根因 GPU
- 真实 case： defective GPU 导致全局 hang，原需 6h+ 复现

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Coll traces distinguish seven injected fault types | seven single-machine injections identify rank/component (§7.1, Fig.7–9) | 32 A100/4 machines, Megatron GPT; one injected machine | high |
| Injection alert latency is bounded in testbed | no more than 13s (§7.1, Fig.8) | centralized RCA testbed, not production percentile | high |
| Iteration overhead is below 1% | GPT 1116→1119ms; NVRx 1124ms, Nsight trace 1125ms (§7.3, Fig.11) | 32×A100 tool-run-separately comparison | high |
| Trace storage is low in reported experiment | 46.8KB/iteration/machine vs Nsight 15MB (§7.3) | 1,200-machine value is an extrapolation | high |
| Production detection/RCA timings are reported | 90% detections within 15s; about 60% RCA within 20s (§7.4, Fig.12) | Nov–Dec 2024 jobs >128 GPUs; labels do not establish FPR/accuracy | high |

## Critical Analysis

### 论证链条

「CCL 黑盒 → 缺 Coll-level observability → Mycroft」直接。与 ByteRobust 形成 detection(localization) vs communication-internal RCA 互补。

### 假设压力测试

- 400Gbps+ 更大 message 时 trace 存储压力？
- 多 tenant 集群是否可部署？论文聚焦单 job。
- 40% case 无法在 20s 定位根因，后续路径未量化。

### 实验可信度

生产统计可信度高。Testbed 32 GPU 相对生产万卡 scale-down，RCA 算法 scale 外推需谨慎。

### 系统性缺陷

论文未讨论：trace 数据隐私；长期存储成本；与自动 remediation（驱逐坏机）闭环集成细节。

## 局限与 Future Work

- **局限 1**：依赖 NCCL 生态插桩。
- **局限 2**：40% case 根因定位 >20s 或失败。
- **Future work 1**：与 scheduler 联动自动 isolate culprit rank，缩短人工介入。

## 相关

- **相关概念**：[[NCCL]]、[[ETTR]]、collective communication、gray failure
- **同类系统**：[[ByteRobust]]、Kineto、Aegis、GREYHOUND
- **同会议**：[[SOSP-2025]]
