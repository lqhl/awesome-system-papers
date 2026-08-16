---
type: paper
name: Mohabi
full_title: "Mohabi: Disaggregating and Sandboxing the Firefox JavaScript Engine"
authors: [Abhishek Sharma, Anand Balaji, Zachary Yedidia, Anthony Du, Taehyun Noh, Iain Ireland, Jan de Mooij, Matthew Gaudet, Tal Garfinkel, Deian Stefan, Hovav Shacham, Shravan Narayan]
venue: OSDI
year: 2026
tags: [browser-security, javascript-engine, sandboxing, software-fault-isolation, firefox]
source_pdf: "[[osdi26-sharma.pdf]]"
source_md: "[[osdi26-sharma]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Firefox JavaScript 引擎的解耦与沙箱化（OSDI 2026）

> **原题**：Mohabi: Disaggregating and Sandboxing the Firefox JavaScript Engine

> **一句话总结**：Mohabi 把整个 SpiderMonkey——包括解释器、JIT、运行时和大部分 GC——从 Firefox 中划出来，再用支持 256 GiB 地址空间和动态 JIT 代码验证的 MH-LFI 软件故障隔离（Software Fault Isolation，SFI）限制它；完整浏览器在 JetStream 2.2 和 Speedometer 3.1 上分别慢 24.82% 和 24.43%，但端到端安全仍取决于尚未覆盖完整 JSAPI 的边界检查。

## 问题与动机

现代 JavaScript 引擎不是一个普通的编译器。SpiderMonkey 同时包含 JavaScript、WebAssembly 和正则表达式的解释器与 JIT，并在多层执行引擎之间动态升级、降级和 bailout。优化 JIT 还会根据运行时类型推测删除数组边界检查；因此，即使引擎本身改用内存安全语言，错误的优化仍可能生成不安全的机器码。

禁用 JIT 只能减少一部分攻击面，而且代价很高：论文引用的 SpiderMonkey 数据显示，JIT 可带来 3.5×–7× 加速；Chrome 2025 年 12 个 JavaScript 引擎漏洞中有 5 个不靠 JIT，Edge 的安全模式解释器也被发现 23 个远程代码执行漏洞。把引擎放到独立进程又不现实，因为 DOM、事件队列、GC root 和 JSAPI 之间存在大量细粒度、嵌套调用。

Mohabi 的目标不是消灭 SpiderMonkey 内部漏洞，而是让引擎完全失陷后仍不能任意写 Firefox 内存、跳到宿主代码或直接发起危险系统调用，同时保留现代浏览器和 JIT。

## 关键观察 / 隐含假设

- **观察 1：合理的沙箱边界在整个 JS 引擎之外，而不是只包住 JS heap。** 把解释器、JIT 编译器、JIT 代码、C++ runtime 和大部分 [[Garbage-Collection|GC]] 一起视为不可信，可避免 Ubercage 那种每个内部组件都要反复净化 heap 数据的宽边界（§3、§7.4，图 7）。
  - **依赖假设**：Firefox 与 SpiderMonkey 的接口可以被显式化并逐项检查；论文只完成 DOM pointer table 等代表性检查，没有证明全部 JSAPI 边界均已覆盖（§7.3、§8）。
- **观察 2：浏览器已有的类型包装和代码生成能把大规模解耦变成少数重复模式。** Firefox 的 2,250 个 JSAPI 函数、有数量级更多的调用点和 1,075 种 WebIDL reflector 不适合人工逐个改写；split-allocation、自动 stub 和改造后的 binding generator 可集中处理（§4）。
  - **依赖假设**：接口仍经过这些生成器和 wrapper；绕过低层接口的新调用点若没有同样的类型约束，可能形成遗漏。
- **观察 3：站点隔离允许使用只限制写入的沙箱。** 每个内容进程不应保存其他顶级站点的秘密，因此 Mohabi 只约束 SpiderMonkey 的 store、控制流和系统调用，不给 read 加 mask，降低 SFI 成本（§3、§5.1）。
  - **依赖假设**：site isolation 确实把跨站秘密移出进程；同一站点内的机密泄露、推测执行侧信道和合法 API 滥用不是该保证的一部分。
- **观察 4：所有 SpiderMonkey JIT 最终汇聚到稳定的 x86-64 MacroAssembler backend。** 在这个 choke point 插入 mask、bundling 和间接跳转约束，比逐个修改九种执行引擎或每项优化更容易维护（§3、§6.1）。
  - **依赖假设**：没有 JIT 路径绕过 backend；论文早期原型确实出现过低层 assembler 直接发出未屏蔽跳转，最终由 validator 找出（§6.3）。
- **假设 1：MH-LFI runtime、binary validator、springboard/trampoline 和宿主侧净化器可信。** SFI 把约 784,000 行 SpiderMonkey 代码及运行时生成代码移出可信计算基（Trusted Computing Base，TCB），但不是零 TCB（§7.3）。

## 核心方法

### 先把 SpiderMonkey 从 Firefox 中划出来

SpiderMonkey 被单独编译成带私有 libc 的二进制，并装入每个需要 JS 的 Firefox 进程。进程内所有线程共享同一 sandbox instance，但各自拥有沙箱 stack、TLS 和保留寄存器上下文。Mohabi 不让原有符号继续直接链接；跨边界控制流必须走 springboard 或 trampoline（图 1、§4.1）。

移动 GC 会更新 Firefox 侧的 JS object reference。Mohabi 用 **split-allocation type** 把一个逻辑对象拆成两份：例如 `Rooted<T>` 的 `ptr` 字段放进沙箱，使 GC 能更新；维护 root 链表完整性的字段留在宿主。这一模式也用于 `Heap<T>` 等类型，并改动了浏览器中的数千个使用点（§4.2，图 2）。

### 自动恢复双向调用

Firefox 调 SpiderMonkey 时，stub-library generator 为 2,250 个 JSAPI symbol 生成间接跳表和专用 springboard。runtime 实例化沙箱时填入实际入口；springboard 切换 stack、保存寄存器并设置 SFI 的 base/mask register。

SpiderMonkey 回调 Firefox 时，目标必须预先注册，调用经 trampoline 返回宿主。WebIDL binding generator 被改成自动生成 sandboxed reflector type：第一次创建某类 DOM reflector 时，注册该类可用的 callback。对 C++ virtual dispatch，virtual trampoline type 把沙箱内虚调用转到已注册函数表，virtual springboard type 则把宿主虚调用转回沙箱；论文为约 20 个 JSAPI class 使用了这套方法（§4.3–§4.5）。

### 在边界净化不可信数据

仅限制控制流还不够：被攻陷的引擎可以篡改 DOM reflector 中的宿主 pointer，再诱导合法 Firefox callback 解引用。Mohabi 为 DOM object 建立带类型与引用计数的 pointer table，并修改 binding generator，在使用传回 pointer 前验证“表中存在且动态类型正确”（§4.6，图 4）。

这部分是原型最重要的未完成项。论文实现的是若干有代表性的 wrapper 和 DOM 检查，而不是对整个 JSAPI 做完备审计；作者把“自动确认所有必要净化均存在”列为后续工作（§7.3、§8）。

### MH-LFI：适合大内存浏览器的 SFI

MH-LFI 在编译器输出的 assembly/object 上重写指令，主要保留标准 clang/LLVM 工具链。它预留 `r14` 作为 sandbox base、`r15` 作为 mask、`r11` 作为 AOT scratch register：

- **数据策略**：对 store 计算目标地址、用 mask 限定在 256 GiB 对齐区域，再加 base；stack pointer 每次修改时受约束，沙箱两端有 unmapped guard region。
- **控制流策略**：每个指令或 guard macroinstruction 必须完整放在 32-byte bundle 内；间接跳转清零目标低 5 bit，只能落在 bundle 开头。`ret` 改写为 pop、mask、jump，避免并发线程在检查后篡改栈上返回地址。
- **系统调用策略**：把 syscall 改写为调用可信 runtime，由 runtime 只开放不会破坏隔离的操作。
- **工程策略**：compiler patch 约 600 行，负责保留寄存器、开放 alignment 和运行一个 backend optimization pass；项目从 LLVM 19 升到 LLVM 22 只花不到 3 天（§5.4）。

为了减少 x86 前端开销，MH-LFI 用 instruction prefix 分摊 bundle padding，把 TLS 放到未使用的 `GS` segment，并只在必须保留 flags 时用较慢的 `pext` 代替 `and`（§5.3）。

### 安全支持 JIT 代码更新

SpiderMonkey 的所有 JIT 经过 MacroAssembler。Mohabi 在 x86-64 backend 中发出同样的 store/branch mask 和 bundle alignment；代码页里的常量被放到 bundle 的第 1–31 byte，而第 0 byte 固定为会 fault 的 `HLT`，避免常量被当作绕过 SFI 的指令流（§6.1）。

JIT 不能简单把同一页在 writable 与 executable 间切换后只检查新增部分，因为并发线程可能改掉旧代码。Mohabi 使用 **dual mapping**：沙箱内保留 executable mapping，runtime 在沙箱外建立指向同一物理页的 writable shadow；更新时先让沙箱 mapping 只读，经宿主 shadow 写入并只验证新代码，再恢复 executable。该方案把每次更新的 permission change 从 3 次降到 2 次，并避免整页重验（§6.2）。

独立 binary validator 同时检查 AOT 与 JIT 代码，使编译器不在 TCB 内。它实际找到了三类遗漏：代码页尾部零字节会解码成 store、低层 assembler 发出的 indirect jump 没有 mask、Wasm trap 恢复路径会覆盖保留寄存器（§6.3）。

## 设计取舍

- **更完整的隔离边界换取约 25% 端到端开销**：Mohabi 比只保护 heap、约 1% 开销的 Ubercage 更贵，但把 JIT compiler、runtime、GC 和 stack 都纳入不可信区域，并提供 validator。
- **只防写逃逸换取较低成本**：write-only SFI 足以阻止权限提升所需的宿主内存破坏，却不构成同进程数据保密机制。
- **自动生成换取对 Firefox 架构的依赖**：codegen 显著减少人工改动，但自定义 JSAPI、GC cycle collector 和未来接口仍需单独审计。
- **大而固定的虚拟区间换取 native pointer**：256 GiB sandbox 避免 4 GiB 上限和边界 pointer translation，代价是要求大块、按 2 的幂对齐的虚拟地址空间。
- **软件可部署性换取 CPU 指令成本**：不依赖 MPK、CET 等不普及硬件，但每个 store、间接分支和 return 都要软件约束。
- **当前实现边界**：只实现 x86-64；ARM64、RISC-V、移动平台、完整边界审计和正式验证均未完成。

## 实验与结果

- 实验机为 Intel Core i9-13900K、32 GiB RAM、Ubuntu 24.04 和 Linux 6.14；浏览器基于 Firefox ESR 115，固定到两个 2.2 GHz 隔离 core，关闭超线程。每个 JetStream 2.2 和 Speedometer 3.1 分数取 15 次运行中位数（§7、表 2）。
- JetStream 分数从 `86.27 ± 0.71` 降到 `64.86 ± 1.10`，开销 24.82%；Speedometer 从 `6.81 ± 0.06` 降到 `5.14 ± 0.03`，开销 24.43%。作者称日常使用 YouTube、Reddit 没有可察觉变慢，但这只是定性观察（§7.1、表 2）。
- Speedometer 组件消融中，forward-edge CFI、backward-edge CFI、bundling、store mask 和 syscall mediation 分别使分数降低 6%、13%、5%、6% 和 3%；完整 Mohabi 为 24%，禁用 JIT 为 53%。各项会互相影响，不能把单项百分比直接相加（§7.1、图 5）。
- 在 NaCl 支持的 SPEC CPU 2017 子集上，同为 4 GiB、读写均隔离时，MH-LFI 平均开销 6.6%，NaCl 为 22.3%；Mohabi 使用的 large-memory、write-only 配置为 5.9%。三个 SFI 优化合计带来 6%–8% 加速（§7.2、图 6、图 9）。
- validator 平均吞吐量在 MH-LFI 4 GiB、MH-LFI Large 和 NaCl 上分别为 140.37、115.79 和 86.08 MiB/s。修改后的 LLVM 与 SpiderMonkey JIT 分别通过各自代码库的全部测试；不过测试通过不等于 validator 或边界净化器已形式化验证（附录表 3、§7.3）。
- 安全评估分析了 code-pointer hijacking、覆盖 executable memory、JIT spray、并发改码和危险 syscall，并检查 4 个 Mohabi 原型完成后由 Anthropic Mythos 找到的 SpiderMonkey JIT、GC、inline cache 和 runtime 内存破坏 bug；作者判断它们会被限制在沙箱内。论文没有回放真实 exploit，也没有生产部署期攻击数据（§7.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 大型遗留浏览器中的完整 JS 引擎可以被划出独立边界 | 2,250 个 JSAPI 自动 stub、1,075 类 reflector、约 20 个 virtual wrapper，完整 Firefox benchmark 可运行（§4、§7） | Firefox ESR 115、SpiderMonkey、x86-64 | 强 |
| MH-LFI 比禁用 JIT 更保留性能 | Speedometer 完整开销 24.43%，No-JIT 消融为 53%（图 5、表 2） | 两个标准 benchmark；没有真实站点 workload distribution | 强 |
| MH-LFI 是比 NaCl 更快的大内存 SFI 基础 | 可比 4 GiB 配置 6.6% 对 22.3%，large write-only 为 5.9%（图 6） | SPEC 子集；编译器版本不同，按各自 native baseline 归一化 | 强 |
| validator 能把 AOT/JIT compiler 排除出 TCB | validator 找到 3 类真实遗漏，吞吐高于 NaCl（§6.3、附录表 3） | validator 自身与 x86 decoder 仍在 TCB，未给形式化证明 | 强 |
| Mohabi 已提供端到端 sound browser sandbox | SFI 机制论证完整，但 data sanitization 只覆盖有限 JSAPI，作者明确称完整覆盖仍是开放问题（§7.3、§8） | 当前 prototype 不能据此声称所有 confused-deputy path 已关闭 | 弱 |

## 批判性分析

### 论证链条

论文最强的贡献不是某一条 mask 指令，而是把两个长期分开的难题接起来：先用类型和生成器把“哪里允许共享与调用”说清楚，再让 SFI 只负责强制执行内存、控制流和 syscall 边界。split-allocation、reflector、stub、pointer table、MacroAssembler 和 validator 分别对应 GC、DOM、JSAPI、宿主数据、JIT 与编译器遗漏，设计与 Firefox 的真实耦合点一一对应。性能消融也证明 backward edge 是最大单项，而不是笼统把全部成本归给 sandbox crossing。

标题、摘要和结论把 Mohabi 称为 sound sandbox，但正文给出的证据更适合支持“sound SFI core + 尚未完备的 browser boundary prototype”。一旦受损 SpiderMonkey 能经未净化 JSAPI 让 Firefox 成为 confused deputy，底层 SFI 仍然正确，端到端隔离却可能失败。论文自己承认 sanitization layer 只做了有限检查，因而应把强结论限制在所有跨边界值均正确验证的条件下。

### 假设压力测试

首先应故意绕过 WebIDL 和 stub generator，加入返回宿主 pointer、长度、enum、callback 或共享容器的新 JSAPI，检查构建是否会失败；如果只在 exploit 时才发现遗漏，边界不具备可维护性。其次应关闭 site isolation 或把同源 secret 放进内容进程，测试 write-only 模式究竟泄露什么；这不会破坏论文的完整性目标，却会暴露用户容易误解的保密边界。

256 GiB 对齐地址空间、3 个保留寄存器和 x86 `pext` 假设也需要在地址空间碎片、高线程数、不同微架构与 extension-heavy 浏览器上压力测试。JIT dual mapping 应用并发 fuzz 验证 permission transition、validator 与 code execution 之间没有 TOCTOU；仅靠功能测试无法覆盖恶意调度。

### 实验可信度

评测有完整浏览器、纯 JS/Wasm、SPEC、组件消融、validator throughput、代码库测试和安全案例，性能口径清楚，且拿 No-JIT 与 NaCl 两类相关基线比较。15 次浏览器运行的中位数与误差也比只给单次结果可靠。

但端到端结果只来自一台桌面 x86 机器、两个 synthetic benchmark 和较旧的 ESR 115。没有 page-load p95、交互 tail latency、memory footprint、energy、Web Worker scaling 或大型 ArrayBuffer/Wasm 的专项数据。安全部分是机制分析和事后 bug mapping，不是 exploit containment 实验；“YouTube/Reddit 无明显变慢”也没有计量。因此性能可用性和安全完备性都还不能等同生产验证。

### 系统性缺陷

边界检查是最主要的结构性债务。当前 TCB 包含 6,200 行 MH-LFI runtime、991 行 validator、1,276 行 Fadec decoder 及其 1,894 行生成表、约 650 行 wrapper definition 和 80 行 DOM table 代码；真正困难的 JSAPI sanitization 还未做完。Firefox 每次增加新的 Web API、GC interaction 或 callback pattern，都可能扩大审计面。

Mohabi 也没有解决合法接口滥用、同进程读取、侧信道、DoS 或浏览器 renderer 之外的 privilege escalation。每个 Firefox 进程都要装一份 256 GiB sandbox mapping，且目前只支持 x86-64。约 25% 的标准 benchmark 开销虽远低于 No-JIT，却仍可能阻碍默认开启；论文没有给按网站、设备或风险等级逐步启用的策略。

## 局限与后续工作

- **局限 1**：宿主边界净化没有覆盖完整 JSAPI，也没有静态证明或构建期检查保证所有新接口经过 sanitizer。
- **局限 2**：只评估 x86-64 单机 Firefox ESR 115；ARM64、移动端、内存占用、能耗和真实网页 tail latency未知。
- **局限 3**：write-only SFI 不保护同进程读取，且侧信道、DoS、合法 Firefox API 滥用不在保证内。
- **局限 4**：安全评估未运行真实 exploit，也未形式化验证 runtime、validator、decoder 和 dual-mapping 并发协议。
- **后续工作 1**：为 JSAPI 定义可机检的跨域类型，自动生成双向 sanitizer，并用未标注接口的 negative build tests 验证 fail-closed。
- **后续工作 2**：回放真实 SpiderMonkey CVE 和 Ubercage bypass，在并发 Web Worker 下验证写逃逸、控制流逃逸、syscall 与 TOCTOU 均被阻止。
- **后续工作 3**：实现 ARM64/RISC-V backend，并在 desktop/mobile 的真实站点集合上报告 page-load、交互 p95、RSS、能耗和崩溃率。

## 相关

- **相关系统**：Firefox、SpiderMonkey、V8 Ubercage、NaClJIT、RockJIT、NoJITSu
- **相关概念**：软件故障隔离、进程内隔离、JIT compilation、binary validation、confused deputy
- **同会议**：[[OSDI-2026]]
