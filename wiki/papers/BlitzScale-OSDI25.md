---
type: paper
name: BlitzScale
full_title: "BlitzScale: Fast and Live Large Model Autoscaling with O(1) Host Caching"
authors: [Dingyan Zhang, Haotian Wang, Yang Liu, Xingda Wei, Yizhou Shan, Rong Chen, Haibo Chen]
venue: OSDI
year: 2025
tags: [llm-serving, autoscaling, model-as-a-service, multicast, serverless, area/ai-infra]
source_pdf: "[[osdi25-zhang-dingyan.pdf]]"
source_md: "[[osdi25-zhang-dingyan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# BlitzScale：使用 O(1) 主机缓存进行快速实时大型模型自动缩放（OSDI 2025）

> **原题**：BlitzScale: Fast and Live Large Model Autoscaling with O(1) Host Caching

> **一句话总结**：MAAS 突发 5× 请求需 <500ms 扩实例但 72B 权重加载需 576 Gbps/GPU，SSD 与单机 DRAM cache miss 20–46%；BlitzScale 用 compute fabric 串行转发 multicast + 全局 O(1)/模型 host cache + 层粒度 live scaling（ZigZag pipeline），TTFT/TBT tail 比 ServerlessLLM 最高降 **94%**，GPU 用量比无自动伸缩的 [[vLLM]]/DistServe **-49%**。

## 问题与动机

Model-as-a-Service 需随 burst 扩 serving instance，但 stop-the-world 加载 10–400GB 权重太慢（Llama3-8B @10Gbps SSD ~12.8s）。ServerlessLLM 等多级 host cache 命中率仅 40–75%，多模型多 host 时 miss 更高。Compute network（200G RDMA / NVLink）serving 时利用率可低至 **7.4%**，可借用于 data plane。

## 关键观察 / 隐含假设

- **观察 1**：已有实例时 serial-forwarding multicast 传参几乎与接收者数量无关；无实例时全局每模型 O(1) host 缓存即可覆盖 MAAS 全模型集（聚合 DRAM 够大）。
  - **依赖假设**：拓扑支持高效 multicast plan；与 serving KV 传输干扰可控（否则 scale 慢 1.5×、TBT tail -50%）。
  - **可能失效场景**：纯 cold start 且网络低于 220 Gbps/GPU 时仍难满足 72B SLO（图 3）。
- **观察 2**：推理本就 layer-by-layer，扩缩可从 instance 粒度降到 layer 粒度，未载权重层可 offload 计算到正在加载的新实例（live scaling）。
  - **依赖假设**：ZigZag 调度能预见后续层到达，避免新实例初期只能算少数层导致负载仍堆在旧实例。
  - **证据强度**：中——bursty trace 上 tail latency **50%** 降（§5.2）。
- **假设 1**：BurstGPT/Azure 类 trace 代表生产 burst（2s 内 5×）。
  - **可能失效场景**：更长平稳高峰可能更接近 over-provision 而非 autoscale 收益。

## 核心方法

**Multicast planner**：模型感知、在线近最优、干扰隔离（vs 离线训练 TE 方案）。

**Live scaling**：layer-wise cooperative execution + ZigZag pipeline scheduling。

**Global parameter pool**：跨机 O(1) per-model 缓存 + RDMA/NVLink 加载。

支持 PD disaggregation 与普通 serving；Rust/C++ 平台。

## 设计取舍

- **取舍 1**：层粒度调度复杂度换 stop-the-world 消除。
- **取舍 2**：multicast 与 serving 共享 fabric，需 planner 避干扰。
- **边界条件**：Llama3-8B、Mistral-24B、Qwen2.5-72B；BurstGPT/Azure traces。

## 实验与结果

- vs ServerlessLLM：TTFT **47–75%** 缩短，TBT tail **最高 94%** 缩短。
- vs [[vLLM]]/DistServe（无 autoscale，按峰值 provisioning）：同 SLO 下 GPU **-49%**。
- ServerlessLLM cache miss **20–46%**（5min keepalive）。
- 满足 72B SLO 需 **~220 Gbps/GPU** 加载带宽（simulator）。

## 批判性分析

### 论证链条

SLO 仿真定带宽预算 → 测量 cache miss 与网络空闲 → multicast+live 设计 → 多模型 trace 端到端，逻辑紧密。49% GPU 节省相对「按峰值 over-provision」baseline，非同等 GPU 下 latency 对决。

### 假设压力测试

千模型 MAAS 全局 pool 的元数据与一致性？multicast plan NP-hard，在线启发式最坏情况？与 [[Disaggregation]] PD 下 KV 迁移峰值叠加时 fabric 瓶颈。

### 实验可信度

Trace 来自 Azure/BurstGPT 有代表性；ServerlessLLM 为直接 SOTA。vLLM 未做同 autoscale 策略对比需注意。

### 系统性缺陷

论文未讨论 partial layer 权重损坏、扩缩失败回滚；multi-tenant 公平性与计费模型未展开。

## 局限与后续工作

- **局限 1**：极 cold + 慢网络仍难达 500ms 72B SLO。
- **Future work 1**：与 speculative 加载、量化权重传输结合。
- **Future work 2**：与 [[KV-Cache]] 动态迁移联合调度。

## 相关

- **相关概念**：[[KV-Cache]]、[[Disaggregation]]
- **同类系统**：[[vLLM]]、ServerlessLLM、DistServe
- **同会议**：[[OSDI-2025]]
