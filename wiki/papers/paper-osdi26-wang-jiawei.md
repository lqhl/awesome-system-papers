# jwmalloc：面向移动设备的可验证内存分配器

> **原题**：jwmalloc: A Verified Memory Allocator for Mobile Devices

> **一句话总结**：论文观察到移动端同时存在频繁跨 size class 重格式化、前后台造成的峰谷内存波动、激进回收和严重线程过量订阅，于是用统一且可池化的 slab、size-class-exact 的 closed sibling tree、基于对象寿命的双缓冲回收和非阻塞接口重构 allocator；在 Mate 70 Pro 的真实场景中，相比 jemalloc 将整机指令数降低 10%，allocator 指令数降低 3.84×，CPU cluster 功耗降低 5–11%。

## 问题与动机

移动设备只有数 GB 级 DRAM，多个应用和系统服务共享内存。论文测得 allocator 指令约占 Android 和 HarmonyOS 实际工作负载全部指令的 8.2% 和 12.4%。移动端还存在高频交互、前后台切换、短对象占比高以及数百线程竞争少量 CPU 核心等情况；传统面向通用吞吐量设计的 allocator 因此同时承受 CPU、内存占用和尾延迟压力。

作者将现有 allocator 的问题归结为四类。jemalloc 的异构 slab 需要频繁拆分和合并不同大小的 range；后端保留大量不能直接服务请求的中间 range；不区分对象寿命的回收会错过邻接 range 即将释放所带来的合并机会；锁保护的共享元数据在严重 oversubscription 下可能造成优先级反转和长尾延迟。

jwmalloc 选择性能导向 allocator，而不是带 quarantine 的内存安全 allocator。作者认为 Rust、MTE 和 HWASAN 等机制与 allocator 的性能优化是正交问题，本文不处理 use-after-free 等客户端内存安全错误。

## 关键观察 / 隐含假设

- **观察 1：size class 的活跃度随时间变化，但总在用内存可能相对稳定。** 图 2 的 graphics 服务显示，不同时段由不同 size class 主导分配；图 3 显示分配次数偏向小对象，而分配字节数更平坦。这意味着同一批物理内存需要频繁重格式化。
  - **依赖假设**：不同 size class 的需求会在同一进程内共享内存，而不是始终保持稳定的独立分区。
  - **可能失效场景**：若 workload 的 size 分布长期稳定，统一 slab 和 pooling 相比现有设计的收益会减小；接近 4KB 的请求还可能因统一粒度产生额外代价。

- **观察 2：移动工作负载有明显的峰谷内存变化。** graphics 的峰值内存超过稳态的 5 倍。现有 per-range 元数据容量随历史峰值增长，却不随释放缩小，会把峰值期间的管理开销带入稳态。
  - **依赖假设**：前后台切换和屏幕关闭会产生可重复的需求下降，并且回收时机足以影响系统内存压力。
  - **可能失效场景**：持续高负载、没有明显 idle 阶段的应用不一定受益；过于激进的回收也会增加后续重新映射和 page fault 成本。

- **观察 3：range 存活时间符合 generational hypothesis。** streaming 中 90% 的 page 在 33.55ms 内变为未使用，但超过 1% 的 page 存活超过 3.22s（图 5）。因此，长寿命 range 邻近的短寿命 range 更值得延迟回收，以等待合并。
  - **依赖假设**：短寿命/长寿命的分界在目标应用和系统配置中相对稳定。
  - **可能失效场景**：寿命分布改变或没有明显 knee point 时，双缓冲的固定时间间隔可能将可用内存暂存过久，或过早丢失合并机会。

- **观察 4：线程过量订阅使锁竞争转化为 UI 可见的尾延迟。** app-market 安装场景中最多有 742 个线程被调度到 8 个核心；graphics 等 producer-consumer 工作负载的 cross-thread free 比例可接近 100%（图 4、图 6）。
  - **依赖假设**：将偶发锁失败转化为额外内存和重试工作的代价，小于阻塞高优先级线程的代价。
  - **证据强度**：中。论文给出了实际设备上的调度和 cross-thread free 测量，但非阻塞路径的最坏内存增长和公平性评估不充分。

## 核心方法

### 统一 slab 与 pooling

所有小对象 slab 使用统一大小，默认与 OS page 一样为 4KB；size class 调整为使尾部浪费受控。完全空闲的 slab 进入跨 size class 的共享 pool，后续可以直接重初始化为任意 size class。这样避免了 jemalloc 异构 slab 在需求切换时反复 coalesce，同时保持接近 jemalloc 的内存占用。线程本地结构仍维护 partial list 和 empty list，pool 通过 watermark 限制规模。

### Size-class-exact backend 与 closed sibling tree

jwmalloc 让后端维护的 range 大小集合恰好等于 allocator 的 size class 集合，避免 tcmalloc 和 jemalloc 中无法直接服务请求的中间 range。其 closed sibling tree 是 buddy tree 的推广：一个节点可以有多个子节点，并且任意连续 sibling 子序列的大小仍是合法 size class。这样可以在拆分时保留大 range，在合并时只在结果合法时合并。

例如，从 256KB range 获取 8KB 时，算法先拆出 32KB 和 224KB，再从 32KB 中得到 8KB 与 24KB，而不是沿二叉路径留下无法直接使用的中间尺寸。实现中的 MULTI-STEP-SPLIT 根据 resolution-R size class 的分解选择拆分路径。backend 还用 metadata shifting 将二维树映射到一维数组，利用 range 大小和 sibling index 计算偏移，省去 parent pointer；元数据按 4KB granularity 计为 12B，并可随 range 释放而回收。

### Lifetime-based reclamation

range 没有可合并 sibling 时进入 active buffer；回收线程交换 active 和 standby，等待时间间隔后回收 standby 中的 range。该双缓冲结构避免为每个 range 保存时间戳，也避免扫描全部缓存 range。高水位时，释放线程可以同步执行回收，并提前唤醒回收线程，以免回收线程因 oversubscription 长时间得不到调度。

### Non-blocking 接口

每个 size class 先使用有界并发 bitmap。bitmap 不可用时才访问带锁的无界链表；如果拿不到锁，allocation 改从更大 range 拆分，free 则把 range 放入 deferred singly linked list，由后续操作或回收线程补偿完成。设计将少量内存浪费和额外工作换成不阻塞。backend 的 Nest 与 Knit 之间采用带 rollback 的 staged ownership transfer，失败时有限重试并回退到更大 range。

### 验证

作者使用 VSync 在 weak memory model 下进行 bounded model checking，分别验证 frontend、midend 和 backend，再用组合 client 覆盖 cross-thread free、线程销毁、deferred release 和树操作。验证检查 memory safety、data race 和 loop termination。它在开发期间发现了 closed sibling tree 根节点路径中的越界读取 bug。验证结论只在测试线程数、API 调用次数和缩小后的常数边界内完整成立，不能等价于整个生产配置的无界证明。

## 设计取舍

- **内存重用换取 size class 复杂度**：统一 slab 和 closed sibling tree 减少重格式化，但 size class、拆分、合并和 ownership transfer 更复杂，增加实现和验证成本。
- **非阻塞换取额外内存与工作**：锁失败时可能从更大 range 拆分，或延迟 free；这降低尾延迟，却可能临时扩大 footprint，并使 deferred list 的排空成为新的后台压力。
- **寿命预测换取回收及时性**：双缓冲利用寿命规律改善合并，但时间间隔和 watermark 需要配置。寿命分布变化时，回收可能偏早或偏晚。
- **移动端专用参数换取通用性损失**：4KB slab、2KB/16KB midend 边界、16KB/4MB backend 范围来自观测到的移动 workload；服务器或不同 page size、内存拓扑下的效果需要重新测量。

## 实验与结果

- 在 x86 微基准中，jwmalloc 平均比 jemalloc 快 74%，allocator-side instruction 减少约 82%。在 rptest-8B-128B-1 上，相比 jemalloc、mimalloc、tcmalloc 分别快 25%、24%、10%（图 12）。
- 在包含 2 秒前后台间隔的 mstress-10N 中，jwmalloc 峰值/稳态 footprint 为 906MB/29MB，jemalloc 为 968MB/376MB（图 13）。这支持其 aggressive reclamation 和可回收元数据的设计。
- 在重 oversubscription 的 mstress-10N 中，jwmalloc P99.99 allocator 操作延迟为 1.5µs，最佳竞争者为 5.9µs（图 14）。但在接近 4KB 的请求和 10N 线程配置下，jwmalloc 也出现性能回退。
- 在 Huawei Mate 70 Pro、HarmonyOS 5.1、12GB RAM 的约两小时真实场景中，每个 benchmark 重复 5 次。相比 jemalloc，jwmalloc 整机指令数少 10%，用户态 allocator 相关指令少 3.84×，CPU cluster 功耗低 5–11%，LPDDR 功耗低 2–3%（表 3、图 15）。
- 论文报告 jwmalloc 已部署到 1200 万台商业移动设备，累计稳定运行超过 300 亿用户小时；该生产数据证明了部署稳定性，但没有给出故障率、版本迁移、设备型号分布或线上 workload 分解。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 移动 workload 中 allocator 开销足以成为整机优化目标 | Android/HarmonyOS 指令占比 8.2%/12.4%；图 1 | 论文选取的真实移动 workload，未覆盖所有应用 | 强 |
| 统一 slab 与 size-class-exact backend 降低 CPU 和 footprint | 图 12、图 13；mstress、rptest、xmalloc | 合成 workload；服务器微基准与手机真实场景硬件不同 | 中高 |
| lifetime-aware reclamation 改善前后台峰谷场景 | mstress-10N：906MB/29MB 对比 jemalloc 968MB/376MB；图 13 | 2 秒 sleep 是前后台行为的代理，不是完整生产 trace | 中高 |
| non-blocking 设计改善过量订阅下的尾延迟 | mstress-10N P99.99 为 1.5µs 对比 5.9µs；图 14 | 未报告最坏 footprint、deferred list 长度和公平性 | 中 |
| 实现具备足够生产稳定性 | 1200 万设备、300 亿用户小时 | 缺少线上错误率和对照版本统计；形式验证有边界 | 中 |

## 批判性分析

### 论证链条

论文的主链条基本闭合：移动测量显示 size class 重格式化、峰谷内存和线程过量订阅；对应设计分别减少 range churn、及时释放内存并避免锁阻塞；微基准和 Mate 70 Pro 结果覆盖指令、footprint、尾延迟和功耗。frontend/backend 的组合实验（jw+jemalloc）也帮助区分了两部分收益。

仍有两个跳步。第一，生产部署数字没有配套线上基线和错误率，无法单凭它量化 jwmalloc 相对 jemalloc 的长期可靠性。第二，论文将 generational hypothesis 外推到不同移动应用，但主要寿命图和回收结果来自有限 workload；对寿命分布突变、跨应用共享内存和极端压力的覆盖不足。

### 假设压力测试

size-class-exact range 管理假设内部碎片上限和重格式化收益之间的平衡适合移动请求分布。若大对象比例上升，resolution-3 的 25% 最坏 roundup 成本可能变得重要。统一 4KB slab 对接近 page size 的对象已出现回退，说明该设计并非在所有 size 区间都占优。

non-blocking 接口把同步等待改成内存和工作开销。论文报告了 P99.99 延迟，却没有给出锁持续失败时的 footprint 上界、deferred list drain 的饥饿行为以及高优先级线程是否可能反复触发昂贵 fallback。该缺口对软实时系统仍然重要。

### 实验可信度

基线包括 jemalloc、mimalloc 和 tcmalloc，且使用默认配置；但 allocator 调优空间、编译器配置和系统集成差异可能影响比较。微基准覆盖 thread-local、cross-thread free、对象寿命和线程创建，能对应设计目标，但不能代表完整手机应用。真实设备实验使用单一旗舰机型、单一 HarmonyOS 版本和五次重复，PSS 采样每分钟一次，难以观察短暂峰值和 P99 尾延迟。

### 系统性缺陷

closed sibling tree、metadata shifting 和 rollback 协议增加了维护难度。形式验证发现过根节点越界 bug，说明该复杂度不是理论风险。论文没有讨论升级兼容、崩溃后的 heap 恢复、诊断工具、调试 allocator 以及多进程共享内存接口。它也没有将 jwmalloc 与 Scudo、PartitionAlloc 或 MTE 组合评测，因此“verified”应理解为并发实现的有界模型验证，不是完整的客户端内存安全保证。

## 局限与后续工作

- **局限 1**：评测主要覆盖一台 Mate 70 Pro 和有限的 HarmonyOS 场景；不同 ARM 核心组合、page size、应用类型和内存压力下的结果未验证。
- **局限 2**：回收时间间隔、watermark、size class 和 2KB/16KB/4MB 分界依赖移动 workload，论文没有给出在线自适应或跨设备配置方法。
- **局限 3**：bounded verification 只覆盖缩小后的配置和专门构造的 client，不能证明生产规模下所有交错都安全。
- **后续工作 1**：在真实前后台 trace 上记录寿命 knee point、cached range 数量、deferred list 长度和 page fault，验证双缓冲参数是否需要按应用自适应。
- **后续工作 2**：测量连续锁失败下的内存上界、回收公平性和高优先级线程延迟，给 non-blocking fallback 建立可操作的软实时保证。
- **后续工作 3**：把 closed sibling tree 扩展到服务器环境，并在 NUMA、多 socket 和大页配置下比较 range churn、内存碎片与 metadata 成本；论文已将此列为未来方向。

## 相关

- **相关概念**：slab allocator、buddy allocator、weak memory model、bounded model checking、generational reclamation
- **同类系统**：jemalloc、mimalloc、tcmalloc、Scudo
- **同会议**：OSDI 2026
