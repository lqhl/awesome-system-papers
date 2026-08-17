---
type: concept
aliases: [KV cache, KV Cache, kv-cache, KV-cache, key-value cache, KvCache]
parent: "[[Attention]]"
last_updated: 2026-08-17
tags: [memory, attention, llm-inference]
---

# KV-Cache

> KV cache 保存 Transformer 每层已处理 token 的 key/value，让自回归 decode 不必每步从头计算整段上下文。它不只是一块 GPU tensor，还是有布局、生命周期、版本、所有权和迁移成本的 serving 状态。

## 核心思想

prefill 一次处理 prompt，为每层生成 K/V；decode 每轮生成一个或少量新 token，追加新 K/V，并读取全部已有历史。对常见 attention，单请求的基本容量可近似写成：

`token 数 × layer 数 × 2(K+V) × KV head 数 × head dimension × 每元素字节数`

batch 和长上下文会线性放大容量。GQA/MQA/MLA、低精度和稀疏 attention 会改变常数，但不会消除“状态随活跃 token 增长”这个性质。

管理一份 KV 至少要回答五个问题：

1. **如何布局**：连续 tensor、[[PagedAttention]] block，还是按 layer/head 分片。
2. **放在哪里**：GPU HBM、CPU DRAM、SSD 或远程节点。
3. **谁能复用**：只属于当前请求，还是通过 [[Prefix-Caching]] 被其他请求共享。
4. **保留多少精度**：原始 K/V、量化/压缩 K/V，或只保留 sparse attention 会选中的部分。
5. **何时失效**：请求完成、模型权重/实例版本变化、租户边界变化，或缓存压力迫使驱逐。

## 为什么重要

[[vLLM-SOSP23]] 测得早期连续预分配系统中，只有 20.4%–38.2% 的 KV 显存真正存放 token state。分页按需分配能让更多请求同时进入 batch，但后续论文表明，“显存利用率”只是 KV 问题的第一层。

OSDI 2026 将设计空间扩展到整个机器与集群：

- [[DirectKV-OSDI26]] 在 Grace–Hopper 上让 attention 直接读 CPU-resident KV，避免 HBM staging buffer。
- [[ECHO-OSDI26]] 把原生稀疏 attention 的完整 KV 放在主存，GPU 只保留被选 token，并在 exact top-k 最终确定前预取。
- [[Strata-OSDI26]] 把主存/SSD 的传输布局与 GPU attention 布局分开，并让 scheduler 依据 KV 完成时间组 batch。
- [[Prism-OSDI26]] 把多模型权重和 KV 放进同一个可伸缩物理显存池。
- [[LMetric-OSDI26]] 说明集群 router 不能只追求 KV 命中；它还要预测送入某实例后的新 prefill 工作和 decode batch 压力。

这些工作共同表明，KV 同时影响 HBM 容量、attention 带宽、请求调度、跨节点传输和故障恢复，不能只交给单卡 allocator。

## 关键观察 / 隐含假设

- **KV 与权重争用同一份 HBM。** [[Prism-OSDI26]] 的生产 trace 显示，同时活跃模型只占 23%–50%，但活跃组合每小时变 54–766 次。固定为每个模型分 KV pool 会让冷模型旁边的显存闲置；弹性物理页能复用这些空间，但不会在所有模型同时变热时创造新容量。
- **cache hit 只说明数据存在，不说明它已在 GPU 可用。** [[Strata-OSDI26]] 指出，1–32 token 的小页会把一段 context 拆成大量小 I/O；8,192-token KV 用传统 copy 时，PCIe 5.0 只达理论带宽约 22%，Grace–Hopper 更快互连上反而只达约 5%。它的主结果是相同平均 TTFT 下吞吐最高 5 倍，但主评测是合成 Poisson 到达，没有 p99 公平性结论。
- **zero-copy 并不会自动避免重复读。** [[DirectKV-OSDI26]] 在 GH200 上为 CPU memory 重新设计 tiling、warp pipeline 和投影–attention 融合，否则朴素 GPU direct access 会反复从 CPU 读相同 K/V。该系统报告 GPU memory 降到 47 GB，比其选定 offload 基线平均少 43%；速度收益强依赖 NVLink-C2C，普通 PCIe H100 对照不支持普遍外推。
- **稀疏 attention 省 GPU KV 的前提是能及时 recall。** [[ECHO-OSDI26]] 把约 1,000 GB、1.8M-token 的完整 KV pool 放在 host，GPU 只保留当前选中部分。其“无损”是指预取不改变最终 exact top-k，不是稀疏模型与稠密 attention 等价；端到端收益主要来自更高并发，intra-query prefetch 额外贡献最高只有 4%。
- **locality 和 load 会相互冲突。** [[LMetric-OSDI26]] 用“送入后尚需 prefill 的 token 数 × 当前 batch size”做无手工权重的 score。在 16 张 H20 真实 trace replay 中，它相对 vLLM 将 mean TTFT/TPOT 降低 92%/24%；生产 canary 相对旧 scheduler 降低 39%/51%。这些是与特定调优基线和 trace 的比较，而且额外 thinking workload 中出现过安全比例失效的时段。
- **KV 必须绑定生成它的模型版本。** [[RollArt-OSDI26]] 在 trainer 更新权重后，会对旧版本下尚未完成的 trajectory 重算 KV；否则新权重将继续读旧权重产生的 hidden state。因此跨实例迁移不只是复制 bytes，还要验证 model/tokenizer/adapter 与 position 语义。
- **大批处理和在线交互需要不同的 KV 调度。** [[BatchGen-OSDI26]] 把 sequence 当作可暂停、合并、分割和迁移的 coroutine，主存保存节点内所有 sequence KV。这适合离线批处理的 BCT；它的跨节点同步和 parallelism 重配可达毫秒至数秒，不能直接套到低 TTFT 服务。
- **解耦是否划算由 KV 路径决定。** [[EcoServe-OSDI26]] 在 32 张 L20 与普通 Ethernet 上发现，完全拆开的 prefill/decode 要为每个请求搬 KV；它改为让完整模型实例按时间窗口轮换阶段。这个结论针对模型副本和 active KV 都能放进单实例的条件，超大模型或超长上下文可能反过来需要解耦。[[Alibaba-ASI-OSDI26]] 的 trace 也显示，跨交换机做异构 P/D placement 会把 KV 传输放进关键路径，但论文没有给出完整 scheduler 解法。

## 设计空间与取舍

| 维度 | 一端 | 另一端 | 核心取舍 |
|---|---|---|---|
| 计算布局 | 连续、layer-first | 分页、per-head/per-layer | kernel 局部性与碎片/共享能力 |
| 传输布局 | 直接复用 GPU page | 在慢层用 page-first/大 chunk | 零转换与链路利用率 |
| 放置 | GPU 全驻留 | CPU/SSD/remote 分层 | 容量与加载延迟、故障域 |
| 传输 | staging 到 HBM | GPU 直读 CPU memory | 通用性与硬件专用 tiling |
| 内容 | exact/full KV | quantized、compressed、sparse KV | 容量/带宽与质量证明 |
| 共享 | request-local | prefix-/context-shared | 复用收益与隔离、失效、公平性 |
| 驱逐 | 重算 | swap/load | GPU 计算成本与链路/存储成本 |

好的系统通常不固定选表中某一端，而是按 prompt 长度、reuse probability、当前 batch、带宽和 SLO 动态选择。难点是这些决策共享同一份 KV metadata，分开的 allocator、router 和 I/O scheduler 容易各自局部最优。

## 引用本概念的论文

- [[NEO-MLSys25]] — 将部分请求的 KV 与 decode attention 成对放入 CPU，避免每轮 PCIe 往返。
- [[LLMQueryReordering-MLSys25]] — 通过离线行/字段重排提高 prefix KV reuse，依赖字段可交换和 batch 全局可见。
- [[BlendServe-ASPLOS26]] — 在保留共享 prefix KV 的同时混合不同资源密度请求。
- [[SkyWalker-EuroSys26]] — 把 KV locality 纳入跨 region routing，说明 cache ownership 已跨越单集群边界。

- [[vLLM-SOSP23]] — 用 block table、按需分配和 copy-on-write 建立现代 KV 内存管理基线。
- [[SGLang-NeurIPS24]] — 用 [[RadixAttention]] 组织跨请求 prefix KV 复用。
- [[KVCacheInTheWild-ATC25]] — 用生产 trace 刻画命中、生命周期和跨用户复用边界。
- [[DiffKV-SOSP25]] — 探索不同 KV 精度与分层的容量—质量取舍。
- [[PrefillOnly-SOSP25]] — 把特定 workload 的 KV/执行边界与通用 online serving 区分。
- [[DirectKV-OSDI26]] — 在 Grace–Hopper 上为 CPU-resident KV 重写 attention 数据路径。
- [[ECHO-OSDI26]] — 为原生稀疏 attention 管理 host-authoritative KV 与 exact recall。
- [[Strata-OSDI26]] — 联合解决分页 KV 碎片 I/O、布局转换与 ready-time 调度。
- [[Prism-OSDI26]] — 在多模型间弹性分配权重与 KV 的 GPU 物理页。
- [[LMetric-OSDI26]] — 路由时联合近似 prefix locality 和实例 load。
- [[Seer-OSDI26]] — 用层级全局 KV pool 迁移长 rollout request，并在 affinity/load 间切换。
- [[BatchGen-OSDI26]] — 把 sequence KV 放入可迁移的离线推理 coroutine 状态。
- [[RollArt-OSDI26]] — 明确权重版本更新会让未完成 trajectory 的旧 KV 失效。
- [[DynaRL-OSDI26]] — 在 agentic RL 中把 cache locality 纳入请求优先级与迁移，说明资源移动也会损失热 KV。
- [[EcoServe-OSDI26]]、[[Alibaba-ASI-OSDI26]] — 从普通 Ethernet 与生产拓扑两侧界定跨实例 KV 传输的代价。
- [[VTC-OSDI26]] — 在 QKV operator 中用虚拟 tensor 避免先物化完整中间结果，说明 KV 写入布局也会受 compiler 数据移动影响。
- [[Nixie-OSDI26]] — 说明对所有 GPU 对象一视同仁的透明迁移无法利用“KV 可重算”这类语义。
- [[StriaTrace-OSDI26]] — 把 distributed KV call、allocation 和 token 状态纳入生产推理的低开销 trace。

## 已知局限 / 开放问题

- **统一布局还没有好答案。** GPU attention 喜欢 layer-first 与局部连续，网络/SSD 喜欢大而连续的 page-first chunk；同时保存两份会增加内存和一致性成本。
- **版本和所有权缺少共同契约。** model weights、tokenizer、adapter、RoPE/position 语义、quantization 与 attention kernel 变化时，哪些 KV 必须失效，不同 engine 尚无统一表达。
- **多租户安全与公平性没有闭环。** 共享 prefix 可能泄露内容是否存在，攻击者也可用长前缀占满 cache；大多数论文只报平均吞吐/延迟。
- **压缩/稀疏 KV 的质量与 SLO 应同表报告。** 只报显存或 token/s，无法判断近似是否值得。
- **故障语义仍很弱。** in-flight transfer、半写入 SSD、worker 崩溃、重复请求和迁移后旧副本回收需要定义可验证的状态机。
- **缺少可复现的联合 benchmark。** 未来比较应同时报 p50/p99 TTFT/TPOT、goodput、quality、GPU/CPU/SSD bytes、能耗、失败恢复和 tenant fairness。
