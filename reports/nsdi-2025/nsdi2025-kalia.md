# Towards Energy Efficient 5G vRAN Servers

**作者**：Anuj Kalia (Microsoft), Nikita Lazarev (MIT), Leyang Xue (University of Edinburgh), Xenofon Foukas (Microsoft), Bozidar Radunovic (Microsoft), Francis Y. Yan (Microsoft Research and UIUC)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/kalia
**源文件**：[[nsdi2025-kalia.pdf]]

---

## 一、背景

5G 虚拟化无线接入网（vRAN）正在取代传统专用硬件基站，在通用服务器上运行蜂窝无线协议栈。vRAN 的优势包括多供应商生态、易维护和快速功能升级。然而，基站是蜂窝网络的主要能耗来源——仅中国就部署了约 210 万个 5G 基站，按每台 vRAN 服务器 240W 计算，即使 1% 的节能也意味着每年约 4400 万 kWh 的电力节省。

蜂窝网络大多数时间处于低利用率状态（一项研究显示超过 50% 的时间段流量低于峰值的 1%），但当前 vRAN 部署禁用了所有 CPU 节能机制，始终以最高频率运行 CPU，造成巨大的能源浪费。

---

## 二、要解决的问题

vRAN 软件有两个独特属性使得传统 CPU 节能技术无法直接应用：

1. **严格的亚毫秒级实时截止时间**：vRAN DU（Distributed Unit）的大多数线程必须在 500μs 的 TTI（Transmission Time Interval）内完成处理。违反截止时间的后果从掉话到整个 cell 离线崩溃不等。传统的 OS 级频率调节（如 HWP）和深度 C-state 睡眠的响应时间在几十毫秒级别，远慢于 TTI 周期。

2. **黑箱特性**：vRAN 软件通常是供应商提供的闭源专有二进制文件，运营商无法直接修改代码来添加测量或优化逻辑。已有的实时系统节能方法需要源码级别的 deadline slack 测量，难以直接应用。

3. **CPU 负载的高变异性**：在亚毫秒时间尺度上，CPU 负载可能从几乎为零突然跳到最大值（如流量突发或控制面操作），使得简单的频率调节极易导致截止时间违规。

---

## 三、洞察与设计

**关键洞察**：蜂窝网络在大部分运营时间内处于低利用率状态，如果能够可靠地将"低负载"时段与"高负载"时段区分开来，就可以在低负载时段安全地降低 CPU 频率来节能——关键在于不能简单地跨所有时间测量 slack（那样 slack 为零），而必须分别测量低负载时段的 slack。

基于这一洞察，RENC（Rate-limiting and Energy-efficient Networking Control）系统采用以下设计：

1. **分离低/高负载时段**：通过 MAC 层速率限制与 CPU 频率变化的耦合来建立安全的低负载时段。降频前先施加 MAC 速率限制防止流量突发；升频后才解除速率限制。严格控制这些变化的顺序和时序。

2. **透明的 deadline slack 测量**：
   - 对 interrupt-driven 线程：利用 Linux eBPF 在调度器的 `sched_switch` 钩子处测量线程活跃时间，计算 "relaxed slack"（不依赖 TTI 边界对齐的保守估计）
   - 对 busy-polling 线程：通过 dyninst 二进制重写框架对少量关键函数进行插桩测量

3. **控制面 CPU 尖峰处理**：通过拦截 FAPI 和 F1AP 接口上的控制消息（如 UE 附着/脱离），检测即将到来的 CPU 负载尖峰，反应式地临时提升 CPU 频率。

4. **迭代式频率调优**：在每个频率配置下收集足够多的低负载 slack 样本，当 slack 高于阈值（默认 10%）时逐步降低频率，优先调低 uncore 频率（影响所有核心且节能效果显著）。

---

## 四、实现细节

- **代码规模**：2500 行 C/C++ 代码 + 100 行 eBPF (libbpf) 代码
- **运行方式**：RENC 作为用户态 agent 运行于 DU 外部，不需要专用 CPU 核心，仅占用约 20% 的一个 CPU 核心
- **eBPF slack 测量**：
  - 在内核中完成全部 slack 计算，避免高频 kernel-user 消息传递（否则每秒 20 万条消息需要专用核心）
  - 每个核心维护两个定长活跃区间数组（分别对应低/高负载），在每次 `sched_switch` 时更新
  - 用户态 agent 仅每 5 秒读取一次 slack 值
  - eBPF 开销 < context switch 成本的 4.6%（每次调用 70ns @1GHz）
- **频率控制接口**：通过 Linux sysfs 控制 CPU core 频率，通过 MSR（Model-Specific Register）控制 uncore 频率。最大延迟分别为 1100μs 和 2300μs
- **流量估计**：上行用 UE 的 Buffer Status Reports (BSR)；下行用 DU 与 CU 接口的吞吐量
- **低/高负载转换**：最近 50ms 所有样本低于峰值的 1% 则进入低负载；任一样本超过 1% 立即切换到高负载
- **控制面尖峰**：拦截 WLS 库的 FAPI 接口检测 RACH 消息，通过 pcap 捕获 F1AP 消息。检测到附着触发器后保持高负载 200ms，脱离触发器后保持 1s

---

## 五、实验结果

**测试平台**：HPE DL110 Gen10 telco 服务器，Xeon 6338N CPU (32 核)，Intel FlexRAN PHY，Foxconn 4×4 RU (3.5GHz, 100MHz 带宽)，商用 5G 核心网。

| 指标 | 默认配置 | C1 states | C1 + HWP | C1 + RENC |
|------|---------|-----------|----------|-----------|
| CPU 功耗（空闲） | 131W | 119W | 123W | **66W** |
| 服务器功耗（空闲） | 242W | 225W | 229W | **160W** |
| CPU 节能百分比 | - | 9% | 6% | **45%** |
| 服务器节能百分比 | - | 7% | 5% | **29%** |

**网络性能影响（SpeedTest）**：

| 指标 | 无 RENC | 有 RENC |
|------|---------|---------|
| 下行 Mbps | 486–520 | 499–520 |
| 上行 Mbps | 29.6–29.7 | 29.7–29.7 |
| Ping ms | 27.1 (σ=3.3) | 27.9 (σ=3.4) |

**实际流量场景**：
- 视频流（9 UE 720p）：平均 CPU 功耗从 121W 降至 83W（31% 节省）
- 混合流量（9 UE）：平均 CPU 功耗从 121W 降至 109W（10% 节省）

**频率分解**：Uncore 频率从 2400→800MHz 单独贡献 32% CPU 节能；core 频率额外贡献 16%。

---

## 六、批判性分析

1. **测试规模极小**：最大实验仅 9 个 Raspberry Pi UE + 2 个 cell，与真实商用基站（每 cell 可有数百 UE）差距巨大。论文辩称"实际部署通常只有 10-20 个活跃用户"，但这忽略了突发场景（体育赛事、演唱会等）。

2. **低负载定义过于保守**：仅在流量低于峰值 1% 时才节能，这意味着在中等负载（如 10-50%）时 RENC 完全不起作用。论文也承认放宽到 10% 会影响性能但"算法可以改进"——这是一个重要的未解决问题。

3. **RU 功耗影响被忽略**：论文承认 MAC 速率限制可能增加 RU 活跃时间从而增加 RU 功耗，但未量化。对于大型 MIMO 天线，RU 功耗可达 DU 的 9 倍，如果 RENC 增加了 RU 功耗，整体节能效果可能大打折扣。

4. **控制面处理过于粗暴**：UE 脱离后强制进入高负载 1 秒（200 个 TTI），这是一个非常保守的选择。在密集 UE 场景中，频繁的附着/脱离可能导致 RENC 大部分时间处于高负载状态，节能效果可能趋近于零。

5. **HWP 对比不够公平**：论文指出 HWP 的问题是"反应太慢"（60ms），但 RENC 的 uncore 频率变化延迟本身就有 2.3ms——这在 TTI 维度上也是显著的。论文没有比较两者导致的截止时间违规率。

6. **binary rewriting 的可维护性**：对 busy-polling 线程的 dyninst 插桩需要知道特定函数名和签名，DU 软件每次升级都可能导致这些接口变化，实际部署维护成本被低估。

---

## 七、AI Infra / MLSys 视角

1. **eBPF 用于实时系统观测的模式可迁移**：RENC 利用 eBPF 在不修改目标二进制的情况下透明测量线程 deadline slack 的方法，可以借鉴到 AI 推理系统的延迟监控中。例如，vLLM 或 TensorRT-LLM 等推理引擎也有严格的延迟 SLO，可以用类似方法测量请求处理的 slack 来动态调节 GPU 频率或 batching 策略。

2. **耦合式负载管理思路**：RENC 将 MAC 速率限制与 CPU 频率变化严格排序的设计模式，与 AI 推理系统中 admission control + 资源调度的联动有相似之处。在 LLM serving 中，可以将请求准入控制与 GPU 频率/功耗管理耦合，在低负载时降频节能。

3. **分时段 slack 测量的思路**：区分低负载和高负载时段分别测量 slack 的方法，可以应用于 GPU 集群的功耗管理——训练集群在 checkpoint、gradient sync 等空闲阶段可以降低 GPU 频率。

4. **值得跟进的方向**：
   - 将类似方法扩展到 GPU 频率管理，用于 AI 推理场景的节能
   - 结合 LLM 推理的 prefill/decode 阶段特性，设计更精细的功耗管理策略
   - 探索 eBPF 在 GPU driver 层面的可编程性，实现透明的 GPU 工作负载观测

---

## 八、总结

RENC 是首个针对商用闭源 vRAN 软件的 CPU 节能系统，通过 eBPF 透明测量 deadline slack、MAC 速率限制与 CPU 频率耦合控制、以及控制面尖峰处理三项技术，在不影响网络性能的前提下，实现空闲模式下 CPU 功耗降低 45%（服务器整体降低 29%）。系统设计遵循 O-RAN 原则，仅需最少的供应商信息即可运行。主要局限在于仅针对低负载（<1% 峰值流量）场景节能、测试规模较小、且未考虑 RU 侧功耗影响。
