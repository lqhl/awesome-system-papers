---
type: concept
aliases: [prefix caching, Prefix Caching, prefix-cache, prefix cache, prompt caching, context reuse]
parent: "[[KV-Cache]]"
last_updated: 2026-08-14
tags: [llm-inference, kv-cache, caching, prefill]
---

# Prefix-Caching

> 前缀缓存（prefix caching）把已经计算过的提示词前缀所对应的 [[KV-Cache]] 留下来。后续请求若具有相同前缀，就只计算新增后缀。它省掉的是 prefill 计算，不是 decode 计算。

## 核心思想

一次安全、有效的前缀复用至少包含四步：

1. **确定身份和有效性。** 缓存项不能只用文本做 key。模型权重及版本、tokenizer、adapter、位置编号、KV 精度和布局都必须兼容。多租户系统还要把租户或授权域放进 namespace。
2. **寻找最长可复用部分。** 简单实现按固定 block 哈希；[[RadixAttention]] 用 radix tree 保存共享 token 路径；离线批处理还可以先看完整批次，再构造全局 prefix tree。
3. **让 KV 真正可用。** KV 若仍在本 GPU，可以共享物理 block，并用 copy-on-write 处理分叉；若在 CPU、SSD 或远端节点，还要搬运、重排并映射到当前执行引擎。
4. **决定缓存和执行顺序。** admission、eviction、请求路由和 batch 调度会共同决定命中率，以及命中的 KV 是否能在请求开始前准备好。

“精确前缀复用”和更宽泛的“上下文复用”需要分开：

- **精确复用**要求 token 序列及其位置一致，因而可以直接复用 KV，语义最清楚。
- **结构化复用**允许应用声明某些上下文块可以换序，再由系统把它们整理成更容易命中的顺序；正确性依赖应用给出的语义约束。
- **近似复用**允许复用不是完全相同上下文产生的 KV，可能提高命中率，但必须单独验证模型质量。

[[vLLM-SOSP23|vLLM]] 的分页 block 和 copy-on-write 让多个请求可以共享前缀而不复制整段 KV；[[SGLang-NeurIPS24|SGLang]] 的 [[RadixAttention]] 则让共享路径成为调度器可见的数据结构。两者解决的是引擎内复用。[[LMCache-arXiv25|LMCache]]、[[Strata-OSDI26|Strata]] 等工作还处理跨引擎和跨存储层的 KV。

## 为什么重要

长上下文、[[RAG]] 和 agent 工作流经常重复 system prompt、历史对话、工具说明或检索文档。若每次都重做 prefill，重复 token 会直接增加算力、TTFT 和能耗。前缀缓存因此可能同时减少计算和显存写入。

但“上下文看起来重复”不等于“精确前缀能命中”。[[KVCacheInTheWild-ATC25|KVCacheInTheWild]] 在生产 trace 中测得理想命中率约为 54%–62%，并发现最热的 10% block 贡献了 77% 的复用。这个结果说明真实复用高度偏斜，也低于许多合成负载给人的印象。该论文提出的 workload-aware 策略相对最佳对照只多得到 1.5%–3.9% 命中率，却把 QTTFT（queued TTFT）降低 28.3%–41.9%；这也说明命中率本身不是最终目标。

扩容到 CPU、SSD 或远端存储也不一定更快。[[LMCache-arXiv25|LMCache]] 的一组 32 Gbps 网络实验中，直到上下文超过约 256K token，远端加载才优于重新 prefill。这个交叉点依赖模型、硬件、网络和 KV 格式，不能当成通用阈值。

## 关键观察 / 隐含假设

### 1. 生产复用与合成复用差别很大

[[KVCacheInTheWild-ATC25|KVCacheInTheWild]] 发现复用集中在少量热 block，跨用户命中几乎不存在，而且某条 trace 中 block 生存期的 P99 只有 97 秒。这支持短期、用户内的复用策略，不支持“所有租户共享一个巨大缓存就会自然获得高命中率”的假设。其数字来自特定生产服务，仍需在其他业务和模型上复核。

### 2. 内容相同，顺序不同，精确前缀仍会失败

[[ContextPilot-MLSys26|ContextPilot]] 报告，在其 RAG 设置中，原始精确前缀命中率只有约 5%；重要原因是相同文档被检索出来后顺序不同。它通过对齐、去重和注解，在部分配置中把命中率提高到 38%–60%。收益依赖模型能正确理解位置或顺序注解，不能理解成任意重排都保持答案质量。

[[SpanQueries-MLSys26|SpanQueries]] 让应用显式声明哪些输入 span 可以交换。它在专门的 microbenchmark 中报告 10–20× TTFT 改善，但需要特殊输入表示、裁剪和语义注解；论文没有证明普通在线服务可以自动推断这些可交换关系。

### 3. 命中不等于就绪

KV 在低层存储中被找到，只说明“存在”，不说明它能及时进入 GPU。[[Strata-OSDI26|Strata]] 观察到碎片 KV 的传输和重排会阻塞 prefill，于是把小页逻辑视图与较大 I/O 传输分开，并按 ready time 调度。其最高 5× 吞吐收益来自论文的分层缓存实验；不能单独归因于更高命中率，也不能直接外推到所有 SSD 或网络配置。

### 4. 局部性与负载均衡会冲突

把请求送到已有前缀的 GPU 可以少算 prefill，却可能让热门前缀对应的 worker 排队。[[LMetric-OSDI26|LMetric]] 用“待处理的新 prefill token 数 × 当前 batch 大小”近似这种代价，并同时考虑缓存局部性和负载。在 16 张 H20 的论文实验中，它相对 vLLM 把平均 TTFT 和 TPOT 分别降低最多 92% 和 24%；生产 canary 中对应降幅为 39% 和 51%。这些数字取决于论文给出的负载与集群，关键结论是路由器不能只看命中率。

### 5. 模型更新会使旧 KV 失效

KV 是模型权重对前缀做计算后的中间状态。[[RollArt-OSDI26|RollArt]] 在在线强化学习中更新 rollout worker 权重后，需要重算仍在执行中的旧 KV。由此可见，模型版本必须进入缓存有效性协议；仅按 token 哈希会错误地把旧权重产生的 KV 交给新模型。

### 6. 映射开销也可能吃掉命中收益

[[MoonBright-OSDI26|MoonBright]] 针对 GPU 虚拟内存映射路径做批量化和异步化，并在论文的 A100、7B/8B prefix-cache 配置中报告 TTFT 最多改善 8.2×。其低层 2 GB 映射实验从 36 ms 降到 14 µs，但这个微基准数字不能当作端到端应用加速比。它揭示的是：共享 KV 的页已经存在时，页表和映射仍可能成为瓶颈。

### 7. 离线全局信息和在线服务是两种问题

[[BatchLLM-MLSys26|BatchLLM]] 在完整批次预先可知时构造全局 prefix tree。论文实验中，vLLM 的 LRU 节省 35.8% prefill token，全局规划节省 58.1%。这种方法适合离线批处理，但没有自动解决在线到达、优先级、公平性和取消请求。

### 8. 邻近系统是否支持前缀缓存，需要看评测而不是接口声明

[[DirectKV-OSDI26|DirectKV]] 说明接口可以与 prefix caching 组合，但没有实际集成评测；[[MPK-OSDI26|MPK]] 使用固定的离线 prompt/decode 配置，没有测缓存 churn；[[OpenTela-OSDI26|OpenTela]] 的模拟器也没有建模 prefix cache。它们可说明组合空间或证据缺口，不能当作前缀缓存收益的直接证据。

## 设计空间与取舍

| 选择 | 优点 | 代价或风险 | 适用场景 |
|---|---|---|---|
| 固定 block 哈希 | 实现简单，容易验证 | 只能匹配严格相同的前缀；block 边界有内部碎片 | 通用在线引擎 |
| Radix tree | 能表示许多共享路径，并把局部性暴露给调度器 | 索引、引用计数和淘汰更复杂 | LM program、多轮共享前缀 |
| 结构化重排 | 能利用“内容相同但顺序不同”的上下文 | 需要应用声明语义；错误重排会影响答案 | RAG、批量结构化请求 |
| 近似 KV 复用 | 命中范围更大 | 质量损失难以统一界定 | 能容忍或验证近似误差的任务 |
| GPU 内缓存 | 延迟低，不需传输 | 容量小，与运行中 KV 和模型权重竞争 | 高频、短期复用 |
| CPU / SSD / 远端缓存 | 容量大，可跨引擎共享 | 传输、重排和故障恢复可能比重算更慢 | 很长上下文、较高复用概率 |
| LRU 等在线淘汰 | 无需预知未来，容易部署 | 不理解业务类别和未来复用 | 在线到达、负载变化快 |
| workload-aware / 全局规划 | 可利用热度、类别或完整批次 | 依赖预测或未来信息，可能损害公平性 | 稳定业务或离线批处理 |
| 共享 namespace | 潜在命中率高 | 隐私、侧信道、权限和污染风险 | 同一信任域 |
| 租户隔离 | 有效性和安全边界清楚 | 跨租户重复内容不能复用 | 多租户生产服务 |

前缀缓存还与其他机制相互影响：[[Chunked-Prefill]] 改变一次调度多少 prefill 计算，[[Continuous-Batching]] 改变请求何时进入 batch，[[Disaggregation]] 决定 KV 位于哪个服务阶段。任何一项变化都可能改变“加载还是重算”的最佳选择。

## 引用本概念的论文

### 基础抽象与引擎内复用

- [[vLLM-SOSP23]]：用分页 KV block 和 copy-on-write 支持请求间共享。
- [[SGLang-NeurIPS24]]：用 [[RadixAttention]] 保存并调度共享 token 路径。
- [[BatchLLM-MLSys26]]：离线已知完整批次时，用全局 prefix tree 重排工作。

### 真实负载、语义和策略

- [[KVCacheInTheWild-ATC25]]：刻画生产 trace 中的命中偏斜、生存期和用户边界。
- [[ContextPilot-MLSys26]]：通过上下文对齐、去重和注解扩大 RAG 复用。
- [[SpanQueries-MLSys26]]：让应用声明 span 的可交换性，再据此安排复用。
- [[CacheBlend-EuroSys25]]：探索非严格前缀的近似 KV 复用，也暴露准确率风险。
- [[Stream2LLM-MLSys26]]：动态 RAG 更新时，按最长公共前缀选择性保留 KV。

### 分层存储、传输与放置

- [[LMCache-arXiv25]]：把 KV 做成跨引擎、跨存储层的缓存对象。
- [[Strata-OSDI26]]：区分缓存命中和数据就绪，优化碎片传输与调度。
- [[SHIP-MLSys26]]：在特定 LPU 系统中使用片上 SRAM 与主机 DRAM 两级缓存。
- [[CacheSlide-FAST26]]、[[SolidAttention-FAST26]]、[[Bidaw-FAST26]]、[[CacheGen-SIGCOMM24]]：分别探索层级放置、存储路径或压缩传输。
- [[DirectKV-OSDI26]]：提供可组合的 GPU KV I/O 路径，但尚未评测 prefix-cache 集成。

### 调度、更新与可观测性

- [[LMetric-OSDI26]]：联合衡量前缀局部性、待算 token 和 batch 负载。
- [[RollArt-OSDI26]]：说明模型权重更新后，旧版本 KV 必须失效或重算。
- [[MoonBright-OSDI26]]：优化共享页映射路径，减少已有 KV 接入 GPU 的控制面开销。
- [[StriaTrace-OSDI26]]：把缓存路径纳入生产推理异常的追踪和归因。
- [[MPK-OSDI26]]、[[OpenTela-OSDI26]]：分别留下动态缓存 churn 和模拟建模的证据缺口。

## 已知局限 / 开放问题

- **有效性协议仍不统一。** 模型版本、tokenizer、adapter、位置编码、量化格式和执行引擎改变时，哪些 KV 还能复用，需要机器可检查的 contract。
- **安全边界尚不完整。** 命中时间可能泄露其他租户是否请求过某段内容；共享 namespace 还面临越权读取、缓存污染和资源挤占。
- **近似复用缺少统一质量保证。** 平均准确率不下降，并不能保证关键样本、长链推理或安全任务不受影响。
- **缓存决策缺少端到端目标。** 命中率没有同时反映排队、加载、重排、重算、能耗和尾延迟；系统需要以 ready time 和 SLO 为中心做选择。
- **工作负载会漂移。** 热前缀、生存期和用户内复用比例可能随产品、模型和 prompt 模板改变，固定策略很容易过期。
- **故障和取消语义不清楚。** 跨节点传输中断、部分 KV 到达、请求取消以及 cache controller 重启时，引用计数和数据一致性仍需更系统的生产证据。
