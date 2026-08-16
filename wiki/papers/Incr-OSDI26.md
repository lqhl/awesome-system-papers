---
type: paper
name: Incr
full_title: "Incr: Faster Re-execution via Bolt-on Incrementalization"
authors: [Yizheng Xie, Evangelos Lamprou, Jerry Xia, Nikos Vasilakis]
venue: OSDI
year: 2026
tags: [shell, incremental-computing, memoization, dependency-tracking, sandboxing]
source_pdf: "[[osdi26-xie-yizheng.pdf]]"
source_md: "[[osdi26-xie-yizheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 以外挂增量化加速程序重执行（OSDI 2026）

> **原题**：Incr: Faster Re-execution via Bolt-on Incrementalization

> **一句话总结**：INCR 利用每个 shell command 的系统调用、环境和隔离文件系统自动推断依赖，再重放缓存的 stream、退出码和文件副作用；14 个开发场景的 85 次修改中有 69 次获得加速，这 69 次平均快 34.2 倍、最高 373.3 倍，但另外 16 次反而变慢，首次执行平均约为 Bash 的 2.01 倍，说明收益依赖“昂贵且大部分未变”的重复计算。

## 问题与动机

软件开发通常只改一小部分代码或数据，但 shell script 会把一串不透明、甚至跨语言的 command 从头再跑。Build system 和数据流系统通常要求开发者声明依赖，notebook 也要用户判断哪些 cell 应重跑；普通 Bash pipeline 既没有显式依赖图，又允许 command 读写文件、环境变量、pipe、网络和其他外部状态，简单地按命令字符串做 [[Memoization|记忆化]] 很容易复用过期结果。

论文的层次更难：INCR 不只缓存纯函数输出，还要处理非幂等副作用。例如 `tee -a`、文件删除或目录移动若被直接跳过，新的文件系统不会得到与原执行相同的变化；pipeline 中的 stdout 又是短暂 stream，不能只靠最终文件恢复。系统因此必须同时知道 command 读了什么、写了什么，以及复用时应重放哪些效果。

INCR 面向开发和调试期：用户用 `incr script.sh` 启用，准备部署时再恢复普通 shell。目标是不给原 script 加 annotation、不修改 command 实现，以较贵的首次分析换后续修改后的快速重执行。它不是生产常驻执行器，也不声称覆盖所有 Linux 可观察行为。

## 关键观察 / 隐含假设

- **观察 1：shell command 虽然语义不透明，但大量依赖最终会表现为系统调用、stream 和文件系统效果。** INCR 在 command 边界插入 probe，用 file-related syscall、stdin、环境快照和 OverlayFS upper layer 恢复依赖与副作用（图 3、§4）。
  - **依赖假设**：会影响结果的状态必须落在 INCR 能观察、隔离或保守禁用复用的 effect class 中。
  - **可能失效场景**：RDRAND、时间敏感 loop、kernel module、共享内存、外部 database 或未启用 `-N` 时的 network/clock/entropy，可能绕过默认模型。
- **观察 2：写入内容相同，不一定需要让下游重跑。** INCR 对 write dependency 比较 content hash，而不是只看“上游运行过”；对 read dependency 用较便宜的 modification timestamp。这能让输入改变但输出不变的 command 保留下游缓存（§5）。
  - **依赖假设**：文件内容、mtime、调用参数、环境和 stdin hash 足以代表 command 的有效输入；非文件外部状态另行处理。
  - **证据强度**：中。真实 workload 显示了收益，但论文没有分别量化 hash/mtime 策略的误判率。
- **观察 3：pipeline 可以先流式执行，再在确认可复用时停止。** Eager stream processing 一边转发和 hash stdin，一边让 command 开始；若稍后确认依赖不变，就 kill 新执行并丢弃隔离 upperdir，再续播旧结果（§6）。
  - **依赖假设**：被提前终止的外部效果均被隔离，否则已经发出的不可回滚效果无法撤销。
  - **可能失效场景**：跨 sandbox 通信、发给外部进程的 signal、后台 daemon 或网络写入不能靠丢弃 upperdir 回滚。
- **假设 1：首次分析与缓存空间可由多次重跑摊销。** 85 次修改中，长计算和大部分 pipeline 未变化时收益很大；许多短 command 必须重跑时，固定 tracing 成本反而占主导（图 4–5）。
  - **证据强度**：强。论文同时报告了 69 次加速与 16 次减速，而不是只给最高值。

## 核心方法

INCR 先用 libbash 解析 script AST，在可跟踪的外部 command 前插入高阶 probe，例如把 `rm $path` 变成 `probe rm $path`。Shell builtin、function、alias 和 background command 不直接 probe；redirection 则改写成 `dd` 后再跟踪。Probe 覆盖该 command 创建的 subprocess，所以 `xargs` 默认作为一个整体处理，而不是自动拆到每个子任务（§4）。

每个 probe 在 try semisolate 中运行 command：为顶层目录建立私有 [[OverlayFS]]，lower layer 只读，upper layer 收集写入；user、mount、PID namespace 隔离跨进程效果。INCR 用 seccomp-BPF 过滤无关 syscall，只 tracing `fork`、`exec` 和 `strace %file` 集合；command 结束后扫描 upperdir，再把改变提交到真实文件系统。环境变量和 shell function declaration 以快照方式记录。因为无法知道 command 实际读了哪个环境变量，它保守地把全部变量作为依赖，只对 Debian/Ubuntu 已知 session/TTY 噪声做过滤。

缓存索引包含 command 参数、环境和 stdin stream hash。Read dependency 以 mtime 检查，write dependency 以 content hash 检查；stdout、stderr、exit status 与 OverlayFS upperdir 一并保存。重执行时，依赖变化就正常运行并更新缓存；依赖不变就跳过 command，重放 stream 和退出码，并依照 upperdir 中的普通文件、whiteout、opaque directory 等记录重新应用创建、修改和删除（§5）。这正是非幂等文件效果也能复用的关键。

论文把效果明确分成五类（表 1）：可精确 memoize 的本地文件与 stream；可观察但不能重放、因而应重跑的效果；被 sandbox 阻止的跨边界效果；prototype 忽略的系统状态、POSIX IPC 等；以及时间敏感、非终止、不可观察随机性等范围外行为。`-N` 会额外观察 clock、network 和 entropy syscall，并对相应 command 禁用复用；默认不开时，外部网络变化不一定触发重新执行。

三个运行时优化控制成本。Eager stream processing 保留 shell pipeline 的流式并行；introspection 根据历史把无文件写入的 command 暂时视为 effect-free，若后来检测到写入则撤销标签并失效缓存；可选 Zstandard compaction 压缩缓存，但默认关闭。另有非必需 annotation：`stateless` 支持 content-defined chunk 的局部重算，`pure` 可跳过 tracing/isolation，argument-independent 可把多文件调用拆开；开发者也可主动关闭某段增量化或把多个小 command 合为一个缓存单元（§6–§7）。

## 设计取舍

- **系统级 observation 换语言无关性**：无需理解 Python、awk、ffmpeg 等内部语义，但 syscall 看不到的依赖只能保守处理、忽略或排除。
- **每 command 隔离换副作用可重放**：OverlayFS 和 namespace 让中途 kill 与非幂等写入更安全，却带来 mount、trace、copy 和 commit 成本，也会阻止合法的跨 command 并发共享。
- **mtime 追踪 read、hash 追踪 write**：降低大量动态 library 读取的成本，但依赖文件系统 timestamp 语义；论文没有讨论粗粒度 mtime 或外部绕过缓存更新的极端情况。
- **默认方便换严格性**：不要求 annotation，也不默认启用 `-N`；因此开箱即用的覆盖面更广，但涉及网络、时间或随机性的 script 必须由用户识别风险。
- **存空间换反馈速度**：完整保存每个 command 的 stream 和 upperdir，能精确重放，却让 cache 平均达到输入的 6.05 倍、最坏 55.44 倍。
- **边界条件**：计算昂贵、修改局部、环境稳定、效果以本地文件和 pipe 为主时最适合；大量毫秒级 command、外部事务、daemon 和强并发 IPC 不适合。

## 实验与结果

- **设置与 workload**：评测含 14 个 Koala/新增 shell 开发场景、共 85 个 code/data delta，覆盖数据处理、ML、系统管理与 [[LLM|LLM]] 辅助修改，输入从数十 MB 到 3.5 GB。部分修改来自开发者或 Git history，部分由作者按真实开发轨迹手工构造。机器为 CloudLab m510：8-core Intel Xeon D-1548 2.0 GHz、64 GB RAM、256 GB [[NVMe|NVMe]]、Ubuntu 22.04/Linux 5.15；每次重执行跑 3 次取平均（§8）。
- **重执行收益与反例**：相对 Bash 全量重跑，85 次中 69 次加速；只在这 69 次中，平均 speedup 为 34.2 倍、最高 373.3 倍。另 16 次的 `Bash time / INCR time` 平均仅 0.73、最差 0.15，即 INCR 明显更慢。Unixgame 的一个反例从 107.8 秒增到 123.6 秒，原因是修改后仍需跑八个短 command（图 4、§8.1）。
- **代表性收益**：Hieroglyph `dpt` 的四轮修改总时间从 1 小时 25 分降到 20 分 41 秒，整体快 4.1 倍；其中扩充输入与新增可视化两轮分别快 91.2 和 119 倍。Image benchmark 复用 GPT-4o mini 标注时从 155.55 秒降到 1.62 秒，快 96.02 倍（§2、§8.1）。
- **首次运行与空间**：对 INCR 运行超过 5 秒的 benchmark，首次执行相对 Bash 平均为 2.01 倍，最坏 music 为 8.32 倍；cache 平均是原输入的 6.05 倍，最坏比例是 music 的 55.44 倍（绝对值 0.87 GB），最大绝对 cache 是 spell 的 3.6 GB（图 5、§8.2）。
- **行为一致性**：14 个场景与未修改 Koala benchmark 的最终输出/exit code 均与 Bash 一致。Bash 5.2.37 suite 有 534 个 test file、22,064 LoC 和 10,282 条 ground-truth output line；INCR 匹配 10,279 条（99.9%），3 条差异来自 recursive alias 与清空 `PATH`，另有 19 个 parser-error case 按范围排除（表 3、§8.3）。这里的 10,282 是输出行数，不是 10,282 个独立测试。
- **优化与 annotation**：16-stage streaming pipeline 首轮从关闭 eager processing 的 9 分 50 秒降到 3 分 22 秒，减少 65.8%；compaction 平均省 55.7% cache，平均 speedup 只下降 1.9%，但最坏下降 9.8%。可选 annotation 在真实 benchmark 上额外带来平均 1.46 倍、最高 24.40 倍提升，并把首次运行平均 overhead 从 101.05% 降到 43.55%（图 6、§8.4–§8.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 无需改 script 的系统级增量化能大幅缩短部分重执行 | 图 4、§8.1 | 14 个 shell 场景、85 次修改；Bash 全量重跑基线 | 强 |
| 收益取决于可复用工作是否覆盖 tracing 固定成本 | 图 4–5 | 69 次加速、16 次减速；单台 8-core 机器 | 强 |
| 文件与 stream 副作用可以被隔离并安全重放 | 图 3、§4–§5 | 本地文件系统、标准 stream 与论文列出的 memoizable effect | 中 |
| prototype 广泛兼容 Bash 行为 | 表 3、§8.3 | 10,282 条 suite output line；3 条差异；19 parser-error case 排除 | 强 |
| 优化能显著降低 tracing/storage 成本 | 图 6、§8.4–§8.5 | 合成 pipeline 消融与 14 个 benchmark annotation 实验 | 中 |

## 批判性分析

### 论证链条

论文从 shell 的隐式依赖和任意副作用出发，把问题拆为 runtime dependency tracking、effect memoization/replay 与成本优化，再分别用真实修改、Bash suite 和消融验证，链条完整。最容易被摘要遮住的是“平均 34.2 倍”的条件：它只对 69 个加速 case 取平均，16 个 slowdown 没进入这个数。另一个需要收窄的词是 behavioral equivalence；论文提供很强的兼容性证据，但表 1 主动列出 ignored 与 out-of-scope 行为，不能理解成所有 shell/Linux 程序的语义等价保证。

### 假设压力测试

INCR 假设运行环境“大体不变”，变化能由文件、stdin、参数和环境捕获。默认不启用 `-N` 时，`wget`、clock 或 randomness 可能被错误复用；启用后又会让相关 command 每次重跑，降低收益。POSIX shared memory、semaphore、hostname、scheduler state 等 prototype 忽略的状态也会产生 stale output。Command 通过 database、远程 API、GPU driver 或自定义 ioctl 改变外部世界时，OverlayFS 无法回滚。大量 shell builtin、alias、background task 与跨 probe pipeline 共享状态同样会削弱跟踪粒度或直接被隔离阻止。

### 实验可信度

85 次修改、14 个不同领域 workload、Bash 官方 suite 和对首轮/空间开销的诚实报告很有说服力。不过性能只在一台 8-core 老款 Xeon 上与 Bash 全量执行比较，没有和手工 checkpoint、build system 或领域增量系统比较。五个场景的修改由作者构造，可能偏向可复用模式；评测也没有给出长时间真实开发 session 中 cache hit、cache 清理与总节省时间。Bash suite 主要测 parser/runtime 输出兼容性，不等于穷尽外部副作用、crash 或并发正确性。

### 系统性缺陷

系统依赖 OverlayFS、user/mount/PID namespace 和 syscall tracing，受容器、权限、文件系统与发行版配置限制；噪声环境变量过滤目前只覆盖 Debian/Ubuntu。Cache 会复制 stdout、stderr 和文件内容，可能保存 secret 或个人数据，论文未讨论加密、访问控制、配额与安全删除。把 upperdir 变化提交回真实文件系统不是数据库事务，论文也未说明 crash 中途的原子性、并发进程同时改文件时的隔离，以及 cache corruption 的恢复。开发者必须正确识别何时加 `-N` 或禁用增量化，这把部分 correctness 责任留给了用户。

## 局限与后续工作

- **局限 1**：正确复用只覆盖明确的 effect model；network、clock、entropy、IPC、daemon、kernel state 和隐藏硬件随机性不是默认安全范围。
- **局限 2**：首次执行与 cache 成本很高，85 次中仍有 16 次减速；系统没有自动预测“这段是否值得 incrementalize”的 cost model。
- **局限 3**：行为测试仍有 alias/`PATH` 三条差异，且 19 个 parser-error case 被排除。
- **后续工作 1**：构造包含数据库事务、HTTP API、shared memory、signal 和 crash 的 effect suite，逐类报告漏检、保守重跑与错误复用率。
- **后续工作 2**：根据历史 command time、effect size 和修改频率自动决定 probe、group、compress 或 bypass，并在真实开发 session 上优化累计 wall time。
- **后续工作 3**：为 cache 增加内容加密、per-project quota、引用计数与可审计清理，并验证 crash-consistent commit/replay。
- **后续工作 4**：延迟 alias 展开后的 probe placement、把 runtime 打成 standalone binary，并重新跑完整 Bash parser-error 集合。

## 相关

- **相关概念**：[[Incremental-Computation]]、[[Memoization]]、[[Dynamic-Dependency-Tracking]]、[[Execution-Tracing]]、[[Sandboxing]]
- **相关机制**：[[OverlayFS]]、[[Content-Defined-Chunking]]、[[Bash]]
- **同类系统**：[[PaSh]]、[[POSH]]、[[Nix]]
- **同会议**：[[OSDI-2026]]
