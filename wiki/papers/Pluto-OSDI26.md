---
type: paper
name: Pluto
full_title: "Pluto: High-Performance, Memory-Efficient Distributed Graph Analytics Through Advanced Mirroring"
authors: [Ying-Wei Wu, Christopher J. Rossbach, Mattan Erez]
venue: OSDI
year: 2026
tags: [graph-processing, distributed-systems, mirroring, memory-efficiency, communication-overlap]
source_pdf: "[[osdi26-wu-ying-wei.pdf]]"
source_md: "[[osdi26-wu-ying-wei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Pluto：用高级镜像降低分布式图分析的内存与通信成本（OSDI 2026）

> **原题**：Pluto: High-Performance, Memory-Efficient Distributed Graph Analytics Through Advanced Mirroring

> **一句话总结**：Pluto挑战“凡是可能访问的远端顶点都应复制”的全镜像做法：push算法只保留能合并至少两条本地入边更新的镜像，pull算法在outgoing edge-cut下完全不存镜像；没有副本的phantom通过单向工作迁移提早发送消息。相对同源的D-Galois+全镜像实现，plain graph最快3.8倍、调和平均1.75倍；模拟labeled property graph时最快2.6倍，并把可运行所需节点数降到全镜像的50%–90%。

## 问题与动机

分布式vertex-centric图系统通常把图分区，并在每台host上复制本地边会访问的remote vertex。复制品称为mirror，原始拥有者称为master。程序在一个BSP round内只访问本地master/mirror，通信阶段再把dirty mirror的更新聚合到master并广播结果，以较大内存开销换较少网络消息（§2.3、图 2–3）。

现有系统一般做full mirroring：只要某个remote vertex可能被本地边使用，就分配副本。论文观察到它会产生最高约4倍内存开销；对于property很大的labeled property graph（LPG），复制vertex state尤其昂贵。内存不仅决定单机能否装下分区，也决定最少需要多少节点；增加节点又会增加跨节点边和同步成本（§1、§3.7）。

Pluto的目标不是设计新partitioner，而是在固定的outgoing edge-cut（OEC）上重新判断“副本究竟何时省通信”。答案取决于update model：push中，多条本地边可在一个mirror上合并；pull中，OEC让所有edge sources都与master同机，remote destination的mirror从不被读取。因此，push适合静态部分镜像，pull可以完全无镜像（§2.2、§3.1–§3.2）。

## 关键观察 / 隐含假设

- **观察 1：一条本地入边对应的mirror必定无收益。** push中，它把一次remote update改成一次local update加一次remote synchronization，网络消息没有减少，反而多做本地工作（§3.1.1、图 4）。
  - **设计边界**：Pluto只静态删除“本host恰有一条入边”的确定无收益副本；它不根据运行时访问热度预测所有mirror的价值。两条以上入边即保留，即使实际只有一条活跃。
- **观察 2：OEC下的pull不需要任何mirror。** pull以destination为pivot，顺序读取incoming sources；outgoing edges与source master同机，所以读到的source总是master。对remote destination在本地先写mirror、再同步master只是多做一次更新（§3.2.1）。
  - **依赖假设**：分区必须是OEC，算法必须使用pull形式；换vertex-cut、2D-cut或需要读remote destination state时，推导不再成立。
- **观察 3：没有副本时，发送“要做的更新”比先拉数据再回写更省一程。** work migration把phantom相关计算送到owner，避免request/response；每个phantom在partial-mirroring中只有一条入边，在mirror-free pull中先本地聚合，所以每轮只需一个work message（§3.3.1）。
  - **关键澄清**：迁移消息在compute phase提早发送，但remote work仍到下一communication phase才应用，以保持BSP语义；被重叠的是网络传输，不是远端计算（§3.3.2）。
- **观察 4：省下mirror后，通信buffer可能抵消内存收益。** 论文提出aggregated memory footprint（AMF），同时计入CSR graph storage和运行时peak sync/work buffers，而不是只数每个master有几份replica（§3.7、式 1–3）。
  - **可能失效场景**：CC/KCore等少数round、早期work migration很密的算法，buffer占比高，个别plain-graph配置的AMF收益很小。
- **观察 5：将消息发送摊到整个compute phase，需要专门的通信工程。** Pluto用独立NIC邻近通信核、异步MPI、每worker聚合、跨worker二次合并和buffer pool；不做message aggregation时，所有实验都超过1000秒timeout（§4、§6.4）。
  - **依赖假设**：计算阶段足够长，可掩盖消息发送。节点太多使compute window过短时，work messages会spill到communication phase，speedup呈先升后降。
- **假设 1：固定update model可接受。** Pluto为每个benchmark选push或pull后全程不变；Gemini可按active-set切换，但要同时存incoming/outgoing adjacency，约加倍edge-list storage（§2.2.2、§6.2.2）。
- **假设 2：静态图、一次partition可代表目标场景。** mirror/phantom classification和target local-ID映射都在partition后准备；动态图的edge变化会使分类和预处理失效，论文没有在线维护机制。

## 核心方法

### 推送路径：静态部分镜像（static partial mirroring）

partition完成后，每台host统计指向remote destination的本地入边。只有一条的destination不分配vertex property，记作phantom；两条及以上仍分配mirror。这样，保留的mirror可在本地合并多次更新，再向master发一次同步；phantom则直接产生一次migrated work。图3的例子中，remote G有两条本地入边而保留，remote E只有一条所以变成phantom（§3.1）。

push只遍历active masters的outgoing edges。若source更新并触发push，对应phantom自然就是dirty，无须给phantom保存旧值或dirty bit。代价是每条边的destination可能是master、mirror或phantom，执行时要检查类型并选择atomic local update或`sendWork`（§3.4、§3.6）。

### 拉取路径：无镜像架构（mirror-free architecture）

pull先处理所有masters，再处理所有phantoms。master按incoming edges做本地归约；phantom只用一个临时accumulator合并本轮所有sources，随后把最终结果作为work message发给owner。固定“masters first, phantoms second”顺序让thread只切换一次更新模式，避免每个vertex反复判断类型（§3.2.2、图 7）。

phantom没有上一轮value，无法直接判断本轮accumulator是否变化。Pluto在master value变化时标dirty bit；phantom记录决定当前聚合结果的source，只在该source为dirty时发送。作者声称对deterministic update operator通用，但论文主要以min类BFS/CC说明，没有分别证明sum、非幂等或浮点归约的边界（§3.4、图 6）。

### 工作迁移（work migration）与 ID 处理

sender把phantom上的update函数及参数打包成单向work message。各worker按destination host连续聚合，默认每buffer容纳`2^15`条消息；专用通信thread在compute phase用non-blocking MPI发送/接收，communication phase再执行received work（§3.3、§4）。

普通full-mirror BSP可依赖固定聚合顺序省略global ID。phantom消息按需产生、顺序每轮变化，不能用同一memoization。Pluto预先交换phantom对应master在target host上的local ID，让sender直接写target local ID，receiver无需global-to-local lookup（§3.3.3）。

### 反向依赖（backward dependence）与实现范围

Betweenness Centrality（BC）的backward pass让source依赖outgoing destination；OEC下destination state不在source host，无镜像便无法本地读取。Pluto只在进入backward pass前恢复所有phantom副本并广播值，回退到full mirroring。当前五个benchmark中只有BC需要一次这种转换（§3.5）。

Pluto基于2023年5月fork的D-Galois，以约4,000行C++实现，沿用Gluon与MPI。每host一条通信thread固定到靠近NIC的core，其余worker也pin core；buffer pool预分配并在不足时翻倍，避免持续`malloc/free`（§4）。

## 设计取舍

- **少复制换更多work messages**：内存下降，部分同步从mirror aggregation变成phantom message；收益取决于compute window能否隐藏传输。
- **阈值固定为1换可靠判定**：一条入边必然无收益，不需cost model；也放弃删除“多条入边但运行时很冷”的mirror。
- **mirror-free换固定pull与OEC**：可以删除所有vertex副本；不能自由切换push/pull，也不能直接推广到其他partition scheme。
- **迁移工作换BSP延迟语义**：避免拉数据再回写，仍必须等communication phase应用，不能提供异步/立即可见更新。
- **目标local ID换预处理状态**：receiver lookup便宜；graph repartition、动态增删边或host变化要重建映射。
- **AMF换单一replication factor**：同时反映graph与buffer，接近真实容量；图9仍用平均每host AMF，直到图10才纳入partition imbalance与单节点OOM。
- **内存效率换自适应update model**：Pluto固定push/pull；Gemini的hybrid执行可能在小集群更快，但需双份adjacency。

## 实验与结果

- **平台与方法**：Stampede3 Skylake集群，每节点Intel Xeon Platinum 8160、48 cores、192 GB DDR4，100 Gb/s Omni-Path；测试8、16、24、32、40、48 hosts。六张图为kmer、mag、fb、rmat、kron、clueweb，五个算法为PR、CC、BFS、KCore、BC；PR固定50轮，其余收敛为止，每点取9次独立运行中位数。BFS/BC用push，PR/CC/KCore用pull（§5、表 1）。
- **内存与最少节点**：AMF分解显示mirror-free通常比static partial节省更多；edge factor高的fb/clueweb因edge storage占主导，收益较小。模拟LPG并实际检查每节点192 GB限制后，全镜像/SPM/mirror-free的最少host分别为：mag 26/24/17、kron 46/36/23、clueweb 47/43/41等；总体Pluto只需全镜像的50%–90%节点（§6.1、图 9–10）。
- **跨系统最快配置**：在每个workload上从8–48 hosts选最快点，Pluto相对Graphite、原D-Galois、Gemini等既有open-source系统最高12倍，§6.2.1报告调和平均2.5倍；表2的30个组合均由Pluto最快。论文摘要却把open-source调和平均写成1.75倍，与引言和正文的2.5倍不一致，应以后者为主并保留此不一致（§1、§6.2.1、表 2）。
- **隔离高级镜像贡献**：对带communication isolation的同源full-mirroring D-Galois+，plain graph最高3.8倍、调和平均1.75倍。speedup随host数通常先升后降：起初compute太长，重叠只占小比例；中间最匹配；再扩展后compute window太短，work messages溢回通信阶段（§6.3.1、图 11–12）。
- **LPG边界**：真实大规模LPG不足，论文把LDBC中测得的vertex/edge property-size分布套到六张plain graphs，并给算法加property predicate；这不是原生LPG trace。计算占比上升后，通信优化相对收益缩小，但仍最高2.6倍、调和平均1.37倍（§5、§6.3.2、图 8、图 13）。
- **消融**：关闭communication isolation后，归一化时间随host数从约2.6倍升到4.6倍；关闭dirty phantom identification约1.45–1.6倍，buffer pool和固定遍历顺序只约1.05–1.15倍。最关键的message aggregation未画入图14，因为一旦关闭，所有实验都超过1000秒timeout；这说明headline性能依赖整套通信substrate，不只是“少几个mirror”（§6.4、图 14）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| full mirroring包含可确定删除的无收益副本 | push中单入边mirror不减少remote update；数据集有较高nonproductive fraction（§3.1、图 5） | OEC、push、静态图；没有覆盖运行时冷的多入边mirror | 强（定义内） |
| advanced mirroring既省内存又能提速 | 对同源D-Galois+，plain graph最高3.8倍、调和平均1.75倍；AMF多数低于1（图 9、12） | 100 Gb/s集群、六图五算法；不同host数存在spillover | 强（评测集内） |
| Pluto能显著降低LPG所需集群规模 | 实际容量检查中只需全镜像50%–90%的hosts（图 10） | property来自LDBC分布合成，不是真实大规模LPG；固定192 GB节点 | 中到强 |
| Pluto优于现有distributed graph systems | 30个表格组合均最快，正文报告最高12倍、调和平均2.5倍（表 2） | 系统的programming/update model不同；每系统各取最佳host数 | 中 |
| work migration的高流量可被有效管理 | 完整Pluto最佳；无aggregation全部timeout，无communication isolation慢2.6–4.6倍（图 14） | 只测Omni-Path+MPI；没有以不同RTT/带宽扫参 | 强（该substrate） |

## 批判性分析

### 论证链条

论文最强的部分是从update semantics而非“热门vertex经验”推导mirror需求：push的单入边mirror数学上不省消息，OEC pull的mirror根本不被读。D-Galois+同源基线把高级镜像本身与跨系统工程差异分开，AMF也避免只报告replication factor。需要降调的是“advanced mirroring本身带来全部性能”：work migration把流量移到compute phase后，message aggregation、通信核隔离和dirty识别是成败条件；无aggregation时系统完全超时。

### 假设压力测试

若图动态增加第二条本地入边，原phantom应升级为mirror；删除边又可能让mirror变无收益，当前静态preprocessing不能处理。若partition不是OEC，pull读取的source未必都是local master，mirror-free推导失效。若每轮compute很短、网络RTT高或host数过多，消息无法在barrier前发完，speedup会下降。若算法要backward read、异步更新、跨多轮保存remote state或使用非确定/浮点聚合，phantom dirty推断与BSP work application都需重新证明。

### 实验可信度

六张大图、五种算法、8–48节点、9次中位数、open-source基线与同源基线构成了扎实评测；图9还把peak work buffer计入内存，图10进一步检查最坏host OOM。限制也很清楚：只测一个老Skylake/Omni-Path集群和OEC；没有误差条、tail round、network counters或失败注入；LPG属性是从较小LDBC图抽取分布后合成，graph topology与property correlation并不真实。跨系统比较还混入vertex-centric对linear algebra、fixed update对hybrid update及不同实现成熟度，不能全归因于mirroring。

### 系统性缺陷

Pluto把固定partition、固定update model和BSP barrier写进设计核心，动态图、online repartition和asynchronous graph engines很难直接采用。memory与performance目标也可能冲突：为了mirror-free pull要保留incoming adjacency；若同时需要push，就要双份edges并失去部分内存优势。work messages把执行逻辑跨节点传递，需要序列化、版本一致性、backpressure和错误处理，但论文只讨论正常执行。没有fault tolerance、straggler恢复、host loss或重复消息语义；通信thread是单点瓶颈。BC在backward pass突然重建full mirroring可能造成峰值内存/OOM，论文没有单独报告转换cost和峰值。

## 局限与后续工作

- 支持dynamic edge和online repartition，量化phantom↔mirror转换、target local-ID重建与在途work message一致性。
- 在Ethernet/[[RDMA|RDMA]]、不同RTT/带宽和每节点core数上扫参，画出compute-window、aggregation size与spillover的break-even点。
- 用真实大规模LPG与production query mix验证property-size/topology correlation，而不是只把LDBC属性分布套到plain graph。
- 报告每轮消息数、bytes、overlap比例、buffer peak、network utilization和p95 runtime，解释哪些graph/algorithm产生最高3.8倍。
- 测BC进入backward pass时的复制峰值、转换延迟和OOM边界，并为双向依赖设计不完全回退full mirror的方案。
- 加入host failure、消息重复/丢失、straggler与checkpoint测试，明确work migration在BSP retry下的幂等语义。
- 探索在严格memory budget内按phase选择push/pull和mirror set，而不是永久固定update model。

## 相关

- **相关概念**：[[Distributed-Graph-Processing]]、[[Bulk-Synchronous-Parallel]]、[[Work-Migration]]、[[Graph-Partitioning]]
- **同会议**：[[OSDI-2026]]
