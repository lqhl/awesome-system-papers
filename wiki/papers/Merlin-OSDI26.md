---
type: paper
name: Merlin
full_title: "Merlin: An Efficient Adaptive Cache Eviction Algorithm via Fine-Grained Characterization"
authors: [Liujia Li, Jinhao Guo, Yi Fan, Jianyu Wu, Zhenlin Wang, Jie Zhang, Yuval Tamir, Xiaolin Wang, Yingwei Luo, Diyu Zhou]
venue: OSDI
year: 2026
tags: [caching, cache-eviction, adaptive-systems, workload-characterization, multicore]
source_pdf: "[[osdi26-li-liujia.pdf]]"
source_md: "[[osdi26-li-liujia]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Merlin：用细粒度访问刻画实现自适应缓存淘汰（OSDI 2026）

> **原题**：Merlin: An Efficient Adaptive Cache Eviction Algorithm via Fine-Grained Characterization

> **一句话总结**：Merlin 发现现有自适应淘汰器把整段访问硬分成少数模式，两个“互补”算法在混合模式下反而相互驱逐；它改为按对象同时记录短期 hotness、长期 popularity，并让 cache size 决定分类阈值，在 11 个数据集、5,423 条真实 trace 上把 10% WSS 时相对 LRU 的平均 hit rate 提高 10.4 个百分点，再在合成混合负载上取得 1.4–7.8 倍吞吐优势。

## 问题与动机

软件 cache 广泛用于 KV store、CDN、VM/block storage 和操作系统 page cache。淘汰策略必须猜测哪些对象还会再用；[[LRU]] 偏向最近访问，[[LFU]] 偏向长期频率，scan、churn 和频繁 phase change 又会破坏各自假设。论文分析 11 个真实数据集时发现，以 1% trace length 为窗口，相邻窗口中 unique objects 的变化比例最高约 45%（图 1），说明现代访问不是稳定的单一模式。

自适应算法本应根据负载切换策略，但 ARC/CAR 主要在“一次访问”和“多次访问”的两个近期列表之间调空间，难以发现间隔很长但会反复出现的对象；Cacheus 在 LRU-like 与 LFU-like 两个 base algorithm 之间调权重，假定它们能覆盖 LFU-friendly、LRU-friendly、churn 和 scan 四种 primitive pattern。现实 trace 常在同一时刻混合四种模式，两个 base algorithm 都会犯错，还会把对方保留的有用对象赶出去。论文的前置实验中，现有 adaptive algorithms 在 11 个数据集上经常输给静态 S3-FIFO 或 LIRS（§3）。

Merlin 的问题定义因此不是再加一个 workload classifier，而是构造一种连续、细粒度、同时反映长短期局部性并感知 cache size 的表示，再让一个统一淘汰架构使用这份表示。这样，系统只改变对象优先级，不在多个完整算法之间来回切换。

## 关键观察 / 隐含假设

- **观察 1：访问序列级标签太粗，对象级局部性才是可组合单位。** 同一窗口内可以同时有 scan、churn、近期热点和长期热点；把整段 trace 叫作某一种模式会丢失其余部分（图 2、5）。
  - **依赖假设**：对象 ID 稳定，历史访问可以在对象粒度关联；语义相关但 ID 不同的一组对象不会被算法识别成整体。
- **观察 2：recency 与 frequency 都需要，而且好坏取决于 cache size。** 重复访问五个对象时，cache 至少容纳五个，LRU 才不会 thrash。同一 trace 在不同容量下需要不同判断，因此阈值不能固定（§4）。
  - **依赖假设**：当前 cache size 固定或变化很慢；动态 memory budget 会立即改变阈值含义，论文把这留作 future work。
- **观察 3：现有 adaptive 失败不仅因为选错算法，还因为组件互相干扰。** Alibaba 742/269 trace 中，只保留 ARC 或 Cacheus 的一个 base component 反而比完整 adaptive algorithm 更好（图 4–5）。
  - **可能失效场景**：如果 workload 恰好符合某个预设 primitive pattern，简单 base algorithm 可能已经足够，Merlin 的额外状态不会带来同等收益。
- **观察 4：FIFO 架构能把命中路径做得很轻。** cache hit 不需要把节点移到队首，只更新少量 counter；队列操作集中在 miss/eviction 路径，因此比 LRU list 更容易多核扩展。
- **假设 1：过去的 hotness/popularity 对未来 reuse 有预测力。** 论文找到 2.9% adversarial traces，过去热点随后消失或 hot set 反复更换，Merlin 会暂时缓存错误对象（§7.2）。

## 核心方法

### 1. 用 cache-sized epoch 刻画每个对象

Merlin 把访问流切成 epoch：固定大小对象时，每出现相当于 cache capacity 数量的 unique-object insertions 就进入下一 epoch；可变大小对象则按 unique objects 的总字节数达到 cache size 计数。对象在当前 epoch 的访问次数叫 hotness，表示短期局部性；它在过去若干 epoch 出现过多少次叫 popularity，表示长期局部性。

系统维护 hotness 与 popularity 的计数分布。假设 cache 能容纳 `S` 个对象，hotness threshold 取第 `S` 个最热对象的值，popularity threshold 同理；可变大小对象按累计字节数达到容量决定。两个阈值把对象分成 hot-popular、hot-rare、cold-popular、cold-rare。阈值每 64 次访问更新一次，因而 pattern 改变时，各类型数量会连续变化，而不是在四个离散 workload label 间跳转（图 6、10）。

### 2. 三个数据队列加一个 ghost queue

Merlin 用三个 [[FIFO]] data queue：filter 占 10%，core 占 85%，staging 占 5%。新对象先进入 filter；离开时，hot 或 popular 的对象进 core，cold-rare 的数据被淘汰，只把 metadata 放进 ghost。ghost 保存约一个 cache 容量的历史，给被过早淘汰的对象第二次分类机会。

core 满时，hot-popular 对象降计数后重新插回 core，其他对象先进入 staging。staging 在最终删除前再检查一次：仍 hot 或 popular 就回 core，否则真正淘汰；从 ghost 复活的对象若仍不值得保留，metadata 会回到原 ghost 生命周期。这个 task division 让 filter 负责挡 scan，core 保存最好对象，staging 验证边界对象，ghost 修正早期误判，没有两个完整淘汰器去修改同一 cache（图 8–9）。

### 3. 用近似结构控制 metadata

hotness 是对象的 3-bit counter；另有一个“来自 ghost”标志和一个本 epoch 是否访问过的标志，总计 5 bits/object。ghost entry 用 fingerprint、hotness 和 sequence number，共 8 bytes，并用 lazy deletion 避免链表定位。

概念上 popularity 覆盖过去 16 epochs，实际用一个 [[Count-Min-Sketch|count-min sketch]] 近似，不保存完整 object name；访问累计到 `16 × cache size` 后，所有 counter 减半形成滑动窗口。默认按每对象约 1 byte 配置，目标 false-positive rate 为 1%。以 4 KB 对象为例，论文估计全部额外空间约占 cache 的 0.31%；小对象 cache 的百分比会更高（§6.1）。

### 4. 实现与并发

作者在 Meta CacheLib 和 libCacheSim 中实现 Merlin，也补充了 ARC/CAR baseline。CacheLib 用 hash table 找 cached object；hit 路径只做 atomic metadata update，不移动 FIFO 节点。miss 可能在 filter/core/staging 间重新插入，但论文观察 eviction loop 通常只迭代少数次。variable-sized objects 已在实现中支持，并不是 future work；动态 cache capacity、TTL 和对象语义才没有解决。

## 设计取舍

- **对象级双维统计换 metadata**：比全局 workload label 细，代价是每个 cached/ghost object 的 counter、fingerprint 和 sketch；0.31% 只对 4 KB 对象成立。
- **近似 popularity 换空间与速度**：count-min sketch 不保存 key，但 collision 只会高估 popularity，可能把无用对象误留在 cache。
- **统一 FIFO 换固定结构比例**：避免 base algorithms 相互干扰，也保留多核扩展；filter/core/staging 的 10%/85%/5% 仍是经验常数，并未在线自调。
- **历史驱动换 phase lag**：突变 workload 出现后，要等旧 hotness/popularity 衰减；极小 cache 观察时间太短，极大 cache 的一个 epoch 又可能跨过多个 phase。
- **优化 hit rate 换目标通用性**：CDN 更关心 byte hit/write traffic，其他系统可能关心 miss cost、TTL、对象生成成本或 tail latency；Merlin 没有统一 cost-aware objective。

## 实验与结果

- **规模、平台与 baseline**：11 个开源数据集含 5,423 traces、338B requests、33B objects，时间跨度 2008–2023，覆盖 KV、CDN、VM/block cache；作者累计模拟 38.5T requests，约用 1M CPU-hours。Merlin 与 16 个基线算法比较，包括 LRU/LFU/FIFO、S3-FIFO、LIRS、W-TinyLFU、ARC/CAR、Cacheus、LeCaR 和 GL-Cache，均用默认配置。吞吐平台是双路 192-core AMD EPYC 9965、Debian 12、Linux 6.13.8，关闭 SMT 和 turbo（§7.1、表 2）。
- **hit rate**：在 cache 为 10% WSS 时，Merlin 的平均 hit rate 比 LRU 高 10.4 个百分点，S3-FIFO、Cacheus、ARC 分别高 7.1、6.8、6.1 个百分点。在 1%、3%、10% WSS 三种容量上，Merlin 都有 6/11 datasets 排第一，另 3/11 排第二且距最佳只约 0.5 个百分点；byte hit rate 的趋势相似（图 11–12）。这里是 trace-driven simulator 结果，不是生产 cache latency。
- **稳健性与失败样本**：以每条 trace 上 16 个算法中的最佳者作为不可部署的“dominant”参照，Tencent CBS、10% WSS 时，99% traces 的 Merlin hit rate 至少达到 oracle 的约 88%，好于 S3-FIFO 的约 83%。仍有 2.9% traces 比最佳算法低超过 5%；其中 1.1% 全体 traces 主要受 count-min sketch false positive 影响，其他常见原因是过去历史无法预测下一 phase（图 13、§7.2）。
- **吞吐与纯管理开销**：吞吐实验不是 5,423 条真实 trace，而是一条 200M-request、2M-object 的合成混合流，包含 Zipf、uniform、周期顺序访问和 scan，并模拟 10 微秒 backend miss。1–32 threads 下，Merlin 在 32 threads 比各 baseline 高 1.4–7.8 倍；相对 S3-FIFO 的约 1.4 倍主要同时包含更高 hit rate。去掉 backend latency 后，Merlin 的纯 cache-management throughput 只比 S3-FIFO 高 16%（图 14）。
- **Flash 结果**：在 CloudPhysics 数据集的 libCacheSim 扩展中，把 filter/metadata 放 DRAM、core/staging 放 flash；容量为 1%–10% WSS、DRAM 为 cache 的 0.1%–10%。Merlin 相对 ARC/Cacheus 少写约 70%，absolute hit rate 高 1–2 个百分点；相对 S3-FIFO 写量近似、hit rate 高约 1 个百分点。这是模拟 write bytes，不是实际 SSD endurance、write amplification 或 P99 latency（图 15）。
- **敏感性与机制证据**：filter 5%–15%、staging 1%–10%、ghost 50%–200%、记录 4–128 epochs，以及 sketch FP 0.1%–5% 时，多数 traces 的 hit rate 稳定；但约 8% traces 对 epoch/sketch 配置会变化超过 1 个百分点，CloudPhysics 中该比例约 25%。默认 10%/5%/100% 总体最好。Twitter/FIU 两条 trace 上，Merlin 从 ghost 提升对象的 precision 和后续平均 hits 高于 ARC/Cacheus，支持分类更准确，但不是全部数据集上的组件消融（图 16–20）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 对象级、cache-aware characterization 比现有 adaptive policy 更稳健 | 图 11–13：6/11 datasets 第一，3/11 第二，2.9% adversarial traces | 5,423 个公开 traces、libCacheSim、默认 baseline 参数 | 强 |
| Merlin 在主设置中提高平均 hit rate | 10% WSS 时比 LRU 高 10.4 个百分点，S3-FIFO 高 7.1 个百分点（图 11） | 按 dataset 汇总的模拟 hit rate，不是端到端 latency | 强 |
| FIFO 架构有较好的多核管理效率 | 无 backend 时 32 threads 比 S3-FIFO 高 16%（图 14b） | 单台双路 EPYC，只测到 32/192 cores，单条合成 trace | 中 |
| hit-rate 收益可转化为吞吐优势 | 模拟 10 微秒 miss 时比 baselines 高 1.4–7.8 倍（图 14a） | 合成 200M-request workload，结果高度依赖 miss penalty | 中 |
| 组件划分适合 DRAM–Flash cache | 相对 ARC/Cacheus 少写 70%，hit rate 高 1–2 个百分点（图 15） | 单个 CloudPhysics 数据集、flash 模拟器，无真实设备 | 中 |

## 批判性分析

### 论证链条

论文先用广泛 trace 证明“adaptive 天然胜过 static”并不成立，再用两个失败案例把原因拆成粗粒度 characterization 和 base-component interference；Merlin 的对象级阈值与统一 FIFO 分别回应两点。大规模 hit-rate 结果与 Figure 20 的 promotion precision 支持新设计有效。不过，论文没有给一套完整 Merlin ablation，分别移除 cache-aware threshold、popularity、staging queue 或统一架构，因此“收益各有多少来自 characterization、多少来自 queue engineering”仍不清楚。

### 假设压力测试

算法假设对象过去被访问能预测未来。突然换 hot set、一次长热期后永久消失、scan 与不断变化的热点交替时，16-epoch popularity 会滞后；论文的 2.9% adversarial traces 已验证这一点。极小/极大 cache 也会让 epoch 太短或跨多个 phase。动态 memory budget 会使两个阈值立刻过期；semantic correlation、TTL、不同 miss cost 和 admission price 也没有进入四分类。

### 实验可信度

11 datasets、16 baselines、多个 cache sizes、variable-sized object、byte hit、Flash、敏感性和 38.5T simulated requests，使 hit-rate 证据很强。需要收窄吞吐 claim：1.4–7.8 倍只来自一条人工混合 trace 和固定 10 微秒 miss；真正隔离 metadata/locking 后，相对最强 S3-FIFO 是 16%。机器有 192 cores，却只扩到 32 threads，也未报告 [[NUMA|NUMA]] placement。baseline 都用默认配置，没有逐 workload 调优；Flash 结果来自 simulator 而非真实 SSD。

### 系统性缺陷

实现包含三个 data queues、ghost hash、per-object bits、分布统计和 count-min sketch，虽然热路径轻，调试误分类和解释 eviction 仍比 S3-FIFO 复杂。sketch collision 会系统性高估某些对象，文中已有 1.1% traces 因此受损。论文没有生产部署、P50/P99 lookup latency、内存碎片、crash recovery、与 TTL/admission/replication 的交互，也没有说明动态缩容时如何快速重建阈值。对于小对象，8-byte ghost 和 sketch 的比例会远高于 4 KB 示例中的 0.31%。

## 局限与后续工作

- **局限 1**：吞吐只测一条合成混合 trace、10 微秒模拟 backend 和最多 32 threads；没有生产 A/B 或 tail latency。
- **局限 2**：cache capacity 固定，filter/core/staging 比例固定；动态内存预算和在线 size adaptation 尚未解决。
- **局限 3**：算法只根据对象 ID 的访问历史，不理解 TTL、语义关联、不同 miss cost 和业务优先级。
- **后续工作 1**：在真实 CacheLib/CDN/KV 服务上按租户 A/B，报告 hit/byte-hit、P99 latency、backend I/O、CPU 与 metadata bytes。
- **后续工作 2**：注入快速 phase switch 和在线 cache resize，测阈值收敛请求数、短期 hit-rate loss，并设计无需清空状态的重标定。
- **后续工作 3**：逐项关闭 popularity、cache-aware threshold、staging 和 sketch，分离 characterization、近似误差与 FIFO 架构各自贡献。

## 相关

- **相关概念**：[[Cache-Eviction]]、[[LRU]]、[[LFU]]、[[Working-Set]]、[[Count-Min-Sketch]]、[[Adaptive-Systems]]
- **同类算法**：[[ARC]]、[[LIRS]]、[[S3-FIFO]]、[[TinyLFU]]、Cacheus
- **同会议**：[[OSDI-2026]]
