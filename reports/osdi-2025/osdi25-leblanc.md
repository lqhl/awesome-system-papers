# PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection

**作者**：Hayley LeBlanc（University of Texas at Austin）、Jacob R. Lorch、Chris Hawblitzel（Microsoft Research）、Cheng Huang、Yiheng Tao（Microsoft）、Nickolai Zeldovich（MIT CSAIL and Microsoft Research）、Vijay Chidambaram（University of Texas at Austin）
**会议**：OSDI 2025，July 7–9, 2025, Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/leblanc
**源文件**：[osdi25-leblanc.pdf](../../papers/osdi-2025/osdi25-leblanc.pdf)

---

## 一、背景

存储系统必须在断电和介质错误等极端条件下保持数据完整性，这是一个长期存在的难题。形式化验证（formal verification）是确保存储系统鲁棒性的有力手段，但当前的验证框架要么依赖 Crash Hoare Logic（CHL）等需要对验证工具进行大幅改造的专用机制，要么依赖 TLA 风格的状态机精化（state machine refinement），均超出了大多数主流验证器的原生能力范围。

持久内存（Persistent Memory，PM）的出现进一步加大了挑战：PM 以字节为粒度提供接近 DRAM 的延迟，但其细粒度的原子写入大小（8 字节对齐）使得同时原子地更新数据和其 CRC 校验码在技术上几乎不可能实现。已有研究证明，PM 存储系统极易出现微妙的崩溃一致性 bug，Azure Storage 等云服务已在生产环境中使用 PM，行业对可验证 PM 存储系统有真实需求。

---

## 二、要解决的问题

**问题 1：现有崩溃一致性验证方法不具备工具无关性**

- Crash Hoare Logic（CHL）仅被 Rocq（Coq）生态支持，而 Rocq 程序须先提取为 Haskell/OCaml 才能运行，性能有限，且 Verus、Dafny 等高性能系统验证器支持 CHL 需要对核心语言进行大规模改造。
- VeriBetrKV 等系统采用 IronFleet 风格的状态机精化，需要在 TLA 风格的推理库之上构建大量额外基础设施，开发成本高昂。
- push-button 验证（如 Yggdrasil、TPot）虽然大幅减少了证明负担，但表达能力受限，不适合复杂存储系统。

**问题 2：已验证存储系统无法达到最先进的性能**

- 现有验证工具与高性能 PM 存储系统之间存在严重的性能鸿沟，阻碍了形式化验证的主流采用。

**问题 3：PM 上的 CRC 管理存在崩溃安全问题**

- PM 的写入原子粒度（8 字节）使得无法原子地同时更新数据及其 CRC，已有研究（Chipmunk）发现 NOVA-Fortis 的 Tick-Tock 算法在任何合理的腐蚀模型下都不正确。
- VeriBetrKV 的腐蚀模型假设 checksum 与数据必须存储在同一块中且原子更新，这与很多实际系统（尤其是 PM 系统）不相符。

---

## 三、核心设计

### PoWER（Preconditions on Writes Enforcing Recoverability）

PoWER 的核心洞察是：**验证崩溃一致性不需要新形式的逻辑，只需在写操作的前置条件（precondition）上加一个约束——所有可能产生的崩溃状态必须是"被允许的"。** 这个约束完全可以用 Hoare 逻辑和量词表达，几乎所有主流验证工具都支持。

具体地，PoWER 为存储 API 的 `write` 方法增加一个前置条件（precondition）：调用者必须提供一个"权限令牌"（permission token），证明本次写操作可能引入的所有崩溃状态都是合法的。这一设计：
- 将崩溃一致性的证明责任转移到写操作的调用点，而非方法体内部；
- 不引入任何运行时开销（所有注解在编译时被擦除）；
- 与工具无关：只依赖 Hoare 逻辑、ghost 变量和量词，无需专用语言特性。

### 基于预言的存储模型（Prophecy-based Storage Model）

PoWER 采用一种简化的预言（prophecy）存储模型，将存储状态表示为两个字节序列：
- `read_state`：反映所有已执行的写（包括尚未持久化的）；
- `durable_state`：反映最终会持久化的预言状态（非确定性选择部分子写的结果）。

相比自然模型（需要显式追踪所有未完成写的可能子集），预言模型大幅简化了证明：写操作之后，开发者只需对唯一的预言持久状态进行推理，而不需要枚举所有可能的崩溃分支。

### 四类写策略

PoWER 将持久化更新分为四类，并为每类提供库函数和证明策略：
1. **Tentative writes**：逻辑上无效的写（修改未被引用的地址），崩溃不影响抽象状态；
2. **Committing writes**：使之前的 tentative 写生效的写，通常通过更新元数据完成；
3. **Recovery writes**：仅在崩溃恢复路径中执行，保证恢复后状态正确；
4. **In-place writes**：直接修改已有数据，需要更复杂的证明。

### 腐蚀模型与 Corruption-Detecting Boolean（CDB）

论文提出了一个新的介质腐蚀模型：设备具有一个腐蚀 bitmask，bitmask 中 1 的数量（Hamming 距离）被一个常数 $c$ 限界。代码可访问一个可信的 CRC-64 库，并依赖"任意两个 Hamming 距离在 $[1, c]$ 之间的字节序列具有不同 CRC"这一公理。

为了在 PM 上实现 CRC 的崩溃安全更新，论文提出 **CDB（Corruption-Detecting Boolean）**：一个 8 字节整数，只能取两个精心选择的值（CRC(0) 和 CRC(1)），8 字节写入可对 PM 原子执行。通过 CDB 实现的 atomic 更新算法维护数据结构的两个版本，CDB 指示哪个版本在恢复时有效，且可检测腐蚀。

---

## 四、实现细节

### CAPYBARAKV（Verus 实现）

- **数据结构**：主表（key + 两个地址 CRC + CDB 有效位）、item 表（item + CRC）、list-element 表（元素 + 下一元素地址 + CRC）、physical redo journal；
- **Journal**：提交时先追加单个 CRC，再用 committing write 更新 CDB，恢复时 replay；
- **Copy-on-write**：更新 item 或 list element 时分配新行，通过 journal 更新指针；
- **并发扩展**：两种变体——读写锁版（允许并发读）和 sharding 版（允许并发写），共享 `UntrustedKvStoreImpl` 组件；
- **pmcopy crate**：受信任的 Rust crate，利用 `#[repr(C)]` 和 `#[derive(PmCopy)]` 宏生成 Verus ghost 代码，通过 Rust 编译器检验类型布局安全性（如防止存储含引用的结构体），并静态断言与编译器生成布局一致；
- **规模**：trusted 5244 行、spec/proof 14255 行、impl 5531 行；proof-to-code 比约 2.6；
- **验证时间**：Intel Core i7-11850H、1 线程 54 秒，8 线程 23 秒。

### CAPYBARANS（Dafny 实现）

- 持久化公证服务，维护逻辑时间戳和 last hash；
- 使用 CDB 算法原子更新存储状态；
- 有可信的 C# wrapper 提供 CRC、加密和序列化的外部方法；
- 总计 trusted 414 行、spec/proof 673 行、impl 278 行；验证时间 12 秒（Dafny 不支持多线程验证）。

### 健全性证明

- 在 Rocq 中机械验证了 PoWER 与 CHL（Crash Hoare Logic）的对应关系（元逻辑证明，依赖受信任翻译）；
- 在 Verus 中完全机械验证了 PoWER 与 Perennial crash invariants 的对应关系。

---

## 五、实验结果

**实验平台**：2 socket，32 物理核，128GB 内存，128GB Intel Optane DC PMM，Debian Trixie，Linux 6.12.10。

**基线**：pmem-Redis、pmem-RocksDB、Viper（均为未经验证的 PM KV store）。

### 微基准测试（25M 条记录，64B key，1KiB value）

| 操作 | pmem-Redis | pmem-RocksDB | Viper | CAPYBARAKV |
|------|-----------|--------------|-------|-----------|
| 顺序 put | 最慢（通信开销） | 中等 | 较快 | 与 Viper 相当或更快 |
| 随机 get | 最慢 | 中等 | 快 | 与 Viper 相当 |
| 整体延迟 | 最高 | 中等 | 低 | 最低或相当 |

CAPYBARAKV 的随机 get 延迟约为顺序 get 的 2 倍（Optane PM 顺序访问性能更好）。在 Azure 的 battery-backed DRAM 环境中，操作延迟提升最多 2 倍。

### YCSB 吞吐量（相对于 pmem-Redis，单线程）

CAPYBARAKV 显著超越 pmem-Redis 和 pmem-RocksDB，与 Viper 性能相近（两者架构类似：均使用内存 hashmap 索引和简单持久数据结构）。

### YCSB 吞吐量（16 线程，sharded）

| 系统 | 相对 pmem-Redis 吞吐量 |
|------|----------------------|
| pmem-Redis | 1× |
| pmem-RocksDB | ~10-19× |
| Viper | ~50-113× |
| CAPYBARAKV | ~50-113×（部分场景超越 Viper） |

16 线程场景下 CAPYBARAKV 超越 Viper，主要因为 Viper 的 CCEH in-memory hashmap 使用 per-bucket semaphore，线程数增加时竞争急剧恶化（线程数从 1 到 16 时开销近乎翻倍），而 CAPYBARAKV 使用 Rust 标准库 RwLock 无此问题。

### 启动时间与资源占用

| 系统 | 启动（空） | 启动（满） | 内存 | 存储 |
|------|-----------|-----------|------|------|
| pmem-Redis | 142 ms | 失败（OOM） | 12.3 GiB | 22 GiB |
| pmem-RocksDB | 9 ms | 7 ms | 2.0 GiB | 17 GiB |
| Viper | 9 s | 75 s | 1.1 GiB | 23 GiB |
| CAPYBARAKV | 7 s | 53 s | 2.8 GiB | 18 GiB |

CAPYBARAKV 因需重建内存索引（所有 key 保留在 DRAM）而启动较慢，但存储占用与 pmem-RocksDB 相当。

---

## 六、批判性分析

**1. 性能基线不公平，对 Viper 的"超越"存疑**

论文单线程场景中 CAPYBARAKV 与 Viper 性能相近，16 线程场景略有优势。但论文明确指出测试机只有一个非交错的 NVDIMM，而 Viper 的并发优化（CCEH）原本针对多 NVDIMM 交错配置设计。在非最优 Viper 配置下取得"胜利"，说服力有限。

**2. CAPYBARAKV 功能限制被轻描淡写**

论文在 §5.1.3 中提及 CAPYBARAKV 的几个重要限制：必须在初始化时静态分配最大容量、不支持动态扩容、key 全部保留在 DRAM（内存占用随 key 数量线性增长）。这些限制在工业场景中相当重要，但论文将其定性为"简化设计决策"，未充分讨论其对实际部署的影响。

**3. 精化证明的信任根（trusted base）不透明**

CHL 对应关系依赖"受信任的 PoWER 语义 Rocq 翻译"，论文称"翻译相当自然"，但没有量化翻译的规模或提供额外的自动化检验手段。这使得该部分证明的可信度相对较低。

**4. CDB 算法的正确性边界**

CDB 依赖 CRC-64 对任意长度数据检测任意单比特错误（$c = 1$），但对较短数据 $c$ 可取更大值（如 1 GiB 以下 $c = 3$）。论文提及"当前实现未利用更短数据对应的更大 $c$ 值"，未来若存储内容较短但需要更强保护时，此处存在未充分利用的保护能力。

**5. 并发支持存在根本性限制**

PoWER 明确不支持同一存储区域上的并发读写（需要调用者在发起读/写时逻辑上已知该区域当前状态）。论文将 sharding 和 reader-writer lock 作为"两种并发形式"，但这些本质上是粗粒度并发控制，对于需要细粒度并发写的场景（如 B+ 树），PoWER 的适用性尚未得到验证。

**6. YCSB 工作负载修改未充分说明影响**

由于 CAPYBARAKV 和 Viper 不支持 partial value update，论文将 RunA 和 RunB 修改为总是更新完整值，但没有分析这对工作负载特征（尤其是 I/O 放大）的影响，可能使测试结果偏向支持 CAPYBARAKV。

---

## 七、总结

PoWER 提出了一种使用标准 Hoare 逻辑前置条件验证存储系统崩溃一致性的工具无关方法，辅以基于 CRC 理论的腐蚀模型和 Corruption-Detecting Boolean 原语，用于解决 PM 上 CRC 崩溃安全更新的难题。论文通过 CAPYBARAKV（Verus）和 CAPYBARANS（Dafny）两个经形式验证的 PM 存储系统证明了方法的有效性，并通过机械化证明建立了与 CHL 和 Perennial crash invariants 的对应关系。CAPYBARAKV 在 Intel Optane PM 上实现了与主流未验证 PM KV store 相当甚至更优的性能。主要局限在于：不支持细粒度并发写、CAPYBARAKV 功能较为受限（静态容量、全 key 内存索引），以及 CHL 对应关系依赖受信任的手工翻译。对于致力于存储系统可靠性的研究者，PoWER 提供了一条实用的验证路径；对于 PM 应用的工程团队，CDB 是一个值得借鉴的新原语。
