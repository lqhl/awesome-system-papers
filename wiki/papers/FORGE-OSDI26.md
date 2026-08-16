---
type: paper
name: FORGE
full_title: "FORGE: Mitigating Synchronization Amplification for Memory-Disaggregated Caching Systems"
authors: [Zhijun Yang, Yu Hua, Ming Zhang, Menglei Chen, Yixiao Wang]
venue: OSDI
year: 2026
tags: [disaggregated-memory, caching, rdma, cache-replacement, synchronization]
source_pdf: "[[osdi26-yang-zhijun.pdf]]"
source_md: "[[osdi26-yang-zhijun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# FORGE：缓解内存解耦缓存系统的同步放大（OSDI 2026）

> **原题**：FORGE: Mitigating Synchronization Amplification for Memory-Disaggregated Caching Systems

> **一句话总结**：[[Disaggregated-Memory|内存解耦]]后，cache hit/eviction的本地metadata操作变成约2 µs的远程同步，object-level hotness与queue维护甚至比Get/Set产生更多[[RDMA]]流量。FORGE首次写入时按时间局部性把objects装入固定group，淘汰前才合并各compute nodes的1-byte frequency counters、救出hot objects并重组；lock-free ring FIFO让“谁快被淘汰”可预测，从而只在eviction window内lazy flush。真实trace上相对Ditto/GLCache-DM最高4.5倍吞吐、P99低7.5倍，平均hit ratio高1.14倍。

## 问题与动机

内存解耦架构把compute nodes（CNs）和memory nodes（MNs）分开：CN执行Get/Set、hotness tracking与eviction，MN只提供大容量remote memory；多个CN经CXL或RDMA直接读写同一MN。好处是compute和capacity可独立扩展，但原本10–100 ns的cache-coherent metadata操作变成CXL约350 ns、RDMA约2,000 ns的cross-node round trip（§1、图 1）。

问题不只在数据Get/Set。LRU每hit移动linked-list node；SIEVE每hit设visited bit、eviction时锁住queue扫描；Ditto把hotness缓存在CN，却要周期flush并随机sample eviction candidates。16 threads、10% cache的YCSB中，LRU的hotness/eviction占RDMA traffic 57.4%/29.2%，真正Get/Set只占13.4%；Ditto两项仍占45.9%/18.0%，高于Get/Set的36.1%（§2.2、图 3）。

RDMA atomic尤其昂贵：CAS/FAA比basic reads/writes慢4–5倍，还会让并发RDMA read throughput下降4.3倍。把atomic destination放进ConnectX-5的256 KB on-chip memory可让atomic throughput提高4.9倍并减少2.4–3.0倍干扰，但容量太小，不能存全cache的per-object metadata（§2.2、图 2）。

简单“整组淘汰”又会伤hit ratio：一个group可能同时含hot/cold objects，aggregated hotness会把少量hot遮住大量cold。FORGE要同时解决三角冲突：group-level operation减少同步，object-level signal保持淘汰精度，且这些signals只能在真正做eviction前及时同步（§1、§2.3）。

## 关键观察 / 隐含假设

- **观察 1：关键路径与housekeeping不需要相同粒度。** Get/Set仍按object访问，避免read/write amplification；hotness flush、space reclaim和eviction按fixed-size group摊销（§3–§4、图 4）。
  - **依赖假设**：workload有足够objects可装满group，且group metadata/内部碎片小于远程同步收益。
- **观察 2：写入时间提供便宜但不完美的相似性。** 同时写入的objects常有相关reuse pattern；第一次Set只按arrival顺序成组，达到chunk或object上限就封组。只有group被淘汰时，才根据整生命周期的object frequency救出hot objects并二次重组（§4.1、图 5）。
  - **关键修正**：FORGE不是在写入时知道“相似热度”。Phase 1是假设temporal locality，Phase 2才用测得hotness净化group。
- **观察 3：FIFO让未来需要哪组hotness变得可预测。** random sampling不知道下一次读谁，只能周期flush所有candidate metadata；ring FIFO知道head附近的eviction window，因此window外的OFM可以一直留在CN（§5.1–§5.2、图 9）。
  - **依赖假设**：head推进速度有可计算上界，所有CN能在group到head前检测并flush；RNIC/operation rate变化时必须调整window与poll interval。
- **观察 4：并发淘汰的工作集远小于cache容量。** 示例中16 groups×256 objects的window只需4,096 counters，16 KB RNIC device-memory ring已能容纳16K counters；cursor也只需8 bytes（§5.2）。
  - **设计边界**：RNIC on-chip memory只暂存即将evict的OFM和cursor，不执行grouping/eviction logic；没有device memory时放MN host memory仍正确，只是更慢。
- **观察 5：group FIFO必须补回hotness awareness。** 纯FIFO会误删老而热的group；virtual segment不做random insertion，而是给tail node写segment count，每次到head仍hot就减count并重新enqueue（§5.4、图 12）。
  - **代价假设**：hot group反复绕queue会增加FAA与traffic；论文没有给单个group最大reinsertion次数或starvation bound。
- **观察 6：fixed-size group同时规避external fragmentation。** variable-size object在group内compact，整group回收连续chunk；相比object-level slab，在小cache的Meta/Twitter trace中不易留下跨CN小碎片（§6.4、图 15）。
  - **可能失效场景**：group内部空间浪费、极大object或size distribution剧变仍可能产生internal fragmentation，论文没有单独报告utilization。
- **假设 1：MN不执行housekeeping，CN通过one-sided RDMA协调。** 这是目标DM模型；memory-side compute、coherent [[CXL|CXL]] CPU或smartNIC可执行policy时，最优设计可能不同。

## 核心方法

### 两阶段对象分组与无锁 Get/Set

Phase 1中，CN把同期Set objects依次写进一个available group；每个group占fixed chunk，达到capacity或最大object count（设计例子256，主实验64）后加入FIFO。每个MN hash slot有两个8-byte atomic fields：index包含fingerprint、length和object pointer，group field包含group ID与intra-group sequence number（SN）（§3、§4.1–§4.2、图 6–7）。

Set先用RDMA CAS更新index并把4-bit version加一，再异步write group field及相同version；最后一次write不在critical-path等待。Get始终按index读到一致object data，只有index/group version相同才用group ID/SN记录hotness；race window内可能暂不记这次hit，但不返回错误value。论文没有讨论4-bit version wrap-around的ABA边界（§4.2）。

每个CN按group维护Object Frequency Map（OFM）：每object一个1-byte counter，SN直接作为array offset，无需保存长key。1 GB local table理论可追踪10亿objects；同group连续8个counters可用一次8-byte RDMA FAA合并到MN（§4.3、图 8）。

### 无争用 ring FIFO与lazy synchronization

MN上的FIFO是带cycle count的ring array。4-byte head和tail打包成一个8-byte aligned word；enqueue/dequeue都用FAA取得唯一old value，所以CN之间不锁queue、不做CAS retry。producer先advance tail再异步写node，consumer读到cycle不匹配会retry，避免读到上一圈或尚未填好的slot（§5.1、图 9）。

CN每个detection interval读head，发现新nodes进入eviction window后，读其group IDs，并把各自buffered OFM批量flush。论文按最坏0% hit推导插入/淘汰上限约12 objects/µs：16×256 objects的window至少需341 µs走完，100 µs polling提供3.4倍margin。更多RNIC或更快insert rate时动态放大window或缩短interval（§5.2）。

OFM destination默认映射到RNIC on-chip 16 KB ring，head/tail也放device memory，缩短FAA serialization；这是可选加速，不依赖NIC programmability。CN仍负责poll、frequency merge、ranking和object copy（§5.2）。

### 淘汰时重组与hotness-aware FIFO

dequeue一批groups后，CN读取已同步OFMs，跨groups排序objects，把最hot者compact成new group并重新插入。每group尾部有Two-Way Index Map（TWIM），每object 8 bytes，记录length与其hash-slot reverse pointer；CN可只读hot objects并直接更新slots，不必scan整个chunk或重新hash lookup（§5.3、图 10–11）。

virtual segmentation在physical ring node里保存4-bit Segment。新Phase-1 groups从segment 0开始；hot-regrouped group进入更深segment。node到head时segment大于0就减一再放tail；segment为0仍检查OFM，若超过一半objects有非零counter，也reinsert并清零OFM。系统再使用20% small FIFO+80% main FIFO过滤one-hit objects（§5.4–§5.5、图 12）。

## 设计取舍

- **group housekeeping换object-level精度风险**：同步和eviction次数按group摊销；错误成组会一起淘汰，需TWIM regroup和virtual segment补偿。
- **arrival-time grouping换application independence**：无需semantic feature或ML model；temporal locality弱时Phase 1 group更异质，要等一次eviction才净化。
- **lazy hotness换poll/window约束**：避免周期flush全部objects；必须确保所有CN在head推进前完成detect+FAA，否则淘汰依据会过期。
- **ring FIFO换全局priority order**：所有CN都能无锁推进；hotness只能通过requeue次数近似，不能像LRU/LFU精确排序。
- **RNIC device memory换portable fast path**：只用普通RDMA访问小on-chip region，不需要offload code；不同RNIC容量/atomic语义会改变收益，host-memory fallback较慢。
- **fixed chunks换external-fragmentation robustness**：整组回收连续空间；TWIM、未填满chunk和size heterogeneity带来metadata/internal waste。
- **one-sided CN-driven design换failure complexity**：MN CPU不在data path；CN crash时半写FIFO node、未flush OFM或regroup中的pointer update如何恢复，论文未定义。

## 实验与结果

- **平台、baseline与方法**：6台机器组成3 CN+3 MN，每台2×Xeon Gold 6230R、256 GB DRAM、100 Gb/s ConnectX-5；因Ditto prototype只支持1 MN，四系统主对比实际统一用1 MN，多MN只在§6.5比较其余系统。baseline为Ditto、作者移植并增强的S3FIFO-DM/GLCache-DM；后二者已加入FORGE的lock-free Get/Set、contention-free FIFO、batched flush和regroup，属于强化重实现（§6.1）。
- **YCSB**：256-byte objects、20% cache、3 CN共16–256 threads、Zipf `θ=0.99`。FORGE相对所有baselines吞吐高2.0–8.7倍，P50低1.3–5.9倍、P99低3.9–13.3倍；YCSB D的recency模式有时让LRU-like baseline hit ratio更好，FORGE并非每项hit ratio第一（§6.2、图 13）。
- **真实fixed-size traces**：CPhy/Wiki/MSR/IBM用128 threads、object固定256 bytes、cache为trace footprint的5%/10%/20%。相对Ditto与GLCache-DM，FORGE吞吐最高4.5倍，P50/P99最低4.0/7.5倍，平均hit ratio高1.14倍；这是摘要headline的主要口径（§6.3、图 14）。
- **variable-size与fragmentation**：Meta/Twitter保留动态object size，object-level baseline已加24-class slab allocator。相对最强GLCache-DM，FORGE吞吐高1.61–1.93倍，P50/P99低1.43–2.00/1.67–1.95倍，hit ratio高1.02–1.09倍；单MN network最终成为两者瓶颈（§6.4、图 15）。
- **扩展性与敏感性**：Meta-20%中从1扩到3 MN、100–300 CN threads，FORGE比GLCache-DM高1.54–2.02倍；Ditto因不支持multi-MN缺席。IBM低hit workload偏好大group以摊销eviction，CPhy高hit对16–256 group size不敏感。加入100/500 µs miss penalty后，低hit IBM的相对收益会明显缩小，但仍最高2.68倍（§6.5–§6.6、图 16–17）。
- **逐项消融**：write-heavy YCSB A中versioned lock-free index相对locking group-FIFO baseline提高21.5倍吞吐；contention-free FIFO再提高23.1%–57.5%，TWIM regroup提高32.6%–55.8%；hotness-aware FIFO把YCSB A–D hit ratio提高1.12–1.21倍；最后lazy sync在已优化系统上仍最高增18.9%吞吐、降33.3% P50（§6.7、图 18）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| object-level housekeeping在DM中产生同步放大 | LRU/SIEVE/Ditto的hotness+eviction占多数RDMA traffic；atomic干扰read达4.3倍（图 2–3） | ConnectX-5、one-sided RDMA、10% cache microbenchmark | 强（该架构） |
| group+lazy sync可同时改善吞吐和hit ratio | fixed-size real traces上最高4.5倍throughput、平均1.14倍hit ratio（图 14） | 3 CN+1 MN、作者增强的baseline、closed-cache setup | 强（测试内） |
| fixed group能缓解variable-size fragmentation | Meta/Twitter小cache上比GLCache-DM仍高1.61–1.93倍throughput和1.02–1.09倍hit ratio（图 15） | 两组traces、24-class slab baseline；未直接报告memory utilization | 中到强 |
| FIFO predictability使lazy hotness及时可行 | 最坏rate推导给3.4倍window margin；消融再增18.9%throughput（§5.2、图 18） | rate bound基于单RNIC operation ceiling；无delayed-CN/failure test | 中到强 |
| FORGE可随MN带宽扩展 | 300 CN threads时，1→3 MN的throughput约15→25 Mops/s；所有配置下比GLCache-DM高1.54–2.02倍（图 16） | 单Meta-20% trace，Ditto缺席，没有动态elastic resize | 中 |

## 批判性分析

### 论证链条

论文先把“metadata很小所以不重要”的monolithic直觉翻转为traffic breakdown，再用group amortization处理频率、FIFO predictability处理timeliness、OFM/TWIM/segments处理精度，三组trade-off都有对应机制。端到端同时报告throughput、P50/P99和hit ratio，避免只靠少同步换坏cache policy。需要注意headline是整套系统收益：图18中lock-free index相对一个locking baseline就有21.5倍，真正最后加入的lazy sync最高再贡献18.9%，不能把全部4.5倍都归因于“延迟hotness flush”。

### 假设压力测试

若arrival time与reuse毫无关联，Phase 1 groups会混合hot/cold，频繁regroup增加read/copy/index update。若cache很小，group数量不足，fixed chunk/TWIM overhead更突出；若objects极大或group长期填不满，内部浪费可能抵消fragmentation收益。若某CN卡顿超过window margin，它的local OFM来不及flush，全局frequency会低估；论文的12 objects/µs上界只约束RNIC吞吐，不约束scheduler pause、packet loss或CN failure。若workload更符合strict recency，Ditto/LRU可能比frequency-oriented group policy命中更准，YCSB D已出现边界。

### 实验可信度

YCSB、六类真实trace、uniform/variable object、5%–20% cache、16–300 threads、1–3 MN、miss penalty与逐项ablation覆盖面强；baseline甚至加入多项FORGE common mechanisms，减少“旧实现太弱”的问题。反面是S3FIFO/GLCache为作者重实现，Ditto限制主实验只能1 MN；closed system中默认miss的backend penalty不计入request，直到敏感性实验才加入100/500 µs。所有机器硬件相同，MN实际有强CPU但被逻辑上闲置；没有CXL实测、run variance、failure、elastic add/remove或真实backend end-to-end latency。

### 系统性缺陷

FORGE引入4-bit dual-field version、group allocator、per-CN OFMs、FIFO/cycle/window、RNIC ring、TWIM和multi-segment/two-queue policy，metadata consistency面比摘要看起来复杂。Get在version mismatch时会漏记一次hotness虽不影响value correctness，频繁overwrite与4-bit wrap的行为未分析。regroup是多步读hot objects、写new group、更新hash pointers，CN中途失败的atomicity、leak与duplicate recovery未讨论。RNIC device memory fallback保证逻辑正确，却没有量化host fallback端到端性能。多个CN/MN的reconfiguration、queue ownership、metadata replication和disaster recovery也未设计。

## 局限与后续工作

- 在CXL coherent memory、不同RNIC generations和无device-memory平台上实测，分离lazy policy与on-chip acceleration收益。
- 注入slow/crashed CN、lost/delayed RDMA和regroup中途故障，验证window timeliness、pointer一致性、space leak与恢复。
- 报告group fill factor、TWIM/OFM bytes、internal/external fragmentation和effective cache capacity，而不只用hit ratio间接说明。
- 对4-bit version wrap、concurrent overwrite/Get和FIFO producer/consumer race做formal invariant或长时间stress test。
- 用真实backend miss与open-loop client arrivals测end-to-end tail latency、queueing和network saturation，替代只在Get miss处sleep。
- 支持dynamic add/remove CN/MN，测metadata/queue迁移成本，验证“elastic scaling”而非静态扩展。
- 在线调整group size、merge count、segment和window，同时给出recency-heavy、scan与hotspot shift下的policy选择。

## 相关

- **相关概念**：[[Disaggregated-Memory]]、[[RDMA]]、[[Cache-Replacement]]、[[Memory-Fragmentation]]
- **同会议**：[[OSDI-2026]]
