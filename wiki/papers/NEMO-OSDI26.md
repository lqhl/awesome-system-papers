---
type: paper
name: NEMO
full_title: "Finding NEMO: Nimble and Expressive Memory Observability"
authors: [Shihang Li, Matthew Giordano, Tushar Garg, Rohan Kadekodi, Daniel S. Berger, Baris Kasikci, Thomas Anderson, Simon Peter]
venue: OSDI
year: 2026
tags: [memory-management, cxl, hardware-telemetry, memory-tiering, noisy-neighbor]
source_pdf: "[[osdi26-li-shihang.pdf]]"
source_md: "[[osdi26-li-shihang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 灵活而及时的内存可观测性（OSDI 2026）

> **原题**：Finding NEMO: Nimble and Expressive Memory Observability

> **一句话总结**：NEMO 在内存控制器旁边放一个不阻塞数据路径的 match–update–notify pipeline，让 OS 用地址映射、简单计数和阈值定义自己的内存 telemetry；一个 CXL 2.0 FPGA 原型把 HeMem 的热集恢复从 324 秒缩到 67 秒、把 MEMTIS 找齐 95% 拆页候选的时间最多缩短 10.4 倍，并以 0.09% CPU 开销达到 1 ms 轮询 MBM 需要 32% CPU 才有的 noisy-neighbor 控制效果，但原型只观察 CXL 慢层，而且通知硬件没有实现，是用 1 ms 轮询模拟的。

## 问题与动机

服务器内存已经不再是一个均匀的 DRAM 池。多 socket [[NUMA|NUMA]]、加速器统一内存和 [[CXL]] 扩展内存带来不同延迟、带宽和容量；OS 要根据访问行为决定页面放哪一层、2 MiB THP 是否应该拆分，以及哪个租户在制造带宽干扰（§1、§2）。这些策略需要同时满足五个条件：覆盖率、及时性、粒度、灵活性和低开销。

现有方法总要牺牲其中几项：

- soft page fault 和 PTE accessed/dirty bit 很灵活，但 fault 或 page-table scan 会消耗大量 CPU。生产系统甚至把扫描周期放到 30 秒，反应自然很慢。
- PEBS 可以采样 cache miss，却在采样率、CPU 开销和反应速度之间取舍；它还看不到 prefetch、non-temporal access 等真实 DRAM 流量，也不能让 host 直接 profile VM guest。
- CPU、MBM 和内存控制器的固定 counter 开销低，但通常只给 core、channel、bank 或 socket 汇总，过滤条件和聚合方式在硬件出厂时已经固定。
- 固定功能 hot-page tracker 能覆盖特定策略，却不能同时表达“每页热度”“hugepage 内 4 KiB skew”“每租户带宽”等以后才出现的需求。

NEMO 的目标不是提出新的 tiering 或 throttling policy，而是给这些 policy 一个共同的、由 OS 定义的观测底座。

## 关键观察 / 隐含假设

- **观察 1：内存控制器是看见真实内存请求的天然位置。** 它能观察发往自己所管内存的 read/write、物理地址和请求元数据，既不会漏掉 prefetch，也不用让 CPU 处理逐访问事件（§1、§3）。
  - **依赖假设**：要得到整机视图，每个相关 controller 都必须部署 NEMO。论文 FPGA 只覆盖 CXL 慢层，所以 HeMem 与 MEMTIS 仍靠 PEBS 观察本地 DRAM。
- **观察 2：很多 OS telemetry 都能写成一次有限更新。** 请求先按 read/write 和地址过滤，再把地址翻译成一个 SRAM state index，对一个 state 执行加法、位运算等 associative、commutative update，最后可检查阈值（图 2、§3.1）。
  - **依赖假设**：策略真正需要的是计数、bitmap 或简单聚合。精确 top-K、方差和需要同时读写多个 state 的算法不在单 pipeline 表达范围内。
- **观察 3：一张可重编程 translation table 可以解耦物理地址与策略语义。** 一页可映射到一个计数器，一个 hugepage 可映射到 512 个 basepage state，多个页面也可映射到同一个 tenant state；OS 可在迁移、分配和释放时增删条目（§3.1–§3.3）。
  - **依赖假设**：kernel/hypervisor 能及时维护物理页所有权和映射。更新滞后会把访问算给错误页面或租户。
- **观察 4：有限 SRAM 可以靠不同粒度和 time multiplexing 复用。** 热页只需一个 state，hugepage skew 需要 512 个；装不下时，OS 每个 scan interval 改写 translation，轮流观察区域（§3.3、§6.1）。
  - **依赖假设**：workload 变化速度慢于完整 sweep；大内存且快速 phase change 时，轮到某页之前的信息已经过时。
- **假设 1：off-data-path 就等于不会影响应用内存延迟。** pipeline 只旁路读取请求 header，并在本地 SRAM 更新，设计上不阻塞 DRAM/CXL 路径；但论文没有 ASIC 时序、功耗和真实 IMC 集成结果。

## 核心方法

### 1. 每个 controller 上的 match–update–notify pipeline

每个内存请求仍按正常路径发往一个 channel，同时把 header 广播给该 controller 的所有 NEMO pipeline。每个 pipeline 包含三段（图 1–2、§3.1）：

1. **Match**：用 OS 配置的 mask 和 shift 从物理地址提取 primary key；key 查 SRAM translation table 得到 base index。需要更细粒度时，再从地址算 sub-region offset，与 base 相加得到最终 state index。没有匹配项就丢弃这次 telemetry 更新。
2. **Update**：对选中的 SRAM state 做一次固定周期 read-modify-write。更新必须 associative 且 commutative，这样一个 controller 的多 channel、多个 controller 以及多个 pipeline 的局部结果都能在任意顺序合并。
3. **Notify**：更新后用简单比较谓词检查阈值，可以向 host 报警。普通策略也可只由 OS 定期读取 counter。

pipeline 的 state SRAM 按 channel 分 bank，连续写同一 state 时用 value forwarding 解决 hazard，不停顿请求流。它只能一次更新一个 state；若 telemetry 需要多个独立统计量，可以用多条 pipeline，或由 host 读取后组合。

### 2. translation 把“地址”变成“页面、子页或租户”

primary mask/shift 决定主区域，例如 2 MiB hugepage；secondary mask/shift 决定区域内偏移，例如 4 KiB basepage。translation entry 的值不是固定物理意义，而是 OS 分配的 state base。于是同一套硬件可支持三种映射（Listing 1–3）：

- 一对一：一个 hugepage 对应一个 hotness counter。
- 一对多：一个 hugepage 的 base index 加 0–511 offset，对应 512 个 basepage counter。
- 多对一：某 tenant 的所有 hugepage 都指向同一个 bandwidth state。

OS 还能只纳入选中的页面，让同一批 state 在多个区域间 time-multiplex。这个设计把灵活性放在地址映射，而不是在 controller 中运行通用程序。

### 3. Driver 负责验证、分配与全局合并

OS 服务提交 filter、translation、update、可选 notify predicate 和 read-side effect。NEMO driver 验证规则，为每个相关 controller 分配 pipeline 与 SRAM bank，并检查 translation entry 是否落在该 controller 服务的物理范围内（§3.2）。

每个 controller 暴露一段由 SRAM backing 的 telemetry memory region。driver 用普通 load 高带宽读出 state；可配置 reset-on-read，让一次读取直接得到最近 interval 的增量。因为 update 可交换、可结合，driver 可把各 controller 的局部 state 做 sum、XOR 等 fold，恢复逻辑上的整机统计。

### 4. FPGA 原型及其真实边界

原型使用 Altera Agilex 7、CXL 2.0 Type-3 hard IP、16 GiB DDR4 和两个 memory channel，逻辑运行在 400 MHz。host 是 32 核 Xeon Gold 6430；实测 host DRAM 延迟 114.1 ns、带宽 114.9 GiB/s，CXL DRAM 为 380.3 ns 和 16.4 GiB/s（§4）。

每条 pipeline 有 8192-entry translation table 和每 channel 8192×64-bit state array，共约 150 KiB。NEMO 逻辑占整个 FPGA bitstream 的 4.4% M20K SRAM 和 4.8% logic；最大的 MEMTIS 配置用 8 条 pipeline，约 1.2 MiB telemetry SRAM（表 2、§4）。

两个限制容易被摘要掩盖：第一，原型只看 CXL-attached DRAM，不能观察 CPU 本地 DRAM；第二，notify stage **没有实现**，作者用一个 core 每 1 ms 轮询 counter 来模拟通知。论文中的“立即通知”和 noisy-neighbor 结果因此验证了软件策略与理想接口，不是实际中断路径。

## 三个策略如何使用 NEMO

### HeMem：更快发现热集变化

HeMem 原来以 0.02% PEBS 采样率估计 hugepage hotness，每秒整理样本。HeMem-NEMO 对 CXL 慢层的每个访问更新 per-hugepage counter，读后清零；本地快层仍用 PEBS，并按采样率缩放 NEMO count，让两层分数可比较。tiering policy 本身不变（§5.1）。

### MEMTIS：观察 THP 内部 skew

一条 pipeline 数 hugepage 总访问，另七条各自跟踪 16 个 hugepage 的 512 个 basepage counter，所以同一时间观察 112 个 hugepage。每 500 ms 在 active/inactive LRU list 间轮换；总体访问不多但内部有热 4 KiB 页面时，也能被选为 split candidate。SRAM 不够时的代价是必须完成一轮 sweep（§5.2）。

### Linux cgroup：按 tenant 归因带宽

所有属于 tenant 的 hugepage 都映射到一个 counter。用户态 QoS controller 读 counter、维护 bandwidth EWMA，再调整 Linux cgroup CPU quota；论文没有用不够准确的 Intel MBA 做执行器。目标是限制 1 GiB/s 的合成 noisy neighbor，保护同机 FlexKVS（§5.3）。

## 设计取舍

- **固定流水线换可预测线速。** 每请求只有一次简单 update，容易并行且不阻塞数据路径，却不是任意可编程 processor。
- **SRAM state 换 DRAM 带宽。** telemetry 不产生额外 DRAM 读写，但 page 数量随内存容量增长，细粒度完整驻留会需要大量 SRAM。
- **time multiplexing 换覆盖范围。** 轮换能观察超过 SRAM 容量的页面，但会降低每页观察占空比，并给 phase change 增加最多一轮 sweep 的延迟。
- **物理地址归因换控制面维护。** controller 不理解进程和租户；页面迁移、共享、COW、分配与释放时都依赖 OS 同步更新 translation。
- **通知换轮询。** 设计中的 threshold interrupt 可减少 host polling，但本原型用轮询模拟，面积、中断合并、风暴控制与真实 CPU 开销没有验证。
- **controller 局部完整覆盖换 cache 可见性。** NEMO 看见到达 controller 的所有请求，却看不到 cache hit；“full coverage”应理解为所管内存流量，而不是程序的每次 load/store。

## 实验设置

- 三个 end-to-end case 分别集成 HeMem、MEMTIS/Linux 5.15 和 Linux cgroup；应用覆盖 FlexKVS、FASTER KV 与 Silo（§5）。
- HeMem 的 FlexKVS 实验使用 24 GiB、1:2 fast:slow 和完全热集切换；FASTER KV 使用 30 GiB、1:1、YCSB-B、16 client thread，并改变 value size。
- MEMTIS 的 Silo 使用 YCSB-C、90M key、20 核，fast:slow 从 1:2 扫到 1:8。为让只看 CXL 的 NEMO 见到所有页，NEMO 配置先把数据固定在 CXL 180 秒，反而让 PEBS baseline 提前开始迁移。
- noisy-neighbor 实验让一个单核程序交替 0.5 秒做 non-temporal store 和 sleep；MBM 从 10–1000 Hz 扫描，NEMO 用模拟通知和每 50 ms 清 counter。

## 实验与结果

- **HeMem 热集反应**：FlexKVS 在 120 秒时完全切换热集。HeMem-NEMO 67 秒恢复稳态，受迁移带宽限制；默认 0.02% PEBS 要 324 秒，约慢 5 倍。NEMO 处理开销为 0.89% CPU；提高 PEBS 采样率会更快，但采样超过 1% 已会明显伤害应用（图 3–4、§5.1.1）。
- **HeMem 应用吞吐**：FASTER KV 的小 value 会让每个 hugepage 内访问接近均匀，两种 telemetry 相近；value 变大、prefetch 流量增加后，PEBS 看不到这些访问，NEMO 才能找出热页，端到端吞吐最高提高约 1.69 倍。这个结果同时依赖具体 object size 与 prefetch 行为（图 5、§5.1.1）。
- **MEMTIS 拆页效果**：NEMO 找到超过 2 倍的 skewed hugepage，并在约 150 秒内找齐 95% candidate，最多比 PEBS 快 10.4 倍。fast:slow 为 1:8 时，MEMTIS-NEMO 的 Silo 吞吐比 MEMTIS-PEBS 高 13%，且各分位延迟更低；NEMO 总 CPU 开销 3%，PEBS 为 2.89%（图 6–7、§5.2.1）。
- **带宽准确性与隔离**：NEMO 和 MBM 对 non-temporal store 都在应用级 ground truth 的 0.1% 内。不限速时 FlexKVS p99 增加约 22%；NEMO 与 1 ms MBM polling 限速后分别只增加 5.2% 和 5.5%，最终都受约 10 ms cgroup actuation 限制（图 8、§5.3.1）。
- **noisy-neighbor CPU 开销**：MBM 每 100 ms 轮询只用 0.7% core，但 FlexKVS p99 仍增加 13%；每 1 ms 轮询把 p99 降到 5.5%，代价是 32% CPU。模拟 NEMO notification 获得相近 5.2% p99 结果，只报告 0.09% CPU，约低 350 倍（图 9、§5.3.1）。
- **SRAM 扩展性分析**：MEMTIS 例子中 1.4 MiB telemetry SRAM 对 16 GiB DRAM 的理论完整 sweep 约 37 秒；若保持相同比例，1 TiB tier 需要约 90 MiB SRAM。把 64-bit counter 缩到 1–4 B 可按比例减少 SRAM 或 sweep time，但这只是公式推算，没有 1 TiB 原型验证（§6.1）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| controller-side 完整计数能比 PEBS 更快跟上热集 | 图 3–5：67 秒对 324 秒；大 value FASTER KV 最高约 1.69 倍吞吐 | NEMO 只观察 CXL 慢层，本地 DRAM 仍用 PEBS；两个 KV workload | 强 |
| 同一 pipeline abstraction 能支持页面、子页和租户三种语义 | Listing 1–3 与三个集成：一对一、一对多、多对一 translation | 都是地址到单 state 的简单聚合，不能证明任意 telemetry | 强 |
| 细粒度 skew telemetry 能改善 THP 拆分 | 图 6–7：超过 2 倍 candidate、最多快 10.4 倍、1:8 下高 13% 吞吐 | 112 hugepage 并行观察、500 ms 轮换；一个 Silo workload | 强 |
| threshold notification 可低成本实现及时隔离 | 图 8–9：5.2% p99 增幅、0.09% CPU，对比 MBM 的 5.5% 与 32% | notify stage 未实现，由 1 ms 轮询模拟；actuator 仍有约 10 ms 延迟 | 中 |
| NEMO 适合现实 controller 资源预算 | FPGA 每 pipeline 约 150 KiB，NEMO 占 4.4% SRAM/4.8% logic | FPGA 资源比例不等于 ASIC IMC 面积、功耗或时序 | 中 |

## 批判性分析

### 论证链条

论文先把 memory observability 分成五个维度，再证明软件采样和固定硬件各缺一半，随后用 translation + 单 state update 取中间设计点。三个 case 的映射形态确实不同：页面是一对一、THP 是一对多、tenant 是多对一，因此“共同 substrate”并非只换名字的 hotness tracker。最薄弱的链条是 notify：设计、Linux controller 和结果都依赖它，但 FPGA 没有实现，0.09% CPU 的关键结果来自轮询模拟。

### 假设压力测试

若 policy 需要精确 top-K、方差、跨地址相关性或多步状态机，单次 associative update 不够；论文建议以后 chain pipeline，但没有实现。若 1 TiB 内存热集在几十秒内快速漂移，均匀 sweep 会在看到页面前过时。共享页、页面迁移、ballooning 和 VM remap 频繁时，translation 更新也可能成为新瓶颈或产生短暂错误归因。controller 只能看到下层请求，cache hit 密集的 workload 还需另外的观测来源。

### 实验可信度

真实 CXL Type-3 FPGA、三个现有系统、不同 telemetry 粒度、端到端应用指标与资源表，使实现证据比纯模拟更强。每个 case 也披露了慢层-only 的限制。仍然缺少多 controller/多 socket 聚合、真实 VM tenant、页表高 churn、controller saturation、重复实验统计和 ASIC PPA。NEMO 通知是模拟的，MEMTIS 还特意先把内存固定在 CXL 180 秒，因此结果不能直接代表无改动生产部署。

### 系统性缺陷

NEMO 把新的共享硬件资源暴露给多个 OS subsystem，却没有完整的 pipeline admission、优先级、配额或冲突语义。恶意或错误规则可能耗尽 translation/state、制造 interrupt storm，或通过读取细粒度访问模式泄露租户行为；论文只给出“driver 验证地址范围”的 threat model。telemetry region 采用可缓存普通 memory 而非 MMIO，需要显式 invalidation，原型读出路径也未完全 pipeline。设备故障、counter overflow、controller hotplug 和规则版本切换的一致性都没有处理。

## 局限与后续工作

- **局限 1**：FPGA 只监控 CXL-attached memory，本地 DRAM 仍依赖 PEBS；没有全机 NEMO 部署结果。
- **局限 2**：notify stage 没有实现，noisy-neighbor 的低开销结论包含理想化通知语义。
- **局限 3**：每请求只能更新一个 state，复杂 telemetry 需要多 pipeline 或 host 后处理。
- **局限 4**：大内存细粒度观察受 SRAM:DRAM 比例限制，time multiplexing 会降低及时性。
- **后续工作 1**：在 ASIC/IMC 原型上报告面积、功耗、critical path、最大 request rate、真实中断合并和内存延迟影响。
- **后续工作 2**：在多 socket、多 CXL controller 和 VM 环境测试 translation churn、跨 controller fold、一致性与 tenant isolation。
- **后续工作 3**：给 pipeline、translation entry、state 和 notification 建立配额与 verifier，并注入 overflow、interrupt storm 和设备重置故障。
- **后续工作 4**：实现 chained pipeline 或 sketch，在固定资源下量化表达能力、误差界和 sweep time，而不是只给扩展方向。

## 相关

- **相关概念**：[[CXL]]、[[PCIe]]
- **相关系统**：HeMem、MEMTIS、Intel MBM
- **同会议**：[[OSDI-2026]]
