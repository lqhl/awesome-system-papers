---
type: paper
name: Merlin
full_title: "Merlin: An Efficient Adaptive Cache Eviction Algorithm via Fine-Grained Characterization"
authors: [Liujia Li, Jinhao Guo, Yi Fan, Jianyu Wu, Zhenlin Wang, Jie Zhang, Yuval Tamir, Xiaolin Wang, Yingwei Luo, Diyu Zhou]
venue: OSDI
year: 2026
tags: [cache-eviction, adaptive-caching, locality, multicore-scalability, flash-cache]
source_pdf: "[[osdi26-li-liujia.pdf]]"
source_md: "[[osdi26-li-liujia]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-24
---

# Merlin：基于细粒度特征的自适应缓存淘汰算法（OSDI 2026）

> **原题**：Merlin: An Efficient Adaptive Cache Eviction Algorithm via Fine-Grained Characterization

> **一句话总结**：现有自适应淘汰算法只在少数预设访问模式间调节，遇到混合且变化的工作负载会互相干扰；Merlin 按对象同时统计短期 hotness 与长期 popularity，并依据缓存容量动态设阈值，在 11 个数据集、5,423 条 trace 上平均将相对 LRU 的命中率提升到 10.4%，吞吐较其他方案提高 1.4–7.8 倍。

## 问题与动机

缓存淘汰策略必须在有限容量内保留未来会再次访问的对象。现代 CDN、KV store 和存储缓存的访问模式同时包含频率、近期性、churn 与 scan，而且会随时间切换。固定策略通常只能覆盖其中一部分。

ARC、CAR 和 Cacheus 尝试自适应，但它们分别调整两个分区、两个基线策略的权重，或隐含假设访问序列属于少数 primitive pattern。论文在 11 个真实数据集上发现，自适应算法反而经常落后于 S3-FIFO 和 LIRS。作者将根因归结为访问模式刻画过粗，以及多个组件在混合模式下相互驱逐有用对象。

## 关键观察 / 隐含假设

- **观察 1：访问模式细粒度且快速变化。** 5,423 条 trace 的窗口 object change rate 最高约 45%（图 1），同一 trace 中可交替出现四类 primitive pattern（图 2）。
  - **依赖假设：**近期和历史访问仍能对未来复用提供信号。
  - **可能失效场景：**阶段切换不可预测、历史热点长期失效时，任何历史驱动的自适应策略都会暂时保留错误对象。
- **观察 2：按整条序列选择少数基线策略会丢失混合模式。** Alibaba 742 trace 中，ARC 只偏向短期 locality，无法保留长间隔但重复访问的对象（图 4）；Alibaba 269 trace 同时包含多种模式，Cacheus 在 LRU 与 LFU 变体之间反复调整（图 5）。
  - **依赖假设：**对象级别的 locality 比整段序列的单一标签更适合指导淘汰。
- **假设 3：缓存容量可以作为 locality 阈值的参照。** Merlin 将 epoch 定义为约一个缓存容量的 unique object 访问，并以当前最热/最流行的前 S 个对象动态确定阈值。容量剧烈变化时阈值需要重新解释；论文未实现动态 memory budget。

## 核心方法

Merlin 对每个对象维护两个维度：当前 epoch 内的访问次数 hotness，表示短期 locality；过去若干 epoch 被访问的次数 popularity，表示长期 locality。对象据此分成 hot-popular、hot-rare、cold-popular、cold-rare 四类。用计数分布而不是固定模式标签表示工作负载，使混合模式可以同时存在；缓存大小 S 决定进入前 S 个对象的 hotness/popularity 阈值（§4、图 6）。

架构由职责分离的 FIFO 组件组成：filter queue 快速过滤 cold-rare 对象；core queue 保存 hot 或 popular 对象；staging queue 在最终淘汰前复核对象类型并优先保留 hot-popular 对象；ghost queue 保存被过滤对象的元数据，提供再次访问机会；popularity recorder 用 count-min sketch 估计跨 epoch 的 popularity（图 8）。

对象命中只更新 hotness 和访问标志。未命中对象先进入 filter；离开 filter 后，cold-rare 对象进入 ghost，其余对象进入 core。core 中 hot-popular 对象可重新插入，其他对象进入 staging，由 staging 再次判断是否回到 core（图 9）。阈值每 64 次访问摊销更新一次（图 10）。这一设计回应了观察 1 和 2：适应性来自阈值变化，而不是让多个完整淘汰策略竞争缓存空间。

实现支持 CacheLib 与 libCacheSim。count-min sketch 以滑动窗口近似最近 16 个 epoch；典型 4KB 对象下，元数据、ghost queue 和 sketch 的总空间开销约为缓存大小的 0.31%（§6.1）。

## 设计取舍

- **取舍 1：**count-min sketch 和 ghost fingerprint 降低了 popularity 与历史记录的空间成本，但会引入计数碰撞和 fingerprint 假阳性；论文测得影响可忽略。
- **取舍 2：**固定使用 filter/core/staging 的 10%/85%/5% 配置简化了运行时调节。敏感性实验显示多数 trace 稳定，但极小或极大缓存、以及动态容量环境仍可能需要重调。
- **边界条件：**FIFO 队列避免 LRU 全局锁，适合多核；代价是算法依赖 FIFO 对 epoch 和访问观察窗口的近似，且对不可预测的相位变化存在滞后。

## 实验与结果

- 在 11 个数据集、5,423 条真实 trace 上与 16 个算法比较，缓存为 WSS 的 10% 时，Merlin 相对 LRU 的平均命中率提升 10.4%，S3-FIFO、Cacheus、ARC 分别为 7.1%、6.8%、6.1%（图 11）。Merlin 在 11 个数据集中 6 个排名第一、3 个排名第二。
- 在 Tencent CBS 的 4,611 条 trace 上，Merlin 在 1% CDF 处达到约 88% 的 dominant-algorithm 相对命中率；S3-FIFO、Cacheus、ARC 约为 83%、76%、76%（图 13）。
- 32 线程、200M 请求混合 trace 上，Merlin 吞吐较其他算法提高 1.4–7.8 倍；去除 10µs backend 延迟后，管理吞吐仍比 S3-FIFO 高 16%（图 14）。
- DRAM–Flash 分层缓存中，Merlin 比 ARC 和 Cacheus 少写约 70%，绝对命中率高 1–2%；与 S3-FIFO 写入量近似但命中率高 1%（图 15）。
- filter、staging、ghost 队列大小、记录 epoch 数和 sketch 假阳性率在较宽范围内通常稳定；但约 2.9% trace 比最佳算法低超过 5%，其中 1.1% 与 sketch 假阳性相关（§7.2、§7.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 对象级 hotness/popularity 能覆盖混合访问模式 | 图 4–7、§4 | 离线 trace，缓存大小按 WSS 比例设置 | 强 |
| Merlin 的命中率比现有静态和自适应方案更稳健 | 图 11、图 13、§7.2 | 11 个数据集、5,423 条 trace、16 个基线 | 强 |
| 组件分离同时降低管理开销并支持多核扩展 | 图 14、§6.1 | 192 核 AMD EPYC，最多 32 线程；合成混合 trace | 中 |
| Merlin 适合 DRAM–Flash 分层缓存 | 图 15、§7.4 | 特定分层布局与 trace，主要观察写入量和命中率 | 中 |

## 批判性分析

### 论证链条

论文的链条基本闭合：真实 trace 显示模式混合与变化，案例说明整序列分类和策略切换会失败，Merlin 改为对象级双维刻画，结果在大量 trace 上更稳健。命中率改善与吞吐改善并非完全独立：图 14 的带 backend 延迟吞吐包含更高命中率带来的收益，管理开销实验才部分隔离了这一因素。

### 假设压力测试

Merlin 假定过去 16 个 epoch 的 popularity 能预测未来复用。作者承认两类反例：热点集合突然改变、scan 与热点阶段交替且每轮热点变化。此类 trace 会使历史高 popularity 延迟衰减。count-min sketch 的碰撞还会把低频对象误判为 popular。论文没有评估语义相关对象、预取关联或多租户之间的相关访问。

### 实验可信度

数据规模和领域覆盖较充分，基线包括 S3-FIFO、LIRS、ARC、Cacheus 及机器学习策略。命中率使用离线模拟器，吞吐使用 CacheLib；两者覆盖了策略质量和运行开销，但真实线上部署、故障恢复、锁竞争在超过 32 线程时的行为没有展示。合成混合 trace 能控制模式，却不能替代生产请求的并发与对象大小相关性。

### 系统性缺陷

算法比 LRU/SIEVE 更复杂，包含多个 FIFO、ghost hash table、计数 sketch 和阈值分布维护。论文报告了空间和吞吐开销，但没有讨论在线参数观测、调试可视化、故障恢复或跨租户隔离。缓存容量变化会使阈值失效，作者将其留作后续工作（§6.2）。

## 局限与后续工作

- **局限 1：**不可预测的 phase shift 会造成错误保留；需要测量阈值变化与命中率恢复之间的滞后时间。
- **局限 2：**count-min sketch 假阳性在相关对象大量共现时可能上升；应在可控碰撞率下比较精确计数器、分层 sketch 与 Merlin 的命中率/空间曲线。
- **局限 3：**当前设计假设固定缓存大小；应在在线扩缩容和多租户配额变化下验证阈值重估策略。
- **后续工作：**为 filter 和 staging queue 的容量调节建立性能模型，并在真实 DRAM–Flash 服务中同时测量命中率、写放大、P99 延迟和恢复行为。

## 相关

- **相关概念：**[[Cache-Eviction]]、[[Count-Min-Sketch]]、[[Locality]]
- **同类系统：**[[S3-FIFO]]、[[LIRS]]、[[ARC]]、[[Cacheus]]、[[SIEVE]]
- **同会议：**[[OSDI-2026]]
