---
type: paper
name: OpenCAS-Crash
full_title: "Crash Consistency in Block-Level Caching Systems: An Open CAS Case Study"
authors: [Shaohua Duan, Youmin Chen]
venue: ATC
year: 2025
tags: [crash-consistency, block-cache, persistent-cache, file-system, testing, reliability]
source_pdf: "[[atc2025-duan-shaohua.pdf]]"
source_md: "[[atc2025-duan-shaohua]]"
---

# Crash Consistency in Block-Level Caching Systems: An Open CAS Case Study (ATC 2025)

> **一句话总结**：这篇论文把 Open CAS 当作代表性 block-level persistent cache 做 crash-consistency 解剖，关键发现是 cache-hit update 和 write-around invalidation 缺少足够的 crash boundary，会在 operation-on-the-fly crash 下返回 bad data；同时 ext-3/4 journal、xfs、btrfs 等文件系统恢复逻辑与持久缓存复用不兼容，轻则 slow recovery / I/O error，重则 durability loss。

## 问题与动机

NVM / PMem 让 block-level cache 不再只是易失的 page cache 替代品：缓存层自己也可能在 crash 后保留数据和 metadata。Open CAS 这类系统因此承诺在返回 ACK 后可以从 persistent cache 中恢复数据，给 HDD/SSD backend 文件系统带来性能和 durability 的双重收益。

问题在于，这个新持久层改变了传统文件系统的 crash model。ext 系列 journaling、xfs、btrfs COW 等可靠性机制通常默认缓存层 crash 后消失，唯一 surviving state 是 backend persistent device；Open CAS 的 fast recovery 则会复用 cache device 上的 data / metadata。二者如果没有共同设计，恢复时可能同时看到两个不一致的 persistent truth。

作者要回答两个问题：Open CAS 自身在所有 cache mode、cache operation、crash timing 下是否保持 crash consistency？Open CAS 与不同 backend file system 的 recovery feature 组合后，是否还能形成端到端一致系统？论文的贡献更像 reliability case study 加测试方法，而不是一个新 caching system。

## 关键观察 / 隐含假设

- **观察 1：Open CAS 官方测试覆盖了 ACK 后 crash，却没有覆盖 operation-on-the-fly crash 和 implicit cache operation。** 论文检查 Open CAS 内建 crash-consistency tests 后发现，它们不测试 eviction / cleaning 这类由 policy 隐式触发的操作，也不在 cache operation 正在执行时 crash。
  - **依赖假设**：如果只验证 ACK 后 durability，就会漏掉真实 power fault 可以落在任意 I/O window 的情况。
  - **可能失效场景**：若部署只采用断电保护、严格屏障或关闭 fast recovery，风险面会缩小；但这不是论文评估的默认 Open CAS recovery model。

- **观察 2：cache miss / eviction 比 hot cache-hit update 更耐 crash。** miss / insertion 先把目标 cache line 置为 invalid，再写 data，最后 atomic 更新 metadata；crash 中途留下的坏数据不会被 valid bit 暴露。相反，write cache hit 覆写已经 valid 的 cache line，没有先 invalid，因此 crash 可让 corrupted cache data 被读出或最终 flush 到 backend。
  - **依赖假设**：valid bit 是主要 crash boundary，metadata 的 4 KB atomic write 假设成立。
  - **可能失效场景**：如果设备 atomicity、flush ordering、sector-valid 粒度或 Open CAS metadata layout 与测试平台不同，具体失败窗口可能变化；但「热数据 overwrite 缺少 before-image / log / checksum」这个脆弱点仍成立。

- **观察 3：persistent cache 与 file-system recovery 的粒度不匹配。** Open CAS 以 cache line dirty bit 判断哪些 line 需要 flush；journal / COW 文件系统以 transaction 或 tree root 判断哪些更新可见。二者粒度不同，Open CAS 可能认为某些 line 已 clean，而文件系统会丢弃不完整 transaction，导致数据无法再次 flush。
  - **依赖假设**：backend 文件系统在 recovery 时会执行自己的 journal / COW 检查，而 Open CAS 仍尝试复用 dirty cache data。
  - **可能失效场景**：如果 cache layer 能识别 backend reliability protocol，或 recovery 时强制丢弃 cache，兼容性问题会减少，但 fast recovery / durability benefit 也随之削弱。

- **假设 1：WLOT 可以用吞吐下降作为 implicit operation 正在执行的代理信号。** 作者用 4 GB Optane PMem + 256 GB SATA SSD，比较 cache line size 和 thread count，发现 eviction / cleaning 在 4 KB cache line、16-thread FIO 下造成明显 throughput degradation；再用显式 `casctl cleaning` / `casctl eviction` driver 复核相同模式。
  - **证据强度**：中。实验显示该平台上信号足够强，但它是灰盒 timing heuristic，不是对内部状态的直接观察。

- **假设 2：Open CAS 是 block-level persistent caching systems 的代表。** 论文额外在 NVCache 上复现 cleaning crash 返回 bad data，并推断 OrthusCAS 因集成 Open CAS 而可能共享风险。
  - **证据强度**：中到弱。两个系统足以说明问题类别真实存在，但不足以覆盖所有 persistent cache 设计。

## 核心方法

论文首先把 Open CAS 的 cache mode 和 cache operation 拆开。Open CAS 有 WT、WB、WO、WA、WI、PT 六种 mode；真正改变 data / metadata 的操作包括 mapping、insertion、update、invalidation、flushing、eviction、cleaning。它依赖 atomic metadata update、I/O ordering、flapped sections、valid / dirty bits 维持 crash boundary，但为了性能没有持久化 operation log。

核心测试框架是 WLOT（Workload-Oriented Test）。它分两阶段：trace mode 先生成 workload，并用 `casctl static` 监控 Open CAS 性能下降，把下降窗口当作 eviction / cleaning 等 implicit operation 的 crash point；随后停止 workload 并 flush 出 oracle。test mode 再回放 workload trace、在预设 crash point 用 unmount + `casctl stop` 注入 synthetic crash，重启 Open CAS recovery，并把恢复后的读结果与 oracle 对比。

为了覆盖 caching layer 本身，作者用 4 GB Optane PMem 作为 cache device、256 GB Samsung SATA SSD 作为 backend，RHEL 7.9、Linux 5.4.0-144、Open CAS 22.03.2、ext-4 默认配置，并启用 direct I/O 绕过 [[Page-Cache]]。workload 包括 sequential write、sequential read、repeat write、update-after-read，覆盖 WT/WB/WA/WI/WO 下 cache miss、cache hit、eviction、cleaning、flushing 等 crash point。结果表中的 R 表示 ACK 后可恢复，C 表示保持一致但未持久化最新数据，B 表示返回 bad data。

为了测试端到端兼容性，作者把 crash 扩展到 caching layer 和 backend file system 同时发生，并在 recovery 时同时运行 Open CAS 和文件系统 recovery。backend 包括 ext-2、ext-3、ext-4 的 writeback / ordered / journal / nodelalloc 配置、xfs、btrfs；cache mode 主要选 WB / WO，因为它们会把最新 dirty data 留在 cache、旧数据留在 backend，更容易暴露 recovery coordination 问题。

论文最后用 NVCache 做 sanity check。NVCache 用 log-structured cache line 和 commit flag，比 Open CAS 的 cache-hit update 更稳，但 cleaning 这种 implicit operation crash 仍会返回 bad data，说明 WLOT 的关注点不只是 Open CAS 的单个 bug。

## 设计取舍

- **测试方法 vs 精确性**：WLOT 不修改 kernel module，也不要求 Open CAS 暴露新接口，因此适合真实系统和灰盒测试；代价是 crash point 依赖 throughput degradation，不能证明每一次 crash 都精确落在目标内部状态。
- **持久缓存复用 vs recovery 简单性**：Open CAS fast recovery 复用 cache data / metadata，保留性能和 durability 收益；代价是缓存层必须承担更强的一致性责任，并与 backend file-system recovery protocol 协调。
- **cache-line metadata atomicity vs operation transactionality**：Open CAS 的 valid / dirty bit 和 4 KB metadata atomic write 足以保护 insertion / miss；但 update、cleaning、journal transaction 这类跨 data + metadata + backend 的操作没有完整 transaction。
- **通用 block layer 透明性 vs filesystem awareness**：Open CAS 作为透明 block cache 不需要上层文件系统改动；但正因为看不到 journaling / COW 语义，它很难判断哪些 dirty lines 是完整文件系统 transaction 的一部分。

## 实验与结果

- caching layer 测试显示：在所有 cache mode 和 cache operation 中，只要 crash 发生在 ACK 之后，Open CAS 都能恢复数据和 metadata，符合其 data integrity guarantee。
- operation-on-the-fly crash 下，cache miss 和 cache eviction 返回 C，而不是 B：最新写入可能丢失，但 invalid bit 防止 corrupted line 被读出或 flush。
- write cache hit 是主要 bug window：WT、WB、WI、WO 在 repeat write 的 write cache hit 上，Result-2 均为 B；WA 例外是因为其 write path 不同。
- WA mode 的 cached-data write 也会返回 B：它先写 backend，再 invalidate cache metadata；如果第二步 crash，cache layer 仍可能把 stale cache data 返回给用户。
- WLOT 的 trigger evidence 来自 Figure 4：4 KB cache line、16-thread FIO 下 eviction / cleaning 的 throughput drop 最明显，因此被用来定位 implicit operation crash window。
- 兼容性测试中，ext-2 和默认 ext-3 可 SR，即 fully recovered 但 recovery 慢，因为需要 fsck；这削弱了 Open CAS fast recovery 的收益。
- ext-3 / ext-4 的 writeback、ordered、journal 相关配置多出现 FE，即 flush dirty data 到 recovered file system 时遇到 I/O error；journal 配置还会出现 LE，即带 error 的 durability loss。
- btrfs 出现 FE + LS，xfs 默认和 wsync 也出现 FE + LS；LS 最危险，因为 durability loss 没有显式 error。
- NVCache 对 cache miss / hit 更稳，但 cleaning crash 仍为 B，支持作者关于 implicit cache operation 需要系统化 crash testing 的主张。

## Critical Analysis

### 论证链条

论文的主链条比较闭合：先指出 persistent block cache 改变 crash model，再从 Open CAS code / tests 中找出 coverage gap，然后用 WLOT 覆盖 implicit operation 和 operation-on-the-fly crash，最后用结果说明「ACK 后 guarantee 不等于任意 crash timing 下的 consistency」。cache-hit update 的解释尤其清楚：miss 有 invalid-before-data-write 的保护，hit 没有，因此 hot data 反而比 cold data 更容易暴露坏数据。

兼容性部分也有明确机制解释：Open CAS 的 dirty-bit 粒度和 file-system transaction 粒度不一致，导致 cache 认为 clean 的 line 可能属于被 filesystem recovery 丢弃的 transaction。这个分析比单纯报告 ext / xfs / btrfs 表格更有价值。

### 假设压力测试

最脆弱的假设是 WLOT 的 timing proxy。throughput degradation 能说明 eviction / cleaning 大概率在运行，但 crash point 仍是近似定位；如果 cache device 更快、backend 更慢、cleaning policy 更激进，或者 workload 不产生明显性能谷值，WLOT 的 crash-window selection 可能变得不稳定。

第二个压力点是平台和配置范围。实验主要在 4 GB Optane PMem、256 GB SATA SSD、Open CAS 22.03.2、Linux 5.4、direct I/O 下进行。更大的 cache、更复杂的 NVMe backend、CXL memory、RAID、dm 层、不同 kernel block layer 行为，可能改变 failure frequency 或 recovery ordering。论文证明了 bug class，不等于枚举了 production deployment 的所有风险。

第三个压力点是 crash model。unmount + `casctl stop` 是 synthetic crash，模拟 in-DRAM state 丢失和 I/O 终止，但不一定覆盖真实 power loss 下的 device write cache、controller reordering、partial sector behavior、multi-queue block layer 状态。若真实硬件 crash 更乱，结果可能更糟；若平台有 power-loss protection，部分窗口可能收窄。

### 实验可信度

优点是 test matrix 覆盖了 Open CAS 的主要 cache mode 和 cache operation，并区分 ACK-after crash 与 operation-on-the-fly crash。作者还用 oracle 比对 recovered data，而不是只看 logs，这对 crash consistency 测试很重要。

不足是 baseline 不是「现有 crash testing tool 无法发现这些 bug」的直接对照，而是通过 Open CAS 内建测试缺口和 WLOT 的新覆盖来说明必要性。compatibility 测试也只用 repeat write + WB / WO 作为主要暴露器；这合理但不完整，不能说明 WA / WI 在更复杂 workload 下的端到端风险更小。

### 系统性缺陷

论文揭示的系统性缺陷不是 Open CAS 某处简单少 flush，而是 block cache abstraction 与 file-system recovery abstraction 之间没有共同 transaction 边界。cache 层追求透明性和性能，不记录 operation log；filesystem 层以为缓存层 crash 后消失。两边都局部合理，组合后不可靠。

论文未深入讨论 production mitigation 的可运维性。例如 checksum per cache line、post-recovery data synchronization、filesystem-aware recovery 都被提出，但没有量化 overhead、配置复杂度、false positive、recovery time、与 existing Open CAS modes 的兼容性。对于系统管理员，论文说明「有风险」，但还没有给出可直接部署的 decision procedure。

## 局限与 Future Work

- **局限 1**：WLOT 对 implicit operation 的识别依赖性能下降，不是形式化或 instrumentation-level 的 crash point 控制。后续可比较 gray-box throughput trigger 与 kernel tracepoint / eBPF instrumentation 的覆盖率和误差。
- **局限 2**：实验平台和 Open CAS 版本单一。后续应在 NVMe SSD、不同 cache sizes、不同 kernel versions、不同 Open CAS cleaning / eviction policies 上复测，量化 failure window 的频率和敏感性。
- **局限 3**：compatibility 测试覆盖了主流文件系统特性，但 workload 较窄。后续可以用多文件、rename / fsync / mmap / metadata-heavy workloads 测试 journal / COW transaction 与 cache dirty-line 状态的交互。
- **Future work 1**：设计 filesystem-aware cache recovery protocol，让 cache line dirty state 能表达「属于哪个 filesystem transaction」，并用 ext-4 journal / btrfs COW 的 crash matrix 验证是否消除 LE / LS。
- **Future work 2**：为 persistent block cache 加入低开销 checksum 或 commit marker，机器可验证目标是让 write cache hit 和 cleaning operation crash 从 B 降为 C 或 R，同时报告 throughput / latency / recovery-time overhead。
- **Future work 3**：构建跨 cache system 的 crash-consistency benchmark，把 Open CAS、NVCache、bcache、flashcache、OrthusCAS 等放进同一 WLOT / tracepoint harness，区分系统特有 bug 和 abstraction-level bug。

## 相关

- **相关概念**：[[Crash-Consistency]]、[[Crash-Recovery]]、[[Persistent-Memory]]、[[Page-Cache]]、[[Journaling]]、[[Copy-on-Write]]、[[Direct-IO]]
- **同类系统**：Open CAS、NVCache、bcache、flashcache、OrthusCAS、First Responder、Assise、NyxCache
- **同会议**：[[ATC-2025]]
- **源材料**：[[atc2025-duan-shaohua]]、[[atc2025-duan-shaohua.pdf]]
