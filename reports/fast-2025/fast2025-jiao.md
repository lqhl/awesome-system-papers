# Silhouette: Leveraging Consistency Mechanisms to Detect Bugs in Persistent Memory-Based File Systems

**作者**：Bing Jiao (Florida State University), Ashvin Goel (University of Toronto), An-I Andy Wang (Florida State University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/jiao
**源文件**：[[fast2025-jiao.pdf]]

---

## 一、背景

Persistent Memory (PM) 是一种非易失性、字节可寻址的存储介质，延迟低于传统存储设备，容量密度高于 DRAM，因此被广泛用于构建高性能文件系统（如 PMFS、NOVA-fortis、WineFS）。然而，PM 编程极其复杂：store 操作不会立即从 CPU cache 刷入 PM，编译器和处理器可能重排指令顺序，这使得 PM 程序在崩溃时极易出现数据丢失和不一致问题。开发者需要显式使用 flush 和 fence 指令来控制持久化顺序，这带来了大量微妙的 crash consistency bug。

现有的 PM bug 检测工具（如 Yat、Vinter、Chipmunk）通过重排 in-flight store 并生成 crash image 来检测 bug，但对于大型 PM 文件系统而言，in-flight store 数量庞大（ordering point 处可达 40+），导致搜索空间呈指数爆炸（2^n crash image），穷举测试不可行。

---

## 二、要解决的问题

1. **搜索空间爆炸**：PM 文件系统在 ordering point 处有大量 in-flight store，现有工具生成的 crash plan 达百万级（Vinter 约 193 万，Chipmunk 约 339 万），穷举不可行。
2. **现有工具缺乏语义理解**：Vinter 和 Chipmunk 将所有 in-flight store 视为等价对待，不区分受 consistency mechanism 保护的 store 与不受保护的 store，导致大量无效探索。
3. **检测能力有限**：Vinter 只关注 recovery 时读取的 store，可能遗漏某些 bug（如缺少 fence 但下一个 fence 恰好产生 consistent state 的情况）；Chipmunk 只 instrument flush/fence 函数而非 store 指令，可能遗漏 temporal store 相关 bug。
4. **Logic bug 检测不足**：现有工具主要检查 PM ordering bug，对 crash 相关的程序逻辑 bug（不能通过添加 flush/fence 修复的 bug）检测能力有限。

---

## 三、洞察与设计

**关键洞察**：所有已知的 PM 文件系统都使用一组标准的 crash consistency mechanism（journaling、log-structured write、replication），这些机制有明确的 persistence invariant。如果文件系统正确实现了这些机制，那么与机制关联的 store 就是"受保护的"，只需对少量"不受保护的"store 进行重排探索。

基于此洞察，Silhouette 的核心设计分为三个阶段：

1. **Instrumentation & Tracing**：使用 LLVM 对文件系统代码进行静态插桩，在运行测试用例时生成执行 trace，记录每条 PM 相关指令（store、flush、fence 等）的时间戳、地址、数据类型等信息。通过 GEP（getelementptr）指令将内存地址映射到具体的数据结构字段。

2. **Invariant Checking**：
   - 为 journaling、log-structured write、replication 三种机制定义 ordering/location/data invariant
   - 使用轻量级 annotation（开发者仅需指定数据结构名和字段，如 journal 的 head/tail pointer）
   - 对 trace 中的 store 进行分类：通过数据类型匹配将 store 关联到 consistency mechanism 的不同 phase，标记为 protected；剩余 store 标记为 unprotected
   - 检查各 phase 的 in-flight period 是否按序且不重叠

3. **File System Validation**：
   - 对 crash-consistency mechanism 生成针对性 crash plan（如 journaling 在 Phase 4 之前崩溃）
   - 对 unprotected store 使用 **2CP (Two Crash Plans)** 启发式策略：对每个 unprotected store 仅生成 2 个 crash plan（只持久化该 store / 持久化除该 store 外的所有 store），将搜索空间从 2^n 降至 2n
   - 通过 syslog test、stat test、write test、unprotected store test、file operation test 五种检查方法检测 bug

---

## 四、实现细节

- **架构**：Client-Server 架构。每个 Client 是一个 QEMU VM，运行测试用例、检查 invariant、生成 crash plan 并执行 recovery。Server 在 host 上管理 VM 的状态监控和恢复。
- **LLVM 插桩**：两遍扫描——第一遍识别顶层 VFS 操作并为指令分配唯一 ID；第二遍插桩 PM 相关指令（store、nt_store、cas、xchg、memset、memcpy、flush、fence）。
- **数据类型识别**：维护一个 interval tree，key 为地址范围，value 为 (structure type, field, timestamp) 元组。通过 GEP 记录更新，查询时使用最近的时间戳匹配。
- **Annotation**：以配置文件形式提供，不修改文件系统源码。例如 PMFS journal 需指定 head/tail pointer、buffer addr/size、dest addr/size、是否 pre-allocate 等（共约 7 个字段）。从 NOVA 迁移到 PMFS 的 annotation 编写仅需约 30 分钟。
- **重复操作检测**：通过指令 ID 的 hash 值识别重复的操作序列，避免重复探索。50K 测试用例中 391,743 个操作仅需探索 356（NOVA）/285（PMFS）/81（WineFS）个唯一操作。
- **Cache/NVM 模拟器**：基于 Witcher 的模拟器，模拟 x86-64 的 store/flush/fence 语义，跟踪每个 store 的 update time、flush time、persist time。
- **开源地址**：https://github.com/iaoing/Silhouette

---

## 五、实验结果

**测试平台**：Dell 7820 (Intel Xeon Silver 4215R, 144GB DRAM + 128GB Intel Optane PM)，QEMU VM (1 core, 8GB DRAM, 128MB emulated PM)，Ubuntu 20.04，Linux v5.1 kernel。

**测试文件系统**：PMFS、NOVA-fortis、WineFS

**Workload**：ACE workload generator，11 种 VFS 操作 + 自定义 workload

### Bug 发现

| 指标 | 数据 |
|------|------|
| 发现所有 Vinter 报告的 bug | 7 个 |
| 发现所有 Chipmunk 报告的 bug | 20 个 |
| 新发现 bug | 15 个（1 PM bug, 12 logic bug, 2 performance bug） |
| 已确认并修复 | 3 个 |

### Bug 发现速度（NOVA, ACE Seq3 workload, 6 小时内）

| 工具 | 测试用例数 | 发现 bug 数 | 找到所有 bug 的时间 |
|------|-----------|------------|-------------------|
| Vinter | 36 | 4 | 156 min |
| Chipmunk | 2.6K | 6 | 164 min |
| Silhouette | 5.3K | 10（含 4 个新 bug） | **17 min** |

### Crash Plan 数量（ACE Seq3 workload）

| 工具 | NOVA | PMFS | WineFS |
|------|------|------|--------|
| Vinter | 1,928,524 | 2,375,295 | 3,312,029 |
| Chipmunk | 3,392,143 | 1,640,534 | 995,865 |
| Vinter (unique) | 27,931 | 26,645 | 7,860 |
| Chipmunk (unique) | 61,218 | 15,386 | 2,179 |
| **Silhouette** | **14,416** | **2,427** | **1,079** |

Silhouette 相比 Vinter/Chipmunk 减少 100x–3000x crash plan，相比 unique 版本减少 1.9x–7.3x。

---

## 六、批判性分析

1. **2CP 启发式的完备性声明过强**：论文声称 2CP 能检测所有 Vinter 和 Chipmunk 发现的 bug，但这只是在三个特定文件系统上的经验观察，而非理论保证。论文也承认 2CP 无法处理 (A, B)→(C, D) 类型的 persistence ordering，但将此轻描淡写为"只观察到一个 real-world case"。随着文件系统设计复杂度增加，这类模式可能更常见。

2. **Annotation "轻量级"的说法值得商榷**：虽然从 NOVA 迁移到 PMFS 只需 30 分钟，但这建立在两者使用相同 consistency mechanism 的前提上。对于使用新型 consistency mechanism 的文件系统，需要 Silhouette 开发者定义新的 phase 和 invariant，这个成本被淡化了。

3. **评估文件系统数量有限且版本较旧**：只测试了 3 个文件系统（PMFS、NOVA-fortis、WineFS），且使用 Linux v5.1 kernel（2019 年版本）。未测试更新的 PM 文件系统如 SplitFS、MadFS、SquirrelFS 等。

4. **False positive 问题被简化处理**：论文提到 unprotected store test 可能产生 false positive，并称"manual verification is needed"且"not much effort is needed"，但未给出 false positive 率的定量数据。

5. **不支持并发 workload**：这是 PM 文件系统实际运行中的常见场景。Bug 13 虽然是并发 bug，但 Silhouette 发现它只是因为恰好没有 replay 异步写入，而非真正具备并发 bug 检测能力。

6. **CXL 时代的适用性存疑**：论文在 Discussion 中提到 Silhouette 的方法可应用于 CXL 存储级内存，但 CXL 的 cache coherence 和 failure domain 模型与 PM 有本质区别，这个迁移的可行性未经验证。

---

## 七、总结

Silhouette 通过利用 PM 文件系统普遍采用的标准 crash consistency mechanism（journaling、log-structured write、replication）的语义知识，将 in-flight store 分为 protected 和 unprotected 两类，结合 invariant checking 和 2CP 启发式策略，将 crash plan 搜索空间减少 2–3 个数量级，在 17 分钟内找到现有工具需要 2.5 小时才能找到的所有 bug，并额外发现 15 个新 bug。该方法适用于使用标准 consistency mechanism 的 PM 文件系统，主要局限在于不支持并发 workload、依赖手动 annotation、2CP 启发式缺乏理论完备性保证。
