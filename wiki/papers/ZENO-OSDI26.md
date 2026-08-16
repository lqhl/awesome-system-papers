---
type: paper
name: ZENO
full_title: "Accelerating Confidential Databases with Crypto-free Mappings"
authors: [Wenxuan Huang, Zhanbo Wang, Mingyu Li]
venue: OSDI
year: 2026
tags: [confidential-computing, databases, tee, encryption, transactions]
source_pdf: "[[osdi26-huang-wenxuan.pdf]]"
source_md: "[[osdi26-huang-wenxuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用免逐值加密的映射加速机密数据库（OSDI 2026）

> **原题**：Accelerating Confidential Databases with Crypto-free Mappings

> **一句话总结**：ZENO 不再让数据库为每个敏感中间值反复做“解密—计算—加密”，而是让不可信 DBMS 只保存与明文无关的 64 位 FID，并在隐私 TEE 内用数组直接找到明文；它仍会加密落盘的映射块，在两种 TEE 上把 TPC-H 相对 HEDB 的平均速度提高 4.4 倍和 5.3 倍，同时显著减少密文膨胀。

## 问题与动机

现代机密数据库（confidential database）常采用分区架构：普通 DBMS 放在“完整性区”，查询计划、索引和维护接口仍对 DBA 可见；只有处理敏感值的表达式进入“隐私区”TEE。这样比把整个 DBMS 都塞进 TEE 更容易维护，也能隔离 HEDB 所讨论的恶意表达式，但每次计算都要跨区调用并操作密文。

以 `SUM` 为例，聚合 `N` 行需要 `2N−2` 次解密和 `N−1` 次加密。论文测试的 ARM 平台上，一次 AES-GCM 解密约 1,500 cycles，加密约 5,000 cycles。12 字节 nonce 加 16 字节 tag 还会把一个 4 字节整数扩成 32 字节。对三个工作负载的 HEDB profiling 显示，密码操作占总延迟 10.5%–62.6%，密文膨胀和额外 I/O 占 13.9%–25.5%，存储空间是明文数据库的 1.4–3.1 倍。

ZENO 的关键问题不是“怎样把 AES 再做快一点”，而是“DBMS 真的需要拿着 ciphertext 吗”。在这个分区架构里，DBMS 并不读取敏感内容；ciphertext 实际上同时充当了保护载体和 opaque pointer。ZENO 把两个职责拆开：查询执行期间只传一个无内容含义的 ID，真正的明文留在隐私区；只有映射块离开可信内存时才加密。

## 关键观察 / 隐含假设

- **观察 1：不可信 DBMS 只需要引用敏感值，不需要持有该值的逐字段密文。** 64 位 field identifier（FID）可以直接编码分区和数组偏移，把每字段 28 字节的 AES-GCM 元数据缩到 8 字节，减少 71.4%（§4.1）。
  - **隐含假设**：论文威胁模型允许泄露表结构、敏感字段位置、访问模式、查询时间、结果规模和分配顺序等信息。
- **观察 2：数组寻址比“密文缓存+哈希表”便宜。** HEDB 即使缓存解密结果，仍要哈希 ciphertext 并处理较大 key；实测哈希 get/put 为 334.9/2,649.4 cycles，ZENO 的数组 Get/Put 为 113.8/316 cycles（§7.2）。
  - **隐含假设**：映射工作集有足够的空间局部性，或者分区预取能在查询需要之前把相应块放入可信内存。
- **观察 3：事务一致性只需要单向的“外部同步”。** 只要 DBMS 能看到的每个 FID 都有一份当前有效映射，多出来但无人引用的 orphan mapping 不会让查询读错（§5）。
  - **隐含假设**：旧引用被数据库 [[Garbage-Collection|GC]]/VACUUM 清除前，FID 绝不复用；mapping WAL 与数据库 commit record 的顺序始终正确。
- **观察 4：FID 不等于确定性加密。** 同一个明文可以分配不同 FID，所以 FID 本身并不会直接揭示“两个明文相等”。真正新增或保留的信号是引用复用、搜索重叠、访问和更新时间、分区位置及单调分配顺序；这些都被论文明确放在允许泄露的范围内（§6）。

## 核心方法

### 1. 用 FID 把 DBMS 与明文映射解耦

完整性区运行普通 PostgreSQL，敏感字段在 tuple 中被替换为 8 字节 FID。默认 FID 用 16 位表示 partition、48 位表示 partition 内偏移，位数可以配置。隐私区维护紧凑 mapping store：固定长度类型直接放进连续数组；变长类型用 offset array 指向按大小分类的存储区。因而 Get/Put 主要是数组索引和复制，而不是哈希、逐值解密或逐值加密。

查询产生的临时值进入 temporary partition，查询结束即可整批回收；需要长期保存的结果会复制到 permanent partition 并获得新 FID。删除永久值则依赖 DBMS 已有的 GC/VACUUM 流程，只有确定旧引用消失后才释放映射。读取和重复使用映射不另加锁，因为并发可见性仍由 DBMS 的事务控制负责；只有分配新槽位需要同步。

### 2. 按数据库布局管理可信内存

mapping partition 与数据库 heap/table 或 InnoDB page 等布局对齐。DBMS 发起磁盘读取时，ZENO 拦截请求，并行预取对应映射分区。需要逐出的映射以块为单位加密并认证，而不是为每个字段生成 nonce 和 tag。这样仍保护静态数据，却把密码操作从每个表达式的关键路径移到块级换入换出路径。

### 3. 让映射更新服从数据库事务

更新采用类似 MVCC 的 out-of-place 方式：新值获得新 FID，旧映射一直保留到 DBMS 清理旧版本；事务 abort 时，DBMS 仍引用旧 FID，新映射只是不可达垃圾。commit 前，ZENO 把加密后的 mapping WAL record 嵌入 PostgreSQL WAL，并排在事务 commit record 之前。恢复时按同一日志重放；若 mapping 已落盘而事务没有 commit，只会留下 orphan，不会让未提交值可见。

### 4. 信任与泄露边界

攻击者可以控制 TEE 之外的基础设施，但数据库完整性区、操作敏感值的隐私区、远程认证和二者的安全通道都受信任。磁盘完整性由 `dm-integrity` 提供，隐私存储用 `dm-crypt`、HMAC-SHA256 和计数器抵抗篡改与旧版本回滚。论文明确不处理 TEE side channel、TEE 或数据库自身漏洞、物理攻击和拒绝服务。

FID 方案也不隐藏数据库布局、I/O 和搜索访问模式、查询时间、结果量、比较结果、被更新的块与数据类型、分配先后和 partition 位置。因此“与 HEDB 有可比语义安全性”的结论只对论文定义的 FID 值与威胁模型成立，不等于 oblivious database。

## 设计取舍

- **把逐值密码操作移出热路径**：查询明显变快，但 mapping store 变成新的可信状态；当工作集大于 TEE 内存时，块加密、换入换出和预取又会成为成本。
- **用 8 字节 FID 换更小数据**：它不直接编码明文相等性，却暴露论文允许的引用、访问、分区与分配信号。若应用需要隐藏这些模式，ZENO 不满足要求。
- **用单向同步换简单恢复**：允许 orphan 可以避免分布式式的双向原子提交，但必须长期正确协调 FID 复用、VACUUM、全局扫描和日志清理。
- **保留 commodity DBMS 换跨区协议**：DBA 仍可看 plan、索引和非敏感元数据，但系统要维护共享内存 RPC、两套保护域和专用 WAL 扩展。
- **平台差异**：ARM 用 S-EL2 的两个 VM；Intel TDX 没有安全的跨 CVM 共享内存，原型改用 TD Partitioning，让隐私区处于 L1、DBMS 位于 L2。这是实验性部署边界，不能直接等同于常见 TDX VM 配置。

## 实验与结果

- **平台与实现**：原型在 PostgreSQL 15.5 上新增约 6.1K 行 C/C++，用共享内存轮询减少 context switch。ARM 是 Kunpeng 920、S-EL2、1 TB SSD；x86 是 Xeon Platinum 8581C、TDX、4 TB SSD。ZENO 和 HEDB 总共各用 32 vCPU、64 GB，并为每个系统选择最优的两区资源划分；明文 PostgreSQL 单独使用 32 vCPU、64 GB。
- **TPC-C**：100 warehouses、60 秒预热、300 秒测量。相对明文 PostgreSQL，ZENO 把 HEDB 的吞吐差距缩小 18.1%–49.8%（ARM）和 51.5%–73.8%（x86）（图 5）。这是“gap reduction”，不是说 ZENO 的原始 TPS 提高了同样倍数。
- **TPC-H**：SF=3、总内存 6 GB，每个查询预热一次后运行五次。HEDB 平均比明文慢 10.0 倍和 23.8 倍，ZENO 缩到 2.3 倍和 4.5 倍；ZENO 相对 HEDB 平均快 4.4 倍和 5.3 倍，单个查询最高为 53.1 倍和 94.7 倍（图 6）。最大值是某个查询，不应与几何平均混为一谈。
- **工业查询与空间**：九个匿名真实 schema/query 使用的是每表 100 万行的合成数据，并非生产数据或生产 trace。ZENO 相对 HEDB 平均快 4.6 倍（ARM）和 2.9 倍（x86），最高 6.0 倍和 3.6 倍（图 7）。TPC-C、TPC-H、工业数据的空间分别比 HEDB 少 38.9%、52.8%、42.4%（表 3）。
- **机制拆解**：ARM TPC-H 累积消融从未 batch 的 HEDB 开始：batching 使几何平均时间降 5.8%，512 MB 解密缓存再降 21.8%，O(1) 但仍填充到 28 字节的 FID 再降 25.7%，紧凑 8 字节 FID 再降 53.0%，按布局分区再降 16.6%（图 8）。这说明主要收益同时来自便宜查找和消除数据膨胀。
- **事务、恢复与压力测试**：同步提交下，mapping WAL 让 TPC-C TPS 下降 2.6%，每次 commit 平均多 997 B 加密日志和 18.3 微秒；一次 2.6 GB WAL 崩溃恢复耗时 26.3 秒，其中映射恢复 4.1 秒，占 15.6%。Sysbench 中，Zipf 访问相对 HEDB 快 1.1–5.8 倍，uniform 最多 2.3 倍；只给约数据集 10% 的 1 GB 内存时平均仍为 2.2 倍（§7.2、图 9）。恢复只测了一种加载期 crash，不是完整故障注入矩阵。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| FID mapping 大幅减少分析查询中的密码和数据搬运成本 | 图 6：TPC-H 平均比 HEDB 快 4.4/5.3 倍 | SF=3、单机、总内存 6 GB | 强 |
| 直接寻址和紧凑表示都是主要收益来源 | 图 8：O(1) FID 与 8 字节 FID 分别再降 25.7% 和 53.0% | 累积消融，ARM TPC-H 几何平均 | 强 |
| 事务日志集成的稳态代价较小 | TPC-C TPS 下降 2.6%，commit 多 18.3 微秒 | 一种同步提交配置，未覆盖复制与长时间 GC | 中 |
| 方案在两类 TEE 上都有效 | ARM S-EL2 与 x86 TDX 上的 TPC-C、TPC-H、Sysbench 趋势一致 | TDX 使用 TD Partitioning 原型，不是任意 TEE 部署 | 中 |
| 方法可迁移到工业 schema/query | 九个匿名工业查询平均快 4.6/2.9 倍 | 数据为每表 100 万行的合成数据，无生产 SLO | 中 |

## 批判性分析

### 论证链条

论文最有价值的地方是重新拆分了 ciphertext 的两个角色：保护数据和充当引用。profile 先证明逐值 crypto 与膨胀是主要成本，设计再分别用数组 FID 和 8 字节表示去掉两项，图 8 的消融也支持这个因果解释。ZENO 并没有消灭密码学，而是把密码操作移到可信映射块的存储边界；这一点比“crypto-free”标题更准确。

### 假设压力测试

FID 不会因为两个明文相同就必然相同，因此不能简单说它泄露明文相等性。但同一个逻辑值或版本被重复引用、哪些查询访问相同 FID、何时更新和分配，仍可能帮助攻击者关联行为；论文选择允许这些泄露。若应用要求隐藏访问模式，或者 mapping 工作集远大于可信内存且访问完全随机，安全或性能前提都会失效。FID 永不提前复用也是硬约束，VACUUM、崩溃和长期 orphan 累积必须共同正确。

### 实验可信度

两种硬件隔离机制、OLTP、OLAP、工业 schema、空间、消融、内存、偏斜、commit 和恢复使评测覆盖较宽；HEDB 是直接而有意义的基线。限制也很清楚：TPC-H 只有 SF=3；工业查询使用合成数据；恢复只有一次加载期崩溃；未测复制、PITR、备份、在线 schema change、长时间 orphan 堆积或实际安全推断攻击。资源划分还为每个系统单独调优，公平但不代表固定生产配额。

### 系统性缺陷

mapping store 和它的 WAL 成为新的敏感持久化子系统，并与 PostgreSQL MVCC/VACUUM 紧密耦合。共享内存轮询会占用 CPU core，TD Partitioning 也增加部署门槛。论文说相关技术已集成到 GaussDB，但没有给真实部署规模、故障记录、运维成本或生产 SLO。key rotation、FID 空间耗尽、partition 重排、mapping 损坏和复制节点切换等长期维护问题仍待回答。

## 局限与后续工作

- **局限 1**：明确允许多种访问和布局泄露，不提供 obliviousness，也不覆盖 TEE side channel。
- **局限 2**：评测是单机 PostgreSQL，尚未验证 replication、distributed transaction、backup/PITR 和 schema migration。
- **局限 3**：大规模随机工作集与长期 orphan/GC 行为证据不足，工业查询也没有使用真实生产数据。
- **后续工作 1**：形式化列出 HEDB 与 FID 各自的 leakage function，并用查询轨迹攻击量化能推断出哪些敏感属性。
- **后续工作 2**：在 SF100 以上、mapping 工作集明显超过 TEE 内存时测 P99 查询、预取命中率和后台加密积压。
- **后续工作 3**：加入 streaming replication 与 PITR，在 commit、WAL flush、VACUUM、checkpoint 和 failover 各点做系统化 crash injection。

## 相关

- **相关概念**：[[Confidential-Computing]]、[[Trusted-Execution-Environment]]、[[Encrypted-Database]]、[[MVCC]]
- **相关系统**：[[HEDB]]、[[PostgreSQL]]、[[GaussDB]]
- **同会议**：[[OSDI-2026]]
