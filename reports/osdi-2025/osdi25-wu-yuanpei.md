# OS Rendering Service Made Parallel with Out-of-Order Execution and In-Order Commit

**作者**：Yuanpei Wu, Dong Du（上海交通大学 IPADS，教育部领域专用操作系统工程研究中心）；Chao Xu, Ming Fu（华为中央软件院 Fields Lab）；Yubin Xia, Yang Yu, Binyu Zang, Haibo Chen（上海交通大学 IPADS）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），2025 年 7 月 7–9 日，波士顿
**DOI**：https://www.usenix.org/conference/osdi25/presentation/wu-yuanpei
**源文件**：[osdi25-wu-yuanpei.pdf](../../papers/osdi-2025/osdi25-wu-yuanpei.pdf)

---

## 一、背景

OS 渲染服务（Rendering Service）是 Android、iOS、OpenHarmony 等智能设备操作系统的核心服务之一，负责将应用描述的 GUI 元素逐像素写入帧缓冲。渲染相关任务平均占据商用智能手机 65%–95% 的 CPU 和 GPU 运行时间，是最关键的系统性能瓶颈之一。

传统渲染服务遵循**顺序模型**：维护一棵 render tree（每个节点只存储相对于父节点的相对信息），由 2D 绘制引擎（如 Skia、Impeller）深度优先遍历，将 draw command 翻译为 GPU 对象（mesh、texture、pipeline 等），最终提交 GPU 执行光栅化。整个流程 CPU 占端到端渲染时间的 82%，GPU 执行时间完全被 CPU 流程覆盖。

近年来，折叠屏手机（双折/三折）和"一芯多屏"车载智能座舱的兴起，使渲染负载急剧上升。以华为 Mate XT（三折屏）为例，需渲染的像素数比单屏机型多 117%，而 SoC 算力相近。智能座舱单芯片需同时驱动 2–6 块 2K 分辨率屏幕，当前方案只能在 45–60Hz 下运行。

---

## 二、要解决的问题

**核心问题**：现有顺序渲染服务无法充分利用多核 SoC，在可扩展显示场景下帧率严重不足。

在实际测量中（OpenHarmony 5.0，Mate X5），渲染线程独占单核 80% 的利用率，而其余 9 个核心（共 12 核）几乎处于空闲状态。并行化面临三个核心挑战：

- **C1 状态依赖（State Dependency）**：render tree 每个节点只含相对信息，正确的绝对状态需要通过深度优先遍历顺序累积，无法直接并行各节点的渲染。
- **C2 绘制顺序依赖（Drawing Order Dependency）**：前后景覆盖关系（z-order）要求图形基元必须按特定顺序提交给 GPU，乱序执行会导致画面错误。
- **C3 接口依赖（Interface Dependency）**：传统 2D 引擎（Skia Canvas、Drawing API）提供有状态接口，新命令依赖历史状态；基于状态的 command batching 优化同样需要顺序保证。

现有方案（帧间并行 inter-frame parallelism、多窗口并行 multi-window parallelism、D-VSync）均存在并行粒度粗、无法应对持续高负载等局限。

---

## 三、核心设计

论文提出 **Spars**，一个受计算机体系结构中**乱序执行 + 顺序提交**（Out-of-Order Execution with In-Order Commit）启发的可扩展并行 OS 渲染服务，底层依托全新绘制引擎 **Spade2D**。

核心洞察：渲染任务与处理器指令类似——依赖关系不等于必须顺序执行，只要在**输入侧**解开状态依赖、在**输出侧**维护绘制顺序，大部分任务可以并行执行。测量表明，76% 的端到端渲染工作量是可并行化的。

**三阶段渲染流程**（对应三种线程）：

1. **顺序准备（In-Order Preparation，主线程）**：对 render tree 做一次快速"干跑"（dry run）——不调用 2D 引擎做实际渲染，只计算每个节点的绝对状态（transform matrix、clipping 等），打包为**自包含渲染任务（Self-Contained Rendering Task）**。同时计算各任务的轴对齐包围盒（AABB），记录任务间的**覆盖关系（Overlapping Relations）**。此阶段也执行 command batching 优化。

2. **乱序执行（Out-of-Order Execution，工作线程池）**：多个工作线程从 SPMC（Single-Producer Multi-Consumer）任务池取任务，调用 Spade2D 无状态接口，将自包含任务翻译为 GPU 对象。任务间无状态依赖，可任意顺序、任意核心并行执行。结果放入 MPSC（Multi-Producer Single-Consumer）资源池。

3. **顺序提交（In-Order Commit，提交线程）**：提交线程从 MPSC 池收取完成的任务，基于覆盖关系（任务链 + AABB 检查）判断当前任务能否安全提交到 GPU command。若所有在其之前的任务均已提交，或其 AABB 与未完成的前置任务不重叠，则可立即提交；否则等待。最终提交给 GPU 执行光栅化。

**API 解耦**：对上层应用保留有状态接口（Spars 的 Drawing API 层），对底层渲染引擎提供无状态接口（Spade2D），两者通过顺序准备阶段的干跑解耦，既保持兼容性，又实现并行化。

---

## 四、实现细节

- 语言：C++，GPU 后端采用 Vulkan（智能设备上最主流的现代图形 API）
- Spade2D 是从头实现的无状态 2D 绘制引擎，与 Skia/Impeller 等功能等价但接口不同
- GPU 资源管理：各类资源（buffer、image、pipeline、shader、descriptor 等）使用 size-class-based pool、哈希表、循环队列等线程安全数据结构；"正在准备中（preparing）"状态通过原子标记防止并行任务双重创建同一 GPU 资源，blocking 仅在极少数非 batch 任务发生竞争时出现
- 工作线程数在运行时可配置，当前实践中 3–5 个线程已足够；在配置 6 个中核的 Kirin SoC 上默认使用 5 个工作线程，保留 1 核给提交线程
- AABB 覆盖检查有预设最大次数限制（3–5 次），防止少数重任务阻塞后续提交
- 内存开销：每线程约 8MB 栈空间，绝对状态信息、自包含任务、覆盖关系合计不超过 10MB，Spars-5 总额外内存 <50MB
- 评估部署方式：Spars 作为自定义渲染服务直接调用 GPU 资源，绕过 Android/OpenHarmony 原生渲染服务，以消除系统调用层面的干扰
- 完整移植一个传统渲染服务（~200K LoC）+绘制引擎（~400K LoC）需要修改超过 1/3 的代码量

---

## 五、实验结果

**测试平台**：华为 Mate70（单屏）、MateX5（双折）、MateXT（三折）；麒麟 9010 芯片组（多屏，2–6 块 2K 屏幕）。CPU 为 4 小核 + 6 中核（3 物理核 + SMT）+ 2 大核（1 物理核）异构架构。所有对比实验固定在中核运行，时钟频率一致。

**基线**：Commercial（OpenHarmony 5.0 商用渲染服务）和 Sequential（Spars 的顺序版本，为公平对比专门构建）。

| 指标 | Spars-3 | Spars-5 |
|------|---------|---------|
| 平均帧渲染时间降低（vs Sequential） | 27.3% | 43.2% |
| 平均帧率提升（vs Sequential） | 1.38× | 1.76× |
| 最高帧率提升（多窗口/画中画） | - | 2.07× |
| 多屏平均帧率提升 | 1.34× | 1.91× |
| 6 屏桌面场景帧率提升 | - | 2.16× |
| 整机功耗降低（vs Sequential，同帧率） | 2.7% | 3.0% |
| 同帧率预算可渲染图形基元倍数 | 1.62× | 2.31× |

- 42 个测试场景在 Spars-5 下全部稳定达到 120Hz；而顺序基线有 27/42（64%）无法在折叠屏上维持流畅体验
- 最多核心利用率：Sequential 单核 80% → Spars-5 中核 45%，进一步使用 5 中核 + 3 小核异构配置可降至 37%
- 可并行化比例（out-of-order 执行 + 顺序提交）：平均 76%；in-order 准备 + GPU 提交仅占 24%
- Amdahl 定律理论上限：3 线程 2.14×，5 线程 2.65×；实测受调度和同步开销影响，低于上限

---

## 六、批判性分析

**基线选取存在重要遮蔽**。论文将"Sequential"（自行构建的顺序版本）作为主要对比基线，而非直接与 Commercial（OpenHarmony 5.0）比较。这一选择的理由是"更公平"，但也掩盖了一个重要问题：Commercial 本身包含帧间并行等优化，其帧渲染时间可能低于 Sequential。MateXT 的 Commercial 数据甚至被完全省略（footnote 2），没有解释原因，令人怀疑在三折屏这一最核心目标场景下，Commercial 的真实表现如何。

**功耗降低幅度与帧率收益不成比例**。声称 1.76× 的帧率提升，但整机功耗仅降低 3.0%。这是因为功耗测量的是"相同帧率"下的对比，但实际上在更高帧率下系统整体功耗必然上升（GPU 运行时间更长），论文对这一 trade-off 未作讨论。

**测试场景使用"哑数据"**。42 个场景的 render tree 从真实应用导出，但实际内容（图像、文字）替换为 dummy data。GPU 资源（image/pipeline）的缓存命中率在真实场景和哑数据场景下可能差异显著，影响并行化的实际收益。

**可扩展性测试刻意选取了最差 batching 条件**。论文注明图形基元可扩展性实验使用随机图形基元，"随机性使大多数 draw command batching 无法发生"——这不反映真实应用的 batching 比例，使得 Spars 并行化的相对优势被高估。

**在部署方式上与真实系统存在差距**。Spars 绕过了 OpenHarmony/Android 的原生渲染服务直接调用 GPU，这在真实 OEM 产品化时需要完整替换渲染服务和 2D 引擎，作者也承认需要重写 >1/3 代码量（传统约 60 万行）。论文对这个工程挑战一笔带过，称"已在华为商用产品中部署"但没有给出完整商用系统的对比数据。

**Overlapping relation 计算的正确性边界未充分讨论**。AABB 检查有最大次数限制（3–5 次），在极端情况下（大量高度重叠的任务）可能退化为顺序等待，但论文未给出此类极端场景的性能数据或理论下界分析。

---

## 七、总结

Spars 将计算机体系结构中乱序执行 + 顺序提交的经典思想成功迁移到 OS GUI 渲染领域：通过"干跑"解开状态依赖形成自包含任务、通过 AABB 覆盖关系在提交阶段维护绘制顺序、通过有状态/无状态 API 双层解耦保持接口兼容性，在 Huawei 折叠屏和多屏设备上实现了 1.76×–1.91× 的帧率提升。该方案适用于 CPU 渲染负载重、多核利用率低的 2D GUI 渲染场景（Android、iOS、OpenHarmony 类操作系统），对折叠屏和多屏方向有明确的商业价值。主要局限在于：完整产品化需要大规模代码重构，测试基线选取有一定偏向性，且对真实应用 workload 特征的覆盖仍有不足。
