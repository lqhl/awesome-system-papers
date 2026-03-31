# Disentangling the Dual Role of NIC Receive Rings

**作者**：Boris Pismenny（EPFL & NVIDIA）、Adam Morrison（Tel Aviv University）、Dan Tsafrir（Technion – Israel Institute of Technology）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation），2025 年 7 月 7–9 日，Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/pismenny
**源文件**：[osdi25-pismenny.pdf](../../papers/osdi-2025/osdi25-pismenny.pdf)

---

## 一、背景

随着以太网速率迈入百 Gbps 时代，网络密集型应用的性能高度依赖 DDIO（Direct Data I/O）等技术。DDIO 允许 NIC 将 DMA 读写直接定向到 CPU 的最后一级缓存（LLC），从而绕过主存，降低包处理延迟并节省内存带宽。

然而，DDIO 的有效性受限于 **I/O 工作集大小**——即 NIC 在某段时间内 DMA 访问的内存区域总量。若 I/O 工作集超出 LLC 容量，新到达的包会将尚未处理的包从 LLC 中逐出（"leaky DMA"问题），导致 CPU 不得不从主存读取包数据，内存带宽成为瓶颈。

为支持 100 Gbps 及以上速率，系统通常采用多核并行处理，每个核心维护独立的 per-core Rx ring（默认大小 ≥1Ki 条目）。随着 NIC 带宽持续增长，Rx ring 的数量和大小都必须增加，I/O 工作集的膨胀问题因此愈发严重。

---

## 二、要解决的问题

### 问题一：I/O 工作集超出 LLC 容量

多核系统中，I/O 工作集大小下界为 N×R×1500B（N 为 Rx ring 数量，R 为每个 ring 大小）。以 16 核 + R=1024 的配置为例，I/O 工作集约为 24 MiB，轻松超出典型 LLC 容量，造成吞吐量下降最高 0.8×、延迟增加最高 37×。

### 问题二：现有解决方案的局限

- **SmallPrivRing**（缩小 Rx ring）：ring 变小后无法吸收包突发，导致丢包，不实用。
- **ShRing**（多核共享 Rx ring）：减少了 I/O 工作集，但存在两大缺陷：
  1. 共享 ring 的 tail 更新需要软件锁，带来同步开销；
  2. 在负载不均衡（load imbalance）场景下，过载核心会独占共享 ring，阻塞其他核心接收包，系统被迫降级回 per-core 大 ring，失去 I/O 工作集优化收益。

### 问题三：负载不均衡在生产环境中普遍存在

论文通过分析 2018 年 NYC CAIDA 数据集证明，RSS 在 16 核场景下的负载倾斜比（最大/最小包率之比）长期维持在 325–433%，并非"病理性"的边缘情况。

---

## 三、核心设计

### 根因分析：Rx ring 的两重职责被耦合在一起

传统 Rx ring 同时承担两个正交的 producer-consumer 结构：

| 结构 | 生产者 | 消费者 | 元素 |
|------|--------|--------|------|
| 内存分配 | CPU core | NIC | 空 buffer |
| 包接收 | NIC | CPU core | 满 buffer（含包数据）|

这种耦合导致：分配 buffer 的数量与接收突发包的能力必须同步扩缩，无法独立调整。

### rxBisect：解耦分配与接收

rxBisect 将每个 Rx ring 拆分为两类独立的 ring：

- **Ax ring（Allocation ring）**：由 CPU 填充空 buffer，由 NIC 消费。**可以很小**（如 128 条目），用于控制 I/O 工作集。
- **Bx ring（Bisected reception ring）**：由 NIC 填入到达的包（含包数据指针和元信息），由 CPU 消费。**保持大尺寸**（如 1Ki 条目），用于吸收包突发。

**跨核 buffer 共享由 NIC 硬件完成**：每个 Bx ring 可与多个 Ax ring 关联，NIC 可以从任意可用的 Ax ring 取 buffer 存放到达的包，无需软件锁。当 NIC 消费了某核的 Ax buffer 来服务不同核的 Bx ring 时，NIC 通过 Bx descriptor 中的专用字段通知源核补充 Ax buffer。

**关键属性**：
- 各核 Ax ring 合计大小远小于 Bx ring 总大小，I/O 工作集大幅缩减；
- 过载核心的 Bx ring 填满时，只影响该核的包接收（包被 NIC 丢弃），不影响其他核继续从其各自 Bx ring 接收包；
- 软件只在跨核归还 buffer 时涉及内存分配器，频率低，成本可摊销。

---

## 四、实现细节

### 软件侧接收流程

核心接收函数（见 Listing 1）同时处理两件事：
1. 从 Bx ring 取出已到达的包；
2. 检测并响应 NIC 对 Ax buffer 的消费通知，立即补充新的空 buffer。

通过 sense-reverse 机制（"generation" bit）以 lockless 方式轮询 Bx ring 头部，无需 MMIO 读取 NIC 寄存器。doorbell 写（MMIO）仅在更新 Ax ring tail 时触发，频率较低。

### 内存分配器要求

跨核 buffer 共享要求支持"A 核分配、B 核释放"，这是 DPDK 的 `rte_pktmbuf_pool` 和 Linux 的 page pool 等现代多核分配器已原生支持的能力（双层设计：per-core cache + 共享池）。实验测量显示，分配器调用延迟与 privRing 相比增加不超过 15 cycles。

### 软件 NIC 框架（原型）

由于 rxBisect 需要 NIC ASIC 改动，作者基于 DPDK 实现了一个专用 emulation 框架，用一个专用"emulator core"模拟 NIC 行为（包括 RSS 分发、虚拟 Bx/Ax ring 管理、RDMA write 模拟），从而在不修改 NIC 硬件的前提下评估 rxBisect。

### Ax/Bx 配置参数

- **Bx ring 大小**：≥1Ki（与 privRing 的 Rx ring 大小一致，足够吸收突发）
- **Ax ring 大小**：满足 `k × |Ax| × 1500B ≤ DDIO容量`（k 为 Ax ring 总数），同时需保证能吸收一次突发（`k × |Ax| ≥ |Bx|`）
- **关联策略**：推荐全对全（all-to-all）Ax-Bx 关联，最大化跨核 buffer 共享灵活性

---

## 五、实验结果

**实验平台**：两台 Dell PowerEdge R640，双路 2.1GHz Xeon Silver 4216（16 核，22MiB LLC），128GiB DDR4，两对 100Gbps NVIDIA ConnectX-5 NIC，背靠背连接。

**应用负载**：
- NAT、LB（FastClick 实现的网络功能，10M 条目哈希表）
- MICA key-value store（128B key + 1024B value，95% PUT）

**对比基线**：
- `privRing`：默认 1Ki 条目 per-core Rx ring
- `smallPrivRing`：128 条目 per-core Rx ring（不实用但作为 yardstick）
- `shRing`：每 NIC 一个共享 1Ki Rx ring，8 核共享
- `dynamic shRing`：自适应在 shRing 和 privRing 之间切换

### 平衡负载（Balanced Load）

| 场景 | rxBisect vs privRing | rxBisect vs shRing |
|------|---------------------|-------------------|
| NAT/LB（200 Gbps，1500B 包）| 吞吐提升最高 20%，延迟降低最高 11× | 接近持平 |
| MICA（均匀分布） | 吞吐提升 37% | 提升 7% |
| MICA（Zipf 偏斜分布） | 吞吐提升 14% | 提升 6% |

### 不均衡负载（Imbalanced Load）

| 场景 | rxBisect vs dynamic shRing |
|------|---------------------------|
| 处理时延可变（内存访问次数增加） | 最高提升 12% |
| 流量倾斜（1 核占比增加） | 最高提升 20%+ |
| CAIDA 真实 trace + PageRank 共置 | LB 提升 16%，NAT 提升 20% |
| CAIDA + STREAM 内存压力 | 提升最高 16%（emulated 对比） |

### 低流量下的同步开销

shRing 在低负载时仍因软件锁产生 34–46% 额外 cycles（vs privRing），而 rxBisect（emulated）比非 emulated shRing 少消耗约 10% cycles。

---

## 六、批判性分析

### 1. 评估基于软件 emulation，未在真实 ASIC 上验证

论文核心贡献 rxBisect 需要修改 NIC ASIC，但所有实验都通过软件 emulation 完成。Emulator 本身会引入约 2× 的 I/O 工作集膨胀和额外 CPU 开销，使 emulated rxBisect 与 non-emulated baseline 的比较天然不公平。论文用"apples-to-apples"框架部分规避了这个问题，但仍有多处直接将 emulated rxBisect 与 non-emulated privRing/shRing 比较。例如，在 CAIDA trace 场景下作者自己承认"non-emulated privRing 在无内存竞争时可以比 emulated rxBisect 高出 7%"，说明 emulation 的系统误差不可忽略。

### 2. NVIDIA NIC 架构师的背书过于非正式

§4.4 引用了与 NVIDIA NIC 架构师的私人沟通，表述为 rxBisect 在 ConnectX NIC pipeline 中"可行"。但该声明仅说明不超出现有 pipeline 边界，并未承诺性能等价，措辞中也明确指出"最坏情况下性能受限于单个 Ax ring 的分配速率"，实际 ASIC 的性能可能与论文预期有差距。

### 3. 负载不均衡的"普遍性"依赖单一数据集

论文通过 §3.3 中一段 2018 年 NYC CAIDA trace 论证 imbalance 普遍性，但 CAIDA 匿名化 trace 主要反映骨干网流量特征，不代表数据中心内部网络。论文本身也承认 NF 场景中 imbalance 不常见（§3.3 首行），而 RPC 场景才是高 imbalance 的典型，但 RPC 场景并未被直接评估。

### 4. 与 RDMA SRQ 的比较过于简略

§7 提及 RDMA Shared Receive Queue（SRQ）与 rxBisect 类似，但在负载不均衡下也表现差。然而论文仅一句话带过，未提供对比实验或设计层面的详细分析，而 RDMA/DPDK 混合部署场景已越来越常见，这一对比的缺失削弱了相关工作讨论的完整性。

### 5. 内存分配器的跨核开销分析不够深入

论文报告分配器开销不超过 0.2% cycles，但该数字仅来自一个流量倾斜实验的极端值，且 DPDK 的 mbuf pool 在高度不均衡时的 per-core cache 失效（一个核反复为其他核"捐赠" buffer 导致 cache 耗尽、频繁访问共享池）未被充分分析。当核数和 NIC 数进一步扩展时该开销是否仍可接受，论文未给出系统性数据。

---

## 七、总结

rxBisect 通过将传统 NIC Rx ring 的内存分配与包接收职责拆分为独立的 Ax/Bx ring，从设计上消除了"为吸收突发必须分配大量空 buffer"与"减少 I/O 工作集"之间的根本矛盾。跨核 buffer 共享被卸载到 NIC 硬件，既避免了 shRing 的软件锁开销，又在负载不均衡时不再阻塞非过载核心的包接收。适用于 100 Gbps+ 高速网络、kernel-bypass 应用（如 DPDK 网络功能、key-value store），在均衡与不均衡负载下均优于 privRing 和 shRing。主要局限在于需要 NIC ASIC 改动，目前仅有软件仿真验证；emulation 引入的系统误差使部分性能数据的可信度有所保留，且未在真实生产级 workload 下验证。
