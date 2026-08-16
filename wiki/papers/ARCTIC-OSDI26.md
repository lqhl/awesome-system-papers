---
type: paper
name: ARCTIC
full_title: "Arctic: a practical lock-free adaptive radix tree"
authors: [Newton Ni, Nicolas Garza, Jenny Stinehour, Michael Goppert, Michal Friedman, Emmett Witchel]
venue: OSDI
year: 2026
tags: [concurrent-data-structure, adaptive-radix-tree, lock-free, memory-reclamation, database-index]
source_pdf: "[[osdi26-ni.pdf]]"
source_md: "[[osdi26-ni]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# ARCTIC：实用的无锁自适应基数树（OSDI 2026）

> **原题**：Arctic: a practical lock-free adaptive radix tree

> **一句话总结**：ARCTIC 重排 ART 的 edge/node metadata，让常见更新只改一个 128-bit atomic word；需要替换 node 时，先冻结所有可写位置，其他 thread 可以帮助完成，而不是等锁。它让 point read wait-free、update lock-free，也支持 wait-free 但非线性一致的 range scan，并提出用 operation key 近似保护 pointer 的 hazard keys 回收方案。

## 问题与动机

并发内存索引通常很难同时得到三个性质（§1）：

1. **高性能**：point lookup/update 要有好的 cache locality，不能经过很多 indirection。
2. **无锁进展（lock freedom）**：即使某个 thread 被暂停或 crash，系统中仍有 operation 能在有限步骤内完成。
3. **range/prefix scan**：index 必须有序，能按 key range 遍历。

concurrent hash map 很快且可以 lock-free，但不能高效 range scan。skiplist 有序，却有 pointer chasing 和高层热点。B+-tree 常靠 optimistic lock coupling；lock-free Bw-tree 用 delta record 和 mapping table 换掉锁，又增加 traversal indirection。ART 是 cache-friendly 的有序 radix tree，但主流 ROWEX ART 会锁 node；已有 lock-free ART variant 往往放大 node、放弃回收，或让 writer 在 structural modification operation（SMO）期间仍可能阻塞（§1、§5）。

这在 thread oversubscription 时尤其重要：持锁 thread 若被 OS deschedule，等同一把锁的其他 thread 都停下。ARCTIC 的目标不是只把 lock 改成 CAS，而是在不加入额外 pointer layer、仍然原地更新 node 的前提下，让任何 thread 都能帮助完成结构变化。

## 背景与适用前提

radix tree 把 key 看作 byte sequence。edge compression 把连续公共 bytes 放到一条 edge 上，减少树高；node compression 根据 child 数量选择小/大 node，减少 sparse array 的空间。ART 把压缩 edge bytes 放在 child node header 中，ARCTIC 则把它们上移到 parent edge，与 child pointer 放在同一个 atomic unit（§2.2、图 1）。

所有这类 prefix tree 都有一个重要前提：**任何 key 都不能是另一个 key 的 prefix**（Precondition 1）。fixed-width integer 和以 `\0` 结尾的 C string 自然满足；其他 variable-length key 要附加 sentinel byte。否则同一位置既要表示 value 又要表示 node，当前 layout 无法处理。

论文中的 scan 也需要先说清语义：point get 是 linearizable 且 wait-free，insert/delete 是 linearizable 且 lock-free；range/prefix scan 是 wait-free，但**不是 linearizable snapshot**。scan 保证 key 最多出现一次、按 lexicographic order 返回，并看到所有“scan 开始前已插入且直到 scan 结束仍未删除”的 key（§3.7）。需要 transaction snapshot 的 database 必须由上层 MVCC 或“scan 时没有 writer”的 phase 提供语义。

## 关键观察 / 隐含假设

- **观察 1：ART 难以无锁化，主要因为一个 SMO 要改两个位置。** edge bytes 在 child header、pointer 在 parent edge；edge expansion 因而要同时更新 parent 和 child。ARCTIC 把 bytes 上移，让 edge 的 compressed bytes、type tag、frozen bit 和 child 能用一次 128-bit CAS 更新（§3.2、图 4–5）。
  - **依赖假设**：平台提供正确的 128-bit CAS；高性能实现还需要 128-bit atomic load。论文列出 x86 `CMPXCHG16B` 和 ARM LSE `CASP`，只在 x86 server 上评测。
- **观察 2：先冻结 node，再让替换结果只由 frozen contents 决定，任何 thread 都可以帮助。** 这样不需要等待最初发起 SMO 的 thread（§3.3）。
  - **依赖假设**：每个可 CAS 的 header/edge 都包含 frozen bit，所有 writer 都检查它；漏掉一个写入口就可能更新已经 unreachable 的 node。
- **观察 3：point operation 的 logical key 限定了它会访问哪些 prefix。** operation key 为 `k` 时，只可能访问 prefix 是 `k` 前缀的 node/value；因此可以发布一次 key，近似一组 hazard pointer（§3.9、图 6）。
  - **依赖假设**：reclaimer 能为 retired allocation 保存正确 prefix；request skew 不能长期让同一宽 prefix 一直受保护。
- **观察 4：常见 update 只需 CAS final edge。** YCSB-A update 不重建路径，也不锁整个 node，所以横向不同 edge、纵向不同 level 都可并发（§3.1、§4.1）。
  - **依赖假设**：workload 以 point operation 为主，SMO 相对少；频繁 grow/shrink 或 adversarial prefix churn 可能反复 freeze 大 node。
- **观察 5：长 string 的树深仍然与 key length 成正比。** ARCTIC 优化了同步和 metadata，不会改变 radix traversal 的基本成本（§4.1）。
  - **适用边界**：integer、IPv4、UUID 等较短 key 表现最好；email/URL 的 read-only workload 不一定胜过 hash/hybrid baseline。

## 核心方法

### 128-bit edge 与 node layout

每条 edge 总共 16 bytes：一半保存最多 7 个 compressed key byte、length、value/frozen bit，另一半保存 64-bit child union。child 可以是 null、user value，或带 lower-two-bit type tag 的 aligned node pointer（图 5）。把 node type tag 也上移到 parent edge 后，读取 child type 不必再加载 child header。

ARCTIC 使用四种 node：一个 cache line 的 `Node3`（64 B）、`Node15`（256 B）、`Node47`（1,024 B）和刚好一页的 `Node256`（4,096 B）。所有大小都是 2 的幂。`Node256` 直接按一个 byte 索引 256 条 edge，不需要 header metadata，也避免跨两个 page。相对 ART 的 `Node4/16/48/256`，容量稍作调整，是为了给 frozen state 和 atomic header 留出位置（§3.2）。

这个 layout 直接简化 edge expansion：先在 local memory 构造一个小 node，再用一次 CAS 把原 edge 从“长 compressed bytes + old child”换成“短 bytes + new intermediate node”。新 node 在 CAS 前不可达，CAS 失败即可直接释放，不涉及并发回收（§3.3）。

### freezing 与统一 node replacement

node expansion、node compression、edge compression 和空 node deletion 都需要把旧 node unlink，再让 parent 指向新 node。若先 copy 旧 node，再 CAS parent，copy 期间的并发 update 可能丢失。ARCTIC 先逐个 CAS node header 和所有 edge 的 frozen bit；writer 只允许在 frozen bit 未设置时修改，所以全部位置 frozen 后，旧 node 内容不可再变（§2.4、§3.3、图 3）。

ARCTIC 不在开始时决定“我要 expand 还是 delete”，而是在 freeze 完成后，根据最终内容确定一个唯一 replacement。可能同时参与的多个 thread 会看到相同 frozen contents，构造逻辑等价的新 node。谁先成功 CAS parent，谁完成 unlink；其余失败者丢弃自己的 local copy。这样 replacement 是幂等、可帮助的，不会因为最初 thread 被暂停而卡住。

writer CAS 失败后分两种情况。若目标未 frozen，说明别的 operation 改了 edge/header，writer 从当前位置继续 traversal。若 frozen，writer 不能等待，而是回到该 node 的 parent edge，帮助做 node replacement；若 parent 又 frozen，就继续向上帮助。实现先走不保存 stack 的 optimistic path，只有真的遇到 frozen failure 才从 root 重启并记录 backtracking stack（§3.5、§3.10）。在论文最容易产生 SMO conflict 的 100 M random 8-byte insert、80-thread test 中，只有 324 次进入 frozen-failure case，没有一次回退超过一层；作者称从未观察到超过两层，但这不是 worst-case 上界。

### partial node 的原子 append

`Node3` 和 `Node15` 的 key-byte mapping、length 都能放进一个 128-bit header，可一次 CAS 加入新 mapping。`Node47` 的 256-entry inverse map 太大，无法连同 length 一次更新。ARCTIC 在 header 增加 `last`，记录最近 append 的 key byte（§3.3）。

thread 先检查 `indices[last] == len-1`。若不一致，表示前一个 append 只更新了 `len/last`，尚未更新 inverse map；当前 thread 先 CAS map 帮它完成。随后 CAS 自己的新 `len/last`，再帮自己写 map。reader 不看 `len/last`，writer 和 freezer 都会先帮助 map 达到一致，所以两次 CAS 中间的状态不会成为逻辑可见的 mapping。这个 helping protocol 是 ARCTIC 少数不是单 CAS 完成的 SMO。

### traversal、更新与 scan

point traversal 从 root edge 开始，先比较 compressed bytes，再按下一个 key byte 选 child edge。它从不等待、从不回退，也不与 freezing 交互，所以是 wait-free（算法 1）。即使读到 frozen、随后被 unlink 的 node，node 内容已经 immutable；论文把 get 的 linearization point 放在 edge freeze 到 replacement 之间的一个时刻（Claim 4）。

insert 找到 null final edge 后 CAS 成 value，delete CAS 回 null；必要时先做 edge expansion、node creation/append/replacement。成功 CAS 是 linearization point。delete 后是否立刻扫描并压缩空 node 是性能/空间取舍：小 node 扫描便宜，大 `Node47/256` 扫描贵，也可以以后异步 replacement（§3.6）。论文没有把一种清理策略提升为接口保证。

range/prefix scan 按 node mapping 的有序结构遍历，所以不用锁也能 wait-free 完成，但并发 writer 可能让结果来自多个时间点。ARCTIC 将这点明确留给 [[RocksDB]] compaction 的 writer-free phase或 Turso MVCC 一类上层机制解决（§3.7、§4.2）。

### hazard keys：用 key 近似 pointer protection

传统 hazard pointer 在每次 pointer load 前发布并验证精确地址，回收内存有界，但 hot path 成本高。epoch-based reclamation（EBR）只在 operation boundary 记录 epoch，开销低；一个 stalled thread 却可能阻止所有 retired object 回收（§2.5）。

hazard keys 的协议是（§3.9）：

1. retired node/value 同时记录它在 tree 中的 logical prefix `p`。
2. operation 开始前只发布一次完整 key `k`。
3. 若 `p` 是任一 active `k` 的 prefix，就暂时不能回收该 allocation；否则这个 operation 不可能访问它。

它比 hazard pointer 更粗，但不用每次 dereference publish；比 EBR 更细，因为 stalled operation 通常只挡住与它 key 同一路径的 retired object。代价是每个 retired prefix 要和 `O(thread count)` 个 active key 比较，而且 reclamation efficiency 取决于 workload。高 skew 时，hot prefix 可能一直被某个 active key 覆盖，未回收内存没有上界；论文明确说 hazard keys 不具备 hazard pointer 的 robustness。未来可以在 traversal 后把 key 收窄成 subtree/value protection，或和 epoch 混合，但当前实现未做（图 6）。

### 工程优化

- optimistic traversal：常见 path 不保存 parent stack，只有遇到 frozen CAS failure 才重启并记录。
- native integer：按 key 类型选择 endian，把 8-byte integer 直接做 XOR + leading/trailing-zero count，避免 `memcpy/memcmp`。
- SIMD/SWAR：bitonic sort `Node15` header，向量扫描 `Node47`，用 register 内 SIMD 查 `Node3`（§3.10）。

## 设计取舍

- **128-bit metadata 换较少 indirection**：edge expansion 和常见 update 很紧凑；缺少廉价 16-byte atomic load/CAS 的平台难以复用性能结果。
- **in-place update 换复杂 freezing proof**：减少 allocator/cache pressure；每个 writer、SMO 和 reclamation path 都必须遵守 frozen invariant。
- **帮助完成换阻塞等待**：满足 lock freedom；多个 thread 同时 freeze/copy 大 node 时可能做重复工作。
- **wait-free scan 换 snapshot 语义**：scan 总能结束并保持有序、不重复；不能代表任何一个瞬间的完整 map。
- **hazard key 一次 publish 换分布依赖**：低 skew/oversubscription 时回收好；高 skew 可无限积累 retired memory。
- **adaptive node 换 deletion policy**：小 node 节省空间；大 node 的同步扫描和压缩可能很贵，推迟清理又会增加 memory。
- **prefix compression 换 key 约束**：短 integer key 高效；长 string 增加 traversal depth，prefix-of-another key 必须先编码 sentinel。

## 实验与结果

- **setup 与 baseline**：单台 Chameleon server 有 2 个 Intel Xeon Platinum 8380，每个 40 cores、2.30 GHz、120 MiB LLC、128 GiB DDR4-3200；Ubuntu 22.04.5、Linux 5.15。作者关闭 hyper-threading/turbo，固定 performance governor 并 pin thread；80 个 physical core 后继续测到 160 thread，观察 oversubscription。baseline 包括 ROWEX ART、无 range scan 的 DashMap、部分 SMO 仍加锁的 FB+-tree，以及 Wormhole；所有 workload 的 memory/core 在两个 [[NUMA]] node 上均匀 interleave（§4、表 1）。
- **YCSB 主结果与反例**：六种 workload、七种 key distribution、每组 100 M operation，request 使用 Zipf 0.99、value 为 8-byte。80 threads 时，相对 ART 的七分布 geometric mean 从 YCSB-C 的 1.3 倍到 YCSB-A 的 7.7 倍；YCSB-A 优势来自 update 通常只 CAS final edge。ARCTIC 在 integer key 上通常最好，但少数 case 输给 DashMap；string read 会随 key length 和 tree depth 变慢，YCSB-E scan 也不是所有分布都领先。超过 80 threads 后 ARCTIC 基本保持 throughput，一些 lock-based baseline 明显下降，不过 FB+-tree 因 SMO 少且 spinlock 有 backoff 也较稳定（§4.1、图 7）。
- **端到端 database integration**：RocksDB bulk load 插入 100 M 个随机 20-byte key、400-byte value，并关闭 WAL；用 ARCTIC 替换默认 lock-free skiplist 后，1/2/4/8 threads 的 throughput 分别是原版 1.36/1.40/1.13/1.05 倍。Turso multi-writer benchmark transactionally 插入 100 K 个 batch、每 batch 100 rows；替换两个 MVCC skiplist 后，同样四个 thread count 是 1.08/1.10/1.08/1.12 倍。最高 40%/12% 的说法成立，但只来自 write-heavy benchmark，且 thread scale 只到 8（§4.2、表 3、图 8）。
- **hazard keys 只在低 skew 占优**：rand-u64、8-byte allocated value 的 YCSB-A/B 中，Zipf 0.99、100 threads 时，hazard keys 的 peak unreclaimed garbage 比 crossbeam-epoch/seize 低 5.6–19 倍；throughput 相对 crossbeam-epoch 在 A 为 +1.3%，B 为 -12%。但 Zipf 提高到 1.1/1.2 后，hazard-key garbage 急增并可明显差于 baseline。在较理想的 Zipf 0.99、80 threads 下，它相对 crossbeam-epoch 的 A/B throughput 仍低 7.2%/6.3%，不是“免费回收”（§4.3、图 9）。
- **ablation 解释收益来自哪里**：80 threads 时，baseline 在 sequential/random u64 insert 为 250/110 Mops/s，read 为 450/250 Mops/s，scan 为 79/27 Mops/s。只加 optimistic path，insert 提高约 1.32/1.16 倍，read/scan 几乎不变；再加 native integer，累计达到 insert 1.40/1.34 倍、read 1.27/1.17 倍；SIMD 后 random read 累计 1.34 倍。所有 scan 优化均至多 1.05 倍，因为瓶颈主要是 memory bandwidth（§4.4、图 10）。
- **memory 与冲突边界**：论文汇总 ARCTIC 相对 ART 的 memory ratio：integer key 为 0.97–1.5，string key 为 0.19–0.61；图 7 还分别报告每种 index 相对 raw key/value baseline 的 peak usage。最高 SMO 压力的 100 M random-u64 insert 中，80 threads 只有 324 次 CAS 因 frozen node 失败，说明普通随机 workload 很少走昂贵 helping path；它不能代表恶意 prefix churn 或反复 grow/shrink 的上界（§1、§3.5、图 7）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| ARCTIC 的 point operation 具有无锁/等待自由进展 | traversal wait-free；update 遇到 frozen node 会帮助 deterministic replacement；Claim 1–7 给出 proof sketch | 证明不是机械验证；依赖所有 128-bit atomic/frozen invariant 正确实现 | 中到强 |
| 无锁 ART 可以比 lock-based ART 更快 | 80-thread YCSB 对 ART geometric mean 为 1.3–7.7 倍，并在 oversubscription 下稳定（图 7） | 一台双 socket x86；长 string/scan 不是总赢，未报告 tail latency | 强 |
| layout 优化能改善真实系统 | RocksDB/Turso write-heavy benchmark 最多 1.40/1.12 倍（表 3） | RocksDB 关闭 WAL；只测 bulk/multi-writer insert 与 1–8 threads | 强 |
| hazard keys 在低 skew、stalled thread 下比 EBR 更精确 | Zipf 0.99、100 threads 的 garbage 低 5.6–19 倍（图 9） | 高 skew 时反转；无有界回收保证，每次 reclaim 要比较所有 thread key | 强 |
| range scan 同时满足高性能索引的实际需求 | wait-free、有序、不重复，并覆盖持续存在的 key（§3.7） | 非 linearizable；没有 snapshot benchmark 或 scan/update correctness history | 弱到中 |

## 批判性分析

### 论证链条

论文从 ART 的双位置 SMO 出发，先用 layout 把 edge transition 压进 128 bits，再用 freezing 解决“copy replacement 时并发 update 丢失”，最后用 helping 得到 lock freedom。设计、invariant、proof sketch、YCSB 和 ablation 能互相对上：性能主要来自更细粒度 update 和 integer path，不只是“无锁”标签。hazard keys 也明确写出高 skew 会失败，没有把 workload-dependent approximation 包装成通用 SMR。

### 假设压力测试

第一项压力是 128-bit atomic portability：CAS 能用不代表 atomic load 同样便宜，ARM、旧 x86 或其他 ISA 的 fallback 可能抹去优势。第二项是 key/data model：prefix key 要改编码，长 string 的 traversal 仍慢。第三项是结构 churn：freeze `Node256` 要触碰最多 256 条 edge，若 workload 反复在 node capacity boundary 附近 insert/delete，多 thread 可能重复 scan/copy/help。论文的 random insert 只有 324 次 frozen failure，正说明评测没有真正压到这个 worst case。第四项是 hazard-key skew；长期 hot prefix 可以让垃圾无界，生产热点恰好不是罕见情况。

### 实验可信度

评测覆盖七种真实/合成 key、六种 YCSB mix、五类 index、1–160 threads、memory、两种 database、三种 SMR 和 optimization ablation，范围很完整，也主动报告 DashMap/string workload 的反例。限制是只有一台双 socket Ice Lake 机器；论文动机提到 tail latency，却几乎只报告 throughput；RocksDB benchmark 关闭 WAL 且只 bulk load，Turso 也只写。range scan 的核心语义没有 linearizability history test，crash/stalled-thread 实验也主要通过 oversubscription 间接模拟。

### 系统性缺陷

“高性能、lock freedom、range scan 三者兼得”在接口层要加限定：得到的是非 linearizable scan，很多数据库仍需 MVCC、write quiescence 或外部 snapshot。hazard keys 是 ARCTIC 最不稳的一部分：回收没有 bounded-memory guarantee，且 request distribution 同时决定性能和内存安全余量。删除后的 node cleanup 也留作多种 policy，没有清楚固定何时压缩大 node；不同选择会改变图 7 的 memory 与 delete latency。最后，复杂的 frozen bits、Node47 两阶段 append、helping、SMR 与 tagged pointer 都进入 trusted core，proof 只是 sketch，部署前仍需要更强的 model checking、sanitizer 和 adversarial stress。

## 局限与后续工作

- 为 scan 增加可选的 snapshot/linearizable 模式，并分别量化 MVCC version、copy-on-write 或 validation 的 throughput、memory 与 tail cost。
- 在 ARM `CASP`、不同 x86 generation 和没有廉价 128-bit atomic load 的平台上实测 fallback，不只根据 ISA 是否有指令判断可移植性。
- 构造反复触发 `Node3↔Node15↔Node47↔Node256` grow/shrink 的 adversarial workload，测 helping amplification、allocator pressure 与 p99/p99.9。
- 将 hazard keys 与 epoch 或 runtime refinement 结合，在 Zipf 1.1/1.2、stalled hot-key thread 下给出明确 memory bound 或 fallback threshold。
- 固定并公开 deletion cleanup policy，分开报告 logical delete、同步 compression 和 background reclamation 的代价。
- 对 atomic protocol 做 model checking，并用 loom、sanitizer、forced preemption 和 address reuse stress 覆盖 frozen/unlink/reclaim 交错。
- 在 RocksDB 常规 WAL、mixed read/write/compaction 和 Turso real transaction workload 中验证端到端收益与 scan semantics。

## 相关

- **相关系统**：[[RocksDB]]
- **相关概念**：[[NUMA]]
- **同会议**：[[OSDI-2026]]
