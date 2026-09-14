---
type: paper
name: Ichnaea
full_title: Ichnaea: A Framework for Precise Tracking of Memory Objects
authors: [Samad Haque, Sibin Mohan, Aaron Paulos, Partha Pal]
venue: OSDI
year: 2026
tags: [memory-tracing, mpk, dynamic-analysis, debugging, fuzzing]
source_pdf: "[[osdi26-haque.pdf]]"
source_md: "[[osdi26-haque]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Ichnaea：精确追踪内存对象的框架（OSDI 2026）

> **原题**：Ichnaea: A Framework for Precise Tracking of Memory Objects

> **一句话总结**：现有动态追踪要么遍历几乎所有 load/store、带来 10–100× 慢化，要么受页粒度和跨线程权限影响而丢事件；Ichnaea 用 MPK 在访问目标对象时触发 SIGSEGV，仅对目标事件做指令模拟和上下文记录，在 SPECInt 中通常维持约 1–3×运行时间，并比 Intel Pin 快 12–60×，但依赖显式标注、非栈对象和有限的 syscall/指令覆盖。

## 问题与动机

调试内存破坏、并发错误和数据驱动控制流时，研究者需要知道哪个线程、哪条调用链在何时读写了哪个对象。静态分析难以覆盖指针别名、间接调用和输入相关路径；Pin、Valgrind 等动态二进制插桩则需要检查大量指令，开销过高。基于 `mprotect` 的方案虽然只在目标页访问时介入，却会因页粒度、全局页权限和解锁窗口在多线程程序中丢失事件。

Ichnaea 将目标定义为 ObjOfInterest，并用 MPK（Memory Protection Keys）把其所在页设为当前线程不可访问。访问触发处理器，处理器记录访问者、指令位置、调用栈、时间戳以及写入前后的数据，再恢复程序执行。

## 关键观察 / 隐含假设

- **观察 1：目标对象通常只占程序访问的一小部分。** 因此让追踪器在目标访问前保持休眠，比对每个 load/store 做过滤更合适；SPECInt 对比中 Ichnaea 通常为原生运行时间的 1–3×，Pin 为 12–86×（图 4）。
  - **依赖假设**：用户能预先选出少量目标对象。
  - **可能失效场景**：若追踪对象数量或访问频率接近全体内存访问，逐次 fault、栈展开和日志成本会超过插桩方案；论文也明确指出全对象追踪可能失去优势。
- **观察 2：传统页保护的解锁窗口会造成跨线程丢失。** `mprotect` 改变的是全局页表权限；一个线程解锁页面时，其他线程可能无 fault 地访问同页对象。MPK 权限则是线程本地的（§2.2、§4.2）。
  - **证据强度**：强。论文给出 syscall、false sharing 和 atomic object 三类具体丢失机制，并以 PostgreSQL 回归测试验证并发场景（表 3）。
- **假设 1：目标对象可以通过源码标注可靠识别，且不需要追踪栈对象。** 标注错误会产生错误轨迹；栈对象未被原型支持（§4.4、§6）。
  - **证据强度**：强。该限制直接写入使用模型和讨论部分。

## 核心方法

Ichnaea 以共享库 `libichnaea.so` 运行，通过轻量 API 注册地址、大小、名称和类型。全局对象可放入专用 ELF section；指向堆对象的指针可用标注配合 malloc/calloc/realloc 拦截自动识别。堆 ObjOfInterest 默认各占一个页，以避免无关对象因页保护而产生 collateral fault（§3.2、§4.5）。

注册后，`pkey_mprotect` 将目标页绑定到一个 pkey，当前线程用 `pkey_set` 禁止访问。SIGSEGV handler 临时放开该线程的权限，模拟可支持的 faulting instruction，写入事件缓冲区，并前移 RIP；返回信号处理器时权限恢复为锁定状态（图 3）。MPK 的线程本地性回应了观察 2，也避免了反复 `mprotect` 的页表更新和 TLB shootdown。

内核向用户缓冲区写入时不会触发用户态 fault。Ichnaea 因而包装部分 libc syscall，在调用前临时放开相关页面，调用后比较对象状态或哈希并恢复保护。该机制覆盖常见的 `read`、`recv*`、`ioctl` 等路径，但无法可靠解析所有变长参数、inline syscall 和 VDSO 路径（§4.3）。

事件在专用内存池中积累，进程退出时序列化为 JSON，包含 PID/TID、RIP、调用栈、访问类型、时间戳、访问计数器及写入数据。原型不到 2000 行 C 代码，不修改内核。

## 设计取舍

- **MPK 与页粒度之间的取舍**：MPK 消除了跨线程解锁造成的丢失，却不能消除页粒度；同页无关对象仍会进入 handler。全局对象隔离可减少 collateral fault，但需要额外布局约束。
- **页级堆隔离与内存占用的取舍**：10,000 个小对象的 RSS 从约 4.2 MiB 增至约 80 MiB，单次分配时间增加 7.6×（表 4）。这适合离线分析，不适合作为常驻部署的默认内存策略。
- **用户态 syscall wrapper 与覆盖率的取舍**：避免内核模块和特权，但 syscall 参数解析不完整；无法解析的对象读可能被漏记。

## 实验与结果

- 在 Xeon Silver 4316、Ubuntu 24.04.2、64 GiB 内存上，SPEC CPU 2017 的 Ichnaea 相比 Intel Pin 快 12–60×；自身通常为原生运行时间的 1–3×，xalan 因高频全局变量访问达到 4.8×（图 4）。
- 相同实现改用 `mprotect` 的版本慢 1.3–7×，说明 MPK 的用户态权限切换避免了页表修改和跨核 TLB 刷新（§5.3.2）。
- PostgreSQL 高并发回归测试中，Ichnaea 比 Intel Pin 快 26×；Ichnaea 的 kernel-mode 时间为 11.2 s，Pin 为 10.4 s（表 3）。
- 合成负载追踪 2–100 个对象时，每增加 20 个对象约增加 8–10%运行时间；高压配置下单次目标访问中位数约 15 µs（图 5）。
- AFL++ 模糊测试在 25 分钟内覆盖并记录 17/17 条目标访问路径；原生版本约 5 分钟完成覆盖，Pin 超过 12 小时仍未到达目标路径（表 6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| MPK 版本比 `mprotect` 版本更适合并发对象追踪 | §2.1.3、§5.3.2，速度提升 1.3–7× | 单机 Intel Xeon；改造版 tracer | 强 |
| Ichnaea 比 Pin 更适合低目标密度的动态追踪 | 图 4，SPECInt 中快 12–60× | CPU 密集型 SPECInt，目标对象由作者选择 | 强 |
| 目标访问可用于模糊测试中的精确记录 | 表 6，17/17 路径被记录 | 自定义、内存访问密集型 fuzz target | 中 |
| 方法能覆盖所有访问来源 | §4.3、§6 同时承认 syscall 读、栈对象和部分指令存在缺口 | libc wrapper 与当前原型实现范围 | 弱 |

## 批判性分析

### 论证链条

“目标访问稀疏”这一观察支持 fault-driven 设计，MPK 的线程本地权限也确实回应了传统 `mprotect` 的并发丢失问题。实验同时显示了代价：目标访问频繁时 fault 处理和栈展开达到微秒级，xalan 的结果说明页共享会放大开销。论文对“低开销”的结论应限定为少量、预选、非栈对象，而非一般性的全内存追踪。

### 假设压力测试

方法依赖 MPK 硬件和内核支持；不同架构、虚拟机或云环境的 fault/权限切换成本可能改变结果。每个堆对象独占页的策略在小对象数量达到 10³–10⁴ 时会产生线性内存放大。高并发虽避免了传统解锁窗口，但 handler、日志池和栈展开仍会竞争 CPU。论文未用生产 trace 验证目标选择是否稳定，也未证明 syscall wrapper 能覆盖真实程序中所有绕过 libc 的路径。

### 实验可信度

Pin 和 `mprotect` 对照覆盖了速度、并发和 fuzzing；合成对象扩展实验也报告了平均值、中位数和 P99。限制在于 workload 主要是 SPEC CPU 和自定义 fuzz target，缺少大规模网络服务、不同 MPK 支持架构以及更强的 tracing 基线。覆盖性结论部分来自设计分析，而不是对所有 syscall、指令和库路径的穷举测试。

### 系统性缺陷

指令模拟器尚未覆盖浮点写入等复杂指令，慢路径会直接执行 CPU 指令。handler 中 `libunwind` 带来约 6 µs 的可避免成本（表 5）。错误标注可能产生不正确轨迹；程序退出前的崩溃、信号嵌套、线程创建和异常处理行为在论文中没有充分讨论。JSON 后处理保留了丰富上下文，但运行期日志缓冲区的峰值内存和溢出策略未被量化。

## 局限与后续工作

- **局限 1**：栈对象不适合当前页保护模型；原型不追踪它们。
- **局限 2**：syscall 参数解析、inline syscall/VDSO 和指令模拟覆盖不完整，尤其是对象读可能漏记。
- **局限 3**：堆对象按页隔离造成约 8 KiB/对象的物理内存成本（表 4）。
- **后续工作 1**：实现面向 ObjOfInterest 的子分配器，在保持隔离区域的同时将多个小对象打包，并测量 10³–10⁴ 对象下的 RSS、分配延迟和事件完整性。
- **后续工作 2**：在真实 PostgreSQL/nginx trace 上系统枚举 syscall、指令和线程生命周期路径，给出按访问类型划分的漏记率，而非只报告设计上的覆盖声明。

## 相关

- **相关概念**：[[Memory Protection Keys]]、[[Dynamic Binary Instrumentation]]、[[Fuzzing]]
- **同类系统**：[[Intel Pin]]、[[Dthreads]]
- **同会议**：[[OSDI-2026]]
