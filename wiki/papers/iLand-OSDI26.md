---
type: paper
name: iLand
full_title: "iLand: An Instruction-Level Dynamic Binary Instrumentation framework for iOS"
authors: [Kaitao Xie, Yizhuo Wang, Xiaolong Bai]
venue: OSDI
year: 2026
tags: [ios, dynamic-binary-instrumentation, emulation, mobile-security, program-analysis]
source_pdf: "[[osdi26-xie-kaitao.pdf]]"
source_md: "[[osdi26-xie-kaitao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# iOS 上的指令级动态二进制插桩

> **原题**：iLand: An Instruction-Level Dynamic Binary Instrumentation framework for iOS

> **一句话总结**：iLand 把 Arm64 指令提前翻译成只读微操作，再用已签名的执行单元解释，从而在无 jailbreak、禁止 JIT 的 iOS 17 上做 App 指令级追踪；代价是 SPEC 比原生慢 15–90 倍，64 个热门 App 只有 49 个功能完整，但仍足以在 60 个可用 App 中发现 13 个调用 private API、15 个直接用 syscall 读取系统信息。

## 问题与动机

动态二进制插桩（dynamic binary instrumentation，DBI）要在程序运行时观察或改写任意指令。Pin、DynamoRIO、Valgrind 一类系统通常把基本块即时编译到可写可执行的 code cache，但普通 iOS App 没有 `allow-jit` 等私有 entitlement，不能创建 RWX 内存或加载未签名代码。jailbreak 只能支持旧系统，repackaging 和 API hook 又会改动原二进制，且看不到任意指令。

直接解释整个进程也不现实。iOS 把系统库放进 Dyld Shared Cache（DSC）；论文以 iPhone 15/iOS 17 为例，设备只有 6 GB RAM，DSC 已约 3.3 GB。分析器若再为 guest 保存一份完整 DSC，容易触发 iOS 的 Jetsam。iLand 因而把问题缩成：只解释 App 自身代码，让系统库原生运行，同时在系统库回调或返回 App 时可靠地重新取得控制权。

## 关键观察 / 隐含假设

- **观察 1：禁止动态代码不等于禁止解释。** 运行前生成只读 IR，运行时只跳转到安装包中预先编译、签名且位于 RX 页的执行单元，就不需要 JIT 或 RWX 页（§3–§4）。
- **观察 2：系统库既是内存负担，也是加速机会。** UI、视频解码和密码学等重活本来就在 DSC 中；让它们原生执行可同时避免第二份 DSC 和大量解释开销，但会失去库内部的指令级可见性。
- **观察 3：最难的不是 I→N，而是 N→I。** 解释器调用原生库很容易；原生库返回、调用 callback、ObjC method、Swift witness table 或异常 catch block 时，库代码不可改，解释器必须在没有动态 trampoline 的情况下重新截获控制流（§6.2–§6.3）。
- **假设 1：guest 与 host 使用兼容的系统库 ABI 和运行时布局。** loader 还定位 `notifyObjCMapped`、改写 libunwind 的私有函数指针，这些内部接口跨 iOS 版本变化时可能失效。
- **假设 2：分析目标不会主动读 iLand 自身地址空间。** guest 和 iLand 同进程运行；默认只拦截 API 与 syscall 内存访问，不检查每条原始 `LDR/STR` 是否越界。论文认为普通 App 很少探测随机地址，但这不是针对恶意目标的硬隔离（§7）。

## 核心方法

**Translator。** iLand 在运行前线性解码固定宽度 Arm64 指令，把一条指令拆成寄存器搬运、运算、结果写回等微操作（µ-op）。16-bit opcode 直接索引预编译执行单元，立即数写进 IR operand；`Table_IR_offset` 为每条原指令保存 4-byte 偏移，使原 PC 到变长 IR 的查找为 `O(1)`。系统共实现 6,709 个汇编执行单元，代码不超过 128 KB。x10–x15 被解释器保留，guest 对这些寄存器的访问重定向到线程本地 shadow（§4，图 3）。

**Loader 与 Interpreter。** 改造后的 dyld loader 把 guest Mach-O 原代码映射成只读页，把 AOT 生成的 IR 映射成只读数据，并完成 ASLR operand 修补、ObjC metadata 注册和异常表重定向。解释器的 dispatch header 只有“取 opcode、加 execution-unit base、跳转”三条指令；执行单元完成语义后再跳回循环。原代码、IR 和执行单元分别保持 R、R、RX 权限（§5–§6.1，图 2、图 4）。

**无状态控制流管理。** 每个 guest 指令地址对应一个固定长度 trampoline。大量 trampoline 虚拟页共享三张不可变代码页和一张可写数据页，靠 PC-relative 指令从 LR 还原 guest 地址，再进入解释循环；因此不需要每次调用保存额外状态，也不产生 RWX 页。iLand 在调用 `pthread_create` 等原生函数前，把 return address 和 callback 参数换成对应 trampoline（§6.2，图 5）。

**分层捕获与虚拟环境。** 静态 fixup 先替换已知代码指针，运行时拦截 C/C++/ObjC/Swift 调用并包装 return/callback；漏网的 N→I 会跳进不可执行的 guest code page，触发 SIGSEGV/SIGBUS，由 signal handler 接管并做一次 lazy 修复。这个 fallback 最慢可达原生的 1,000 倍，因此频繁回调且难以枚举的 `libswiftcore` 会改为继续解释。Virtual Environment Manager 再重定向 guest 文件系统、library call 和 syscall，让 guest 看见自己的 bundle/data container（§6.3–§7）。

## 设计取舍

- **应用代码可见性换系统库性能。** App 内任意指令可以插桩，系统库内部指令则不可见；iLand 只能在 library boundary 和 syscall 处观察它们。
- **静态复杂度换运行时合规。** 预编译 µ-op 避开 JIT，但实现超过 300 KLOC，包含 6,709 个手写汇编单元；新 Arm 指令和 iOS 私有运行时变化都带来维护成本。
- **透明分析换弱隔离。** guest 原代码不被改写，但分析前仍要取得已解密 IPA、生成 IR 并放入 iLand 的私有目录；15 个兼容性异常或失败 App 能检测到环境差异。
- **分层快路径换长尾风险。** 常见 callback 走 trampoline 很快，未知路径依赖 signal fallback；论文没有报告 fallback 发生率和 P99 开销。

## 实验与结果

- **三组实验口径**：性能组在 jailbroken iPhone X（A11、3 GB、iOS 16.7.7）上跑 SPEC CPU 2017 `train` 输入，只保留能交叉编译并原生运行的 8/19 个 benchmark；兼容性组在无公开 jailbreak 的 iPhone 14 Pro（A16、6 GB、iOS 17.3.1）上测试 64 个 2025 年 4 月美国 App Store Top Free App。所有 SPEC 性能测试都关闭插桩（§9.1，表 3）。
- **相对原生开销**：在同一 iPhone X 上，Valgrind 比原生慢 5–10 倍，iLand 慢 15–90 倍。表 4 的绝对时间例如 `x264_s` 为原生 12.5 s、Valgrind 111.0 s、iLand 1,244.2 s；iLand 的优势是无需 JIT，而不是接近原生性能（§9.2，表 4）。
- **解释器对照**：qemu-tci 在 Yitian 710 Linux ECS 上比其本机原生慢 100–600 倍，iLand 在 iPhone 上慢 15–90 倍，所以按各自 slowdown ratio 计算快约 5–15 倍。两者不在同一硬件、OS 或 runtime 上，不能把这个数字当成同机 speedup（§9.2）。
- **插桩范围**：表 5 的功能对照显示 iLand 同时支持任意 App 指令、library call 和 syscall 插桩，而且不需要 JIT；Frida/Substrate 只能部分覆盖 library boundary，QEMU 没有 closed-source iOS 适配。该表是功能清单，不是准确率或开销实验（§9.3，表 5）。
- **兼容性**：64 个 App 覆盖 16 类、二进制约 40–430 MB；49 个（76.6%）核心功能完整，11 个部分失效，4 个异常终止。也就是 60 个达到可继续 vetting 的“可用”状态，但不是 60 个都完整兼容。作者只做人工 login、browse、search、video 等主流程，没有自动覆盖率或 UI 延迟数据（§9.4、表 A.1）。
- **App vetting**：60 个可用 App 中，24 个二进制含 SVC，共 2,914 处；15 个实际通过 `SYS_open`、`SYS_read` 等直接访问系统文件；13 个运行时调用 private API，其中 `SecTaskCopyValueForEntitlement` 和 `iokit_user_client_trap` 两项用测试 App 经 TestFlight 验证会被自动拒绝。动态路径由人工注册和登录触发，未覆盖的路径可能产生漏报（§9.5，表 6–7）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 无 jailbreak 的 iOS 可以做 App 指令级 DBI | iPhone 14 Pro/iOS 17.3.1 上 64 个真实 App 均能启动测试，60 个达到可用状态 | 需要已解密 IPA；15 个 App 不完整或终止 | 强 |
| 预编译 µ-op 比通用解释器高效 | iLand slowdown 15–90 倍，qemu-tci 为 100–600 倍 | 不同硬件和 OS，只能比较各自相对原生的比例 | 中 |
| application-only emulation 保留真实 App 体验 | 49 个 App 可完成 login、video、browse 等人工主流程 | 没有 full-emulation 对照、量化 UI latency 或能耗 | 中强 |
| iLand 具有比 API hook 更细的观测能力 | 表 5 的三层插桩能力；SVC、间接跳转和 dlsym tracing 案例 | 系统库内部指令不可见，动态分析没有全路径覆盖 | 强（能力）/中（覆盖） |
| 热门 App 中存在绕过 review 的低层行为 | 13/60 调 private API、15/60 直接读系统信息；2 个 API 经 TestFlight 验证 | Top Free 非随机样本，Apple 无权威 private-API 清单，也无完整 ground truth | 中强 |

## 批判性分析

### 论证链条

“没有 RWX → AOT IR + 预编译 µ-op”“双份 DSC 太大 → 只解释 App”“原生库会回调 → 共享 trampoline + 分层 fallback”三条设计链都很清楚。真正没有闭合的是 application-only 的成本归因：论文没有测 full emulation 的实际内存、应用代码占比、各类 N→I 路径命中率，也没有逐项关闭 trampoline 预计算或 register fast path 的消融。因此 49 个 App 可用说明整体方案有效，却不能判断每个复杂组件贡献多少。

### 假设压力测试

应跨 iOS 17/18/19 和不同 A 系列芯片测试 dyld、ObjC、Swift、libunwind 私有接口是否稳定，并统计每种 callback 捕获层的命中率。对故意构造的 guest，应让它直接读写 iLand 地址、制造大量未知回调、动态生成 ObjC/Swift metadata 和触发复杂 unwind；这些场景会检验“普通 App 不探测地址”和 signal fallback 很少发生的假设。

### 实验可信度

真实 Top Free App 和两台 iPhone 给出难得的实机证据，且 49/11/4 的失败拆分比只报“60 个可用”更诚实。但 SPEC 只剩 8 个 benchmark、使用缩小的 `train` 输入并关闭 instrumentation；qemu-tci 对比跨平台。兼容性靠人工感受“无明显延迟”，没有帧率、响应时间、内存峰值、Jetsam、能耗和 P99。vetting 也没有已知恶意/合规 App ground truth，无法计算 precision 与 recall。

### 系统性缺陷

系统超过 300 KLOC，手写数千汇编单元，又依赖 iOS 私有运行时入口，维护和移植风险很高。15–90 倍的纯计算 slowdown 会触发 watchdog 或让计算密集 App 不可用，4 个终止案例已显示这一点。系统库内部不可观测，guest 与分析器同进程且默认没有逐指令内存隔离，也限制了安全分析的完整性。最后，获取解密 App、处理签名与分发规则本身是研究部署门槛；“标准 sandboxed App”不等于普通 App Store 用户可直接分析任意已安装 App。

## 局限与后续工作

- 在相同 Arm 硬件上对比 qemu-tci，并报告开启不同 instrumentation plugin 后的平均和 P99 slowdown、内存峰值与能耗。
- 量化静态替换、运行时拦截、lazy signal fallback 各自的命中率和开销，给出未知 N→I 路径的回归测试集。
- 为 guest memory access 启用可验证隔离，测试恶意 App 对 iLand 自身状态的读取和破坏。
- 用有 ground truth 的合规/违规 App 集合测量 private API 与 syscall detector 的 precision、recall 和路径覆盖率。

## 相关

- **相关概念**：[[Dynamic-Binary-Instrumentation]]、[[Binary-Translation]]、[[iOS-Sandbox]]、[[Code-Signing]]、[[AOT-Compilation]]
- **同类系统**：[[Valgrind]]、[[QEMU]]、[[Frida]]
- **同会议**：[[OSDI-2026]]
