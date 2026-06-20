---
type: paper
name: RCuckoo
full_title: "Cuckoo for Clients: Disaggregated Cuckoo Hashing"
authors: [Stewart Grant, Alex C. Snoeren]
venue: ATC
year: 2025
tags: [rdma, disaggregated-memory, key-value-store, cuckoo-hashing, one-sided-rdma, fault-tolerance]
source_pdf: "[[atc2025-grant.pdf]]"
source_md: "[[atc2025-grant]]"
---

# Cuckoo for Clients: Disaggregated Cuckoo Hashing (ATC 2025)

> **一句话总结**：RCuckoo 抓住 small-value disaggregated KVS 在 100-Gbps [[RDMA]] 上已从带宽瓶颈转向 RTT、remote atomic 与锁竞争瓶颈这一观察，用 locality-enhanced dependent hashing + NIC-memory MCAS locks 把纯 one-sided RDMA cuckoo hash table 的常见路径压到 inlined read 1 RTT、update/delete 2 RTT、median insert 2 RTT；在 320 clients 的 YCSB-B 上最高 2.5×、写密集 YCSB-A 相比部分系统最高 7.1×，但结论强依赖小 value、ConnectX-5 device memory/MCAS、以及 90-95% fill 附近 cuckoo path 仍保持局部性。

## 问题与动机

Memory disaggregation 的承诺是把 DRAM 池化，避免每台机器按 peak-of-sums 过度配置。但只把远端内存暴露出来还不够：如果多个 compute client 需要共享同一块 pooled memory，就必须有一个 coherence/serialization 层。论文选择的抽象是 key/value store，而不是 general-purpose remote memory paging，因为 KVS 可以把共享访问约束在 read/update/delete/insert 这些较明确的操作上。

现有 RDMA KVS 大致分两类。第一类是 FaRM、Sherman 这类带 server-side CPU 或 memory-side worker 的系统，用 two-sided RDMA 或服务端逻辑处理复杂更新，性能强但不再是完全被动的 memory server。第二类是 FUSEE、Clover 一类更接近 fully disaggregated 的系统，倾向 lock-free optimistic protocol，用 8-byte atomic-friendly index entry 指向 extent；这样可以避免锁，但 small-value read 通常要先读 index 再读 extent，写密集场景也会被 CAS、retry 和 metadata path 拖住。

RCuckoo 的反直觉点是重新启用 locks。传统经验认为 remote locks 在 RDMA 上很危险，因为 remote atomic 吞吐有限，contended CAS 会把 NIC/PCIe 打成瓶颈，client failure 持锁更会造成恢复复杂度。论文的核心主张是：如果锁足够细、持锁时间足够短、锁表小到能放进 NIC device memory，并且 cuckoo path 的空间跨度可以被概率性压小，那么 lock-based cuckoo hashing 反而比 lock-free extent index 更适合 small-value shared remote memory。

## 关键观察 / 隐含假设

- **观察 1：small-value RDMA KVS 的瓶颈从带宽转向 round trip 与 dependent access。** 论文用 Figure 1(a) 说明，在测试机上单次 1-KB RDMA read 的 latency 低于两次依赖的小 read；Figure 8(d) 进一步显示 inline values + single read 对 YCSB-B/A 分别带来 21%/37% 性能收益。
  - **依赖假设**：目标 workload 以 small key/value 为主，100-Gbps 级网络还没有被 value payload 打满；operation rate、dependent RTT、cache miss 才是关键瓶颈。
  - **可能失效场景**：value 大到很快到 line rate 时，RCuckoo 的 inline/covering read 会变成 bandwidth amplification；论文也显示 read performance 在约 64B value 后开始 link-rate limited。

- **观察 2：RDMA locks 不是一概不可用，瓶颈在 lock placement 和 acquisition span。** Host memory 上 atomic throughput 很快封顶，contended CAS 只有约 3 MOPS；ConnectX NIC device memory 上 contended atomic 可以约 3.1×，independent address 约 1.8×。如果锁表放进 256 KB NIC memory，并用 masked CAS 一次拿最多 64 个 1-bit locks，锁的 common path 可以变短。
  - **依赖假设**：部署硬件支持 OFED-4.9 的 MCAS 和 device-mapped memory；lock table 能被压到 NIC memory 内；client 数和热点不会让少数 physical locks 长时间饱和。
  - **可能失效场景**：没有 MCAS/device memory 的 RDMA NIC、跨厂商 RDMA 栈、或表规模过大导致 virtual lock false sharing 明显上升时，lock-based 路线的优势会被削弱。

- **观察 3：传统 cuckoo hashing 的随机性对 fully disaggregated insert 太贵，但完全固定 locality 又会牺牲 fill factor。** 独立 hash 让 cuckoo path 跨随机远端 row，client 必须多轮 RDMA read 和分散加锁；固定 bound 又会让 max fill 只有约 10-15%。RCuckoo 的 dependent hashing 用概率性 bounded offset，在 f=2.3 时保持 95%+ expected max fill，同时 68% 的 key 两个位置相距 5 行以内，95% insert path span 不超过 32 rows，近 99% 不超过 256 rows。
  - **依赖假设**：hash 分布足够均匀，BFS cuckoo path search 的局部路径确实存在；table row 有 8-way associativity，且 fill factor 主要落在论文评估的 90-95% 区间。
  - **可能失效场景**：极高 fill、insert-only burst、adversarial key distribution 或 shard 内局部热点会把 dependent hashing 的 locality 变成 hot spot 和 lock contention。

- **假设 1：client failure 是 rare event，100 ms timeout 足以区分失败与慢操作。**
  - **证据强度**：中。论文给出 99th-percentile insert 约 50 us、search 和 message propagation 是 single-digit microseconds，因此 100 ms 很保守；但 stale slow client 仍需要额外 liveness protocol，论文没有在真实生产故障模型下证明。

- **假设 2：单 memory server 的实验足以代表 disaggregated shared-memory KVS 的核心瓶颈。**
  - **证据强度**：中偏弱。单 server 能暴露 one-sided operation、lock table 和 index layout 的瓶颈，但多 server sharding、replication、rebalancing、server failure 和 resize 都被推到 future work。

## 核心方法

RCuckoo 是一个 fully disaggregated, lock-based [[Cuckoo-Hashing]] KVS：memory server 被动暴露 RDMA-registered memory，所有 protocol logic 都在 clients 上完成。Index table 是 main memory 中的 row array，每行包含固定数量的 associative entries（实验用 8 个）、8-bit version 和 64-bit CRC。Entry 可以直接 inline key/value，也可以存 key + 48-bit pointer + size 指向 extent。CRC 用来检测 torn write 或失败修复过程中的中间状态，version 用来帮助判断 row 是否发生 mutation。

Read path 是论文最清楚的收益点。Client 用 dependent hash 算出 key 的两个候选 rows，然后并发读两行；如果两行相邻，还可以发一个 covering read 读回连续区域。Small value 被 inline 时，命中任一 row 且 CRC valid 就能 1 RTT 完成；large value 才需要第二个 RTT 读 extent。这直接回应观察 1：为了少一次 dependent access，RCuckoo 接受一点 I/O amplification。

Update/delete path 需要锁住两个候选 rows。由于 dependent hashing 通常让两行很近，client 往往可以用一次 MCAS 拿到对应 locks，并在同一 batch 里读 rows。更新时 client 写回 entry、row version 和 CRC，再按顺序释放 lock；extent value 更新会先把新 value 写到 client 私有 extent region，再释放旧 extent。常见 uncontested update/delete 是 2 RTT。

Insert 是设计的核心。Client 先用本地 RDMA-registered index cache 做 speculative BFS cuckoo-path search；cache 可能 stale，所以这个阶段只用于提出候选 path。随后 client 根据候选 path 计算需要锁住的 rows，用 MCAS 按地址递增顺序拿 locks，并在同一 batch 里同步被锁覆盖的 rows 到 cache。拿锁成功后，client 在“已锁且新鲜”的局部 cache 内做 second search：如果原 path 或替代 path 仍然可行，就从 path 尾部的空槽开始倒序执行 cuckoo moves，逐行写 entry/version/CRC，最后释放 locks；如果不可行，就释放 locks 并重试。

Locality-enhanced dependent hashing 是把 cuckoo hashing 变成 RDMA-friendly 的关键。Primary location 仍均匀随机，secondary location 是 primary 加一个由 h2、h3 和参数 f 控制的概率 bounded offset；offset 越大概率越低。这个机制保留了 cuckoo hashing 高 fill 的概率性，同时让大多数 key 的两个位置和 insert path 都落在小范围内，从而提升 covering read、single-MCAS lock acquisition 和 second-search 成功率。

Fault tolerance 也沿着“client-only protocol”走。Locks 是 bit vector，不记录 owner；如果 client timeout 后怀疑某个 lock 被失败 client 持有，就先获取覆盖对应 index region 的 repair lease。修复者读取 lock 覆盖的 rows，把部分 insert 留下的状态归为四类：duplicate + bad CRC、duplicate + good CRC、no duplicate + bad CRC、或没有 corruption。修复按 deterministic sequence 前进：先补 CRC，再清 secondary duplicate，或直接重算 bad row CRC，最后释放 stranded lock。这个协议保证已存在 key 不丢，失败 client 正在插入的新 key 可以视为未完成。

## 设计取舍

- **用 lock-based protocol 换 small-value read/update 效率**：RCuckoo 牺牲了 lock-free optimistic path 的简单 failure model，换来 inline value、single-round-trip read 和较短 update path。收益集中在 small-value mixed workloads；代价是 lock contention、timeout tuning 和 repair logic。
- **用 probabilistic locality 换 predictable RDMA access span**：dependent hashing 降低 cuckoo path span 和 MCAS 次数，但它不是 free lunch。f 越小 locality 越强，越容易 hot spot 和低 fill；f 越大 fill 更好但路径又接近随机。论文选择 f=2.3 是实测 sweet spot，而不是理论最优。
- **用 NIC memory single-bit lock table 换硬件依赖**：1-bit locks + MCAS 最大化 256 KB NIC device memory 的覆盖范围，也让 contended atomic 更快；但超大表需要 virtual locks，多 logical locks 映射到一个 physical bit 会引入额外 false sharing。
- **用 inline value 换 bandwidth amplification**：inline entries 让 read 少一次 extent access，但 entry 变大后 insert 会变得 bandwidth-limited。Figure 8(c) 显示 read-only 对 entry size 不敏感，50% insert/read 则随 8/16/32/64B entry 变大明显下降。
- **用 passive memory simplicity 换系统完整性**：RCuckoo 避免 memory-side CPU，接口和部署模型很干净；但 resize、replication、server failure、multi-shard load balancing 和 stale slow client fencing 都没有完整实现。

## 实验与结果

- **实现与环境**：高性能实现是 8.7K LOC C++，另有 12K LOC Python RDMA simulator 做 correctness testing。实验依赖 OFED-4.9、ConnectX-5 MCAS 和 device-mapped memory；9 台 dual-socket Intel Xeon E5-2650 机器，每台 256 GB RAM、100-Gbps Mellanox switch；RCuckoo 用 1 台 memory server，其余 client machines 分摊线程，client index cache 64 KB。
- **主 workload**：100M-entry table，预填 90M entries，32-bit key + 32-bit value，Zipf(0.99)，比较 FUSEE、Clover、Sherman。FUSEE 作为 fully disaggregated lock-free baseline 且关闭 replication；Clover 有 metadata server 和 client caching；Sherman 是 lock-based distributed B-tree，功能更强但不是 fully disaggregated。
- **YCSB-C read-only**：RCuckoo、Clover、Sherman 在低中并发接近，scale 后 RCuckoo 最高；FUSEE 因为 extent-based value storage 要多一次 read 而落后。Clover 在 Zipf skew 下 cache 命中很好，论文指出 uniform workload 下会下降。
- **YCSB-B 95% read / 5% update**：少量 update 就让 Sherman 在 skewed workload 下因 lock contention 出现瓶颈，Clover 的 cache 优势也被 invalidation/update 削弱。RCuckoo 在 320 clients 下最高约 2.5×。
- **YCSB-A 50% read / 50% update**：RCuckoo 和 FUSEE 接近，但 FUSEE 在测试床上无法扩到 250 clients 以上，RCuckoo 继续 scale；Sherman 约 5 MOPS 后 collapse，Clover 在 write-heavy 下最弱。论文的“最高 7.1×”更像是相对 Sherman/Clover 这类 comparison points，而不是对所有 baseline 都稳定 7.1×。
- **Insert 随 fill factor 变差但仍受控**：insert-only 时，RCuckoo 从近空表的 11.5 MOPS 降到 90% fill 的 4.5 MOPS；FUSEE 最大 insert-only 约 9.1 MOPS 且基本不受 fill 影响，因此高 fill insert-only 是 RCuckoo 的弱点。论文强调 insert-only 在实际 KVS 中少见。到 90% fill 时，per-operation bytes 最多约 2×，RDMA message count 不超过约 1.5×。
- **Locality microbenchmark**：在 85% 预填到 95% 的 insert 测试里，dependent hashing + BFS 的 median 与 independent hashing 同量级，但 99th-percentile insert round trips 比 independent hashing + DFS 少一个数量级；4 个以上 locks per message 时表现相近，说明 MCAS batching 是关键。
- **Fault tolerance**：注入 partial insert failure 并随机截断 RDMA batch 后，RCuckoo 在每秒数百个 client failures 下仍保持高吞吐，约 500 failures/s 后 lock granularity 开始主导下降。论文给出参考：RDMA server 建连能力约 1.4K connections/s，因此 500 failures/s 已接近非常激进的 churn。
- **Value/entry size**：inline 8B value 在 YCSB-B/A 分别带来 21%/37% 改善；read performance 在 value size 约 64B 后开始被 100-Gbps link-rate 限制，说明“大 value”不是 RCuckoo 主战场。

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条总体闭合：先证明 small-value RDMA workload 中 dependent RTT 和 remote atomic contention 重要，再用 inline entries 减少 read RTT，用 dependent hashing 缩短 cuckoo path span，用 NIC-memory MCAS 缓解 lock acquisition，最后在 YCSB mixed workloads 中展示吞吐优势。最强的部分是把“锁不可用”的 received wisdom 拆成几个具体条件：锁表在哪里、一次拿多少锁、锁覆盖多大范围、持锁多久、失败如何 repair。

主要跳步在于把单 memory server + synthetic YCSB 推到“pooled memory practical KVS”的广义 claim。RCuckoo 证明了一个 data-structure/protocol kernel 很强，但完整 memory disaggregation 系统还需要 replication、resize、multi-server sharding、tenant isolation 和 operational fencing。论文承认这些大多是 future work，因此贡献更像是“fully disaggregated lock-based hash table can be fast”，而不是完整生产 KVS。

### 假设压力测试

第一类压力来自 workload。RCuckoo 赢在 small values、read/update mixed、Zipf skew、较少 insert-only burst。高 fill insert-only 时 FUSEE 反而更好；large value 时优势会被 link bandwidth 吃掉；uniform workload 下 Sherman lock contention 下降、Clover cache 行为也会变化。论文有提到部分未展示 uniform 结果，但没有系统画出 distribution sensitivity。

第二类压力来自硬件。MCAS、ConnectX-5 device memory、256 KB NIC memory、OFED-4.9 是实现路径的一等前提。没有这些特性时，锁表可能回到 host memory，contended atomic 和 PCIe round trip 会重新成为瓶颈。这个设计很“2025 Mellanox-specific”：很工程有效，但跨 NIC generation/vendor 的可移植性需要进一步验证。

第三类压力来自 failure semantics。RCuckoo 能修复 fail-stop client 持锁导致的 torn row/duplicate state，但 slow client 被误判失败后继续发 stale writes 的问题没有在 RCuckoo 内部解决，只建议外部 liveness protocol 或极端的 QP reset 技巧。100 ms timeout 对性能路径很安全，却可能在真实 tail latency、network pause、GC pause 或 host overload 下产生可观测的长尾和误判。

### 实验可信度

实验覆盖了主路径、insert fill factor、failure injection 和关键 microbenchmark，足以支撑“RCuckoo 的核心设计在 small-value synthetic workload 下有效”。Baselines 选择也合理：FUSEE 是最接近 fully disaggregated 的 comparison，Clover/Sherman 覆盖 cache-based 和 lock-based designs。

但 apples-to-apples 仍有边界。Sherman 支持 range query 且是多 server B-tree，不是同一功能点；Clover 有 metadata server，目标包含 persistent memory；FUSEE 原本支持 replication，实验关闭 replication。RCuckoo 自身没有 replication/resizing/server failure，因此比较的是 data-path performance，而不是完整 system feature set。YCSB Zipf(0.99) 是标准但不等同 production trace；32-bit key/value 也把 workload 推到了最有利于 inline read 的区域。

### 系统性缺陷

RCuckoo 的实现复杂度不低：speculative search、cache synchronization、second search、batched ordered writes、CRC/version repair、lease recovery 和 virtual locks 都必须正确交织。论文用 Python simulator 做 correctness testing 是加分项，但 page-level note 应记住：这是用很多协议细节换来的“简单 memory server”，不是整体系统变简单。

资源隔离和公平性也未充分讨论。Fine-grained locks 提高并发，但 hot keys/hot ranges、virtual lock collision、repair lease contention 都可能造成局部 unfairness。论文提到 Citron 的 fair bakery algorithm 可能作为 future work，说明当前 RCuckoo 优先 raw common-case performance，而不是公平 lock scheduling。

可观测性和运维风险基本缺席。生产环境需要知道哪些 locks 被频繁 timeout、哪些 virtual locks false share、哪些 clients stale、repair 是否反复发生、CRC mismatch 是 torn write 还是硬件/软件 bug。论文的协议能恢复局部表状态，但没有给出足够的 diagnosis surface。

## 局限与 Future Work

- **局限 1：只覆盖 small-value, single-server data path。** 需要在 multi-memory-server sharding + replication + realistic trace 上测量：吞吐、tail latency、fill factor、rebalancing 成本和 recovery time。
- **局限 2：高 fill insert-only 是弱点。** 可验证的后续问题是：在 90-97% fill、不同 insert/update/delete mix 下，是否存在 adaptive f、stash、局部 rehash 或 hybrid FUSEE-style extent index 能避免 4.5 MOPS 级别的下降。
- **局限 3：stale slow client 没有内建 fencing。** Future work 应实现 one-sided liveness table 或外部 lease service，并量化 false failure、recovery latency、stale write prevention 和 throughput cost。
- **局限 4：硬件依赖强。** 需要在 ConnectX-6/7、RoCEv2、不同 OFED 版本、以及没有 MCAS/device memory 的 NIC 上重跑 lock-table microbench，判断设计是通用 RDMA pattern 还是特定平台 sweet spot。
- **局限 5：公平性与隔离不是目标。** 可以把 Citron-style fair range locks 或 admission control 接到 RCuckoo，测量 hot-key workload 下 p99/p999 latency、lock starvation 和 throughput tradeoff。
- **Future work 1：在线 resize 和 shard migration。** 目标指标应包括迁移期间的 read/update correctness、blocked time、extra RDMA traffic 和 fill-factor recovery，而不是只说“支持扩容”。
- **Future work 2：把 repair path 变成 first-class observability。** 记录 lock timeout、lease acquisition、CRC repair、duplicate cleanup 和 retry 原因，验证这些 counters 是否能预测即将出现的 contention collapse。

## 相关

- **相关概念**：[[RDMA]]、[[Cuckoo-Hashing]]、[[Disaggregated-Memory]]、[[One-Sided-RDMA]]、[[Key-Value-Store]]
- **同类系统**：[[FUSEE]]、[[Clover]]、[[Sherman]]、[[FaRM]]
- **同会议**：[[ATC-2025]]
