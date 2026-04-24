---
type: paper
name: BlitzScale
full_title: "BlitzScale: Fast and Live Large Model Autoscaling with O(1) Host Caching"
authors: [Dingyan Zhang, Haotian Wang, Yang Liu, Xingda Wei, Yizhou Shan, Rong Chen, Haibo Chen]
venue: OSDI
year: 2025
tags: [llm-inference, autoscaling, serverless, rdma, live-scaling]
source_pdf: "[[osdi25-zhang-dingyan.pdf]]"
source_md: "[[osdi25-zhang-dingyan]]"
---

# BlitzScale: Fast and Live Large Model Autoscaling with O(1) Host Caching (OSDI 2025)

> **一句话总结**：BlitzScale 借用 GPU 间未饱和的 RDMA/NVLink 计算网络做多播式参数加载、只需 O(1) 主机缓存，并首创「层粒度 live 扩容 + ZigZag 调度」让新实例加载第一层就能分担请求，在 BurstGPT / Azure 轨迹下相比 ServerlessLLM 尾延迟降 **最多 94%**，相比无扩容的 [[vLLM]]/DistServe 节省 **49%** GPU 时间。

## 问题

Model-as-a-Service 的 autoscaling 对 SLO 至关重要：BurstGPT 等真实轨迹里请求 2 秒内能爆 5×，要求扩容时间 < 500 ms 才能守住 TTFT。但 LLM 参数 10–400 GB，数据平面是瓶颈：

- SSD 只有 2–10 Gbps/GPU，远不够；
- ServerlessLLM 用 host DRAM 缓存 + PCIe (256 Gbps) 加速，但 hit rate 实测只有 40–75%，因为 MAAS 上有几百个开源模型家族 + 大量用户微调模型，不可能在每台机器都缓存全；
- 所有已有方案都 **stop-the-world**：参数没加载完新实例不能服务。

## 核心方法

BlitzScale 有两个关键洞察。

**数据平面：用计算网络多播，只需 O(1) 缓存**。GPU 间 RDMA 是 100–400 Gbps，NVLink 可达 16 Tbps，比 CPU-GPU PCIe 还快；且在 DistServe 这种通信重负载下也还有 > 40% 网络空闲。所以让已部署实例直接多播参数到新实例 → 无须任何缓存；若没有部署，host CPU 只需缓存 1 份即可广播（O(1) / model）。挑战是在线生成多播计划：作者用 **serving-guided greedy planner**，先按 NVLink 把 GPU 聚成 group 消除异构，再贪心构造 serial forwarding chain（对大块数据最优），利用 RDMA 双向特性避免与 serving 的 KV-cache 迁移冲突（e.g. PD 解耦时从 decode 实例向 prefill 实例方向加载）。

**数据平面 live 化：层粒度扩容 + ZigZag 调度**。把扩容粒度从 instance 打到 layer：新实例加载第 k 层后，overloaded 实例可以 offload 前 k 层的计算过去，然后把 activation 送回继续剩余层——即便所有层没加载完，新实例已经能提升吞吐。但 naive best-effort 会让新实例初期只能跑 1–2 层，大部分请求仍排队在旧实例。**ZigZag 调度**通过故意延迟旧实例上部分请求的后续层执行，等待新实例加载更多层后再让它处理这些请求更深的层，从而更平衡流水线切分，实测尾延迟再降 **50%**。BlitzScale 支持 [[vLLM]] 风格连续 batching 和 PD 解耦服务。

## 关键结果

- 相比 ServerlessLLM：尾 TTFT 降 **47–75%**，尾 TBT 降 **最多 94%**
- 相比无 autoscaling 的 vLLM/DistServe (按 peak 过度 provisioning)：节省 **49% GPU 时间**，无 SLO violation
- 实测网络使用率 < 60% 仍能稳定扩容，不挤占 serving
- 在 Llama3-8B / Mistral-24B / Qwen2.5-72B 三款模型上一致收益
- 开源：https://github.com/blitz-serving/blitzscale

## 相关

- **相关概念**：[[RDMA]]、[[Disaggregation]]（PD 解耦）、[[KV-Cache]]、[[Continuous-Batching]]、[[Tensor-Parallelism]]
- **同类系统**：ServerlessLLM、PipeSwitch、DeepPlan、[[vLLM]]、DistServe
- **同会议**：[[OSDI-2025]]
