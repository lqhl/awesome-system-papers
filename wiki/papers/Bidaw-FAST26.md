---
type: paper
name: Bidaw
full_title: "Bidaw: Enhancing Key-Value Caching for Interactive LLM Serving via Bidirectional Computation–Storage Awareness"
authors: [Shipeng Hu, Guangyan Zhang, Yuqi Zhou, Yaya Wei, Ziyan Zhong, Jike Chen]
venue: FAST
year: 2026
tags: [llm-serving, kv-cache, two-tier-storage, scheduling, eviction]
source_pdf: "[[fast2026-hu-shipeng.pdf]]"
source_md: "[[fast2026-hu-shipeng]]"
---

# Bidaw: Enhancing Key-Value Caching for Interactive LLM Serving via Bidirectional Computation–Storage Awareness (FAST 2026)

> **一句话总结**：让 LLM 推理引擎与「host memory + SSD」两层 [[KV-Cache]] 存储互相感知，引擎按 I/O 延迟排队、存储用模型回答长度预测复用距离做驱逐，相比 CachedAttention/FlashGen 把交互式多轮对话的响应延迟降低最多 3.58×、吞吐提升最多 1.83×，逼近全量 KV 驻留 host memory 的理论上界。

## 问题

交互式 LLM 服务（虚拟陪伴、Duolingo 角色扮演、客服等）每个用户平均 22.4 轮对话，回填历史 KV 占 93.1% 计算量，因此普遍把历史 KV 缓存到「host memory（性能层） + SSD（容量层）」两层存储。但作者实测：现有方案 CachedAttention 和 FlashGen 在他们的百万轮对话 workload 上，比理想全 host memory 缓存延迟高 3.8×、吞吐低 2.0×。

根因是计算引擎和两层存储「互不感知」。一方面，引擎按 FCFS 调度，不知道每个请求 KV 的存储位置和大小，导致一个慢的容量层 I/O 阻塞后面快的请求；另一方面，存储驱逐只看自身访问历史，但交互式对话的 KV 时间局部性差（80% 复用距离超过 200 GB 性能层容量），传统 LRU/FIFO/queue-enhanced 命中率仅 ~20%。

## 核心方法

Bidaw 在 [[vLLM]] 之上引入「双向感知」：

- **I/O-aware request scheduling**：引擎用 dual queue 分离请求——KV 在性能层的进 ready queue（FCFS 调度），KV 在容量层的进 preparing queue 等待预取；preparing queue 内用自定义 disk-HRRN（response ratio = 1 + waiting time / KV size）兼顾「小 KV 优先」与「防大 KV 饿死」。
- **Previous-answer-based eviction**：观察到 weighted reuse distance 下界与上一轮模型回答长度强相关（Spearman 0.94–0.98），因为答案越长用户阅读思考越久。Bidaw 把 reuse distance 分桶，用一个后台「ghost cache」跑 Belady 最优策略统计每桶的 hit potential，再用上轮答案长度作为下界裁剪概率分布，驱逐 hit potential 最低的 KV。
- **Storage-efficient tensor caching**：MHA 模型里 KV 不是 cost efficiency 最高的中间张量——normalized activation（tensor 6）每单位空间能省 51.0 单位计算（KV 是 30.5），缓存它再在低优先级 CUDA stream 上转回 KV，省空间又省再算。GQA 模型 KV 已经够小，不适用。

## 关键结果

- 比 CachedAttention/FlashGen 响应延迟降低最多 3.58×（OPT-13B），吞吐提升 1.43–1.83×；P99 尾延迟降 47–57%。
- Performance layer miss rate 比 queue-enhanced 降低 57.6%，比 LRU/FIFO 降 69.9%。
- 调度开销 0.62 ms/次，驱逐 0.35 ms/次，可忽略。
- 在 ShareGPT 公开 workload 上吞吐提升 1.40×（增益小于自家 workload，因为合成的 Poisson 时间戳让答案-长度信号失效）。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、Belady 最优替换、HRRN 调度
- **同类系统**：[[vLLM]]、CachedAttention、FlashGen、HCache
- **同会议**：[[FAST-2026]]
