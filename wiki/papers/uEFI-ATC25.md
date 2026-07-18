---
type: paper
name: uEFI
full_title: "µEFI: A Microkernel-Style UEFI with Isolation and Transparency"
authors: [Le Chen, Yiyang Wu, Jinyu Gu, Yubin Xia, Haibo Chen]
venue: ATC
year: 2025
tags: [uefi, firmware-security, isolation, microkernel, sandboxing, access-control]
source_pdf: "[[atc2025-chen-le.pdf]]"
source_md: "[[atc2025-chen-le]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-18
---

# µEFI: A Microkernel-Style UEFI with Isolation and Transparency (ATC 2025)

> **一句话总结**：µEFI 把 [[UEFI]] 的 signed-but-untrusted modules deprivilege 到独立地址空间，利用 system table 这个统一 callout gate 和标准化 protocol metadata 做透明 trampoline 转发、参数验证与数据同步；在 EDK2 上跑 6 个未修改模块时 boot 阶段开销为 1.91%，但安全边界依赖可信 UEFI core、完整 protocol 语义和预部署 policy/testing。

## 问题与动机

论文要补的是 [[Secure-Boot]] 的结构性盲点：Secure Boot 验证模块是否被信任签名，却不保证签名模块内部没有漏洞。一旦合法 DXE driver、bootloader 或第三方 UEFI application 有 memory safety / input validation bug，攻击者仍可借它绕过 boot chain，甚至安装能跨系统重装和硬盘替换存活的 firmware implant。

作者把风险归因于 UEFI 生态复杂度增长。到 2025 年 UEFI Forum 有 365 个 vendor，EDK2 代码量从 2018 到 2025 增长约 9 倍；供应链里 OEM、IHV、chip vendor、BIOS vendor 层层叠加，下游常在上游 firmware 之上继续加模块。结果是 UEFI 模块越来越多、来源越来越杂，但默认仍共享地址空间、以高权限执行，并且 services / protocols 基本全局可达。

现有 OS driver isolation 不能直接搬过来。UEFI 模块常以 binary 形式存在，尤其是 option ROM，要求不能改模块；模块之间不是静态符号调用，而是通过 core services 在运行时 discover protocol function pointer；跨模块数据也没有一个统一 IPC payload 格式，而是 C pointer 和 protocol-specific struct 直接共享。

µEFI 的 claim 是：在不修改现有 UEFI modules 的前提下，用 microkernel-style isolation 给每个模块独立 sandbox，同时维持原来的 function-call interface illusion，并在服务和 protocol 层加 capability restriction 与 automatic input validation。

## 关键观察 / 隐含假设

- **观察 1：UEFI 的 callout 虽然动态，但入口高度集中。** services 通过 system table 直接取；protocol interface 虽然运行时 discover，但也要通过 LocateProtocol 等 core services 间接拿到。µEFI 因此可以替换每个 sandbox 看到的 system table，并在 protocol acquisition 时注入 trampoline。
  - **依赖假设**：模块的外部交互主要经过 UEFI 标准 service / protocol 路径，而不是大量绕开 system table 的私有入口、硬编码地址或 vendor-specific side channel。
  - **可能失效场景**：某些 proprietary firmware 通过非标准全局状态、MMIO side effects、hand-written assembly 或私有 dispatcher 交互时，透明拦截可能不完整。

- **观察 2：UEFI protocols 足够标准化，能离线恢复跨模块调用的数据语义。** protocol definition 包含函数、struct、参数注释和 GUID，调用者按 interface contract 写代码，不需要知道 provider 实现。µEFI 用 LibClang 解析 EDK2 protocol headers，生成 protocol/function/type 数据库，运行时由 interface proxy 查询。
  - **依赖假设**：生产 firmware 的 protocol definitions 与实际 binary 行为一致；参数名和注释能支撑 buffer-size / array-count pairing；custom protocol 的语义也能进入数据库。
  - **可能失效场景**：void* 携带隐式 payload、vendor protocol 文档不足、注释与实现不一致、callee 对 pointer lifetime 有隐藏约定时，自动 validation / copy 只能覆盖一部分语义。

- **观察 3：UEFI boot phase 的单线程、短生命周期让 isolation 成本可被隐藏。** 论文强调 UEFI 是 single-threaded event-driven 环境，没有 OS driver isolation 里复杂的同步和并发共享状态问题；多数真实 boot path 又被硬件 I/O 和 OS boot time 掩盖。
  - **依赖假设**：目标 workload 仍是典型 boot-time firmware execution，而不是高频、低延迟、纯内存 protocol call 密集路径。
  - **可能失效场景**：runtime services、SMM handler proxy、或大量 tiny cross-sandbox calls 会把 syscall/context-switch/copy 成本放大；mock DiskIo 实验已经显示非 I/O 路径下开销从 5,646 cycles 增到 26,437 / 30,870 cycles。

- **假设 1：UEFI core 和更早 SEC/PEI phases 可以作为 TCB。**
  - **证据强度**：中。论文给出工程边界而非证明；这种边界让设计可落地，但也意味着 core、SEC/PEI、sandbox manager 或 protocol database bug 不在防护范围内。

- **假设 2：least-privilege policy 可以通过显式声明或启发式分类得到。**
  - **证据强度**：弱到中。显式 GUID policy 需要开发者/部署者维护；启发式从第一个 non-generic protocol 推断 module type，论文把 miss 处理为 pre-deployment testing 中的 fail-stop，但没有给出大规模 production policy 维护成本。

## 核心方法

µEFI 的在线部分是 sandbox manager，作为一个 UEFI module 与 core 同权运行；为了优先接管后续 module loading，core 修改少于 100 SLOC。每个被隔离的 UEFI module 进入 user mode / lower privilege execution，并拥有独立 page table、heap metadata、shadow system table 和 transient sandbox stack。sandbox manager 本身约 4,773 SLOC C + 253 SLOC assembly，离线 analyzer 约 907 LOC C++。

**Shadow service** 解决 core service 调用。UEFI core 原本把 Boot Services / Runtime Services 的 function pointers 放在 system table 里传给 module；µEFI 在加载 sandboxed module 时传入 per-sandbox shadow system table，把 service call 变成 system call 进入 sandbox manager。这样一来，shadow service 能做两层 [[seccomp]]-style restriction：一层限制 LoadImage / StartImage 等高权限 services，另一层限制 module acquire/install 哪些 protocols。

policy 有两种来源。严格模式下，开发者按 module GUID 显式声明可调用 services/protocols；兼容模式下，系统根据 module 第一次 acquire/install 的 non-generic protocol 推断 module type，只允许对应类别 protocols。后者是 µEFI 透明性的一部分，也是一个明显工程取舍：它降低手写 policy 成本，但把安全正确性转移到 pre-deployment testing 和 fail-stop 行为。

**Safe trampoline injection** 解决 protocol function pointer 调用。普通 microkernel IPC 需要 caller 知道 server、准备 IPC message、调用专门接口，会破坏 UEFI binary transparency。µEFI 在 module 获取 protocol interface 时不返回真实 function pointer，而是动态生成 read-only trampoline：trampoline 携带 protocol/function metadata，按原 calling convention 接住调用，然后 syscall 到 sandbox manager。sandbox manager 的 interface proxy 处理参数后再 forward 给目标 module。

trampoline 有三类。cross-sandbox trampoline 支持一个 sandbox 调另一个 sandbox 的 protocol function；core-sandbox trampoline 让 UEFI core 调 sandboxed module 暴露的 basic protocol；return / callback trampoline 让 callee 或 callback 结束后能透明回到 sandbox manager。这个设计的核心是保留 C function call 的表象，而不是要求模块显式参与 IPC。

**Interface proxy + protocol database** 解决参数验证和数据同步。离线 analyzer 用 LibClang 解析 EDK2 MdePkg 等 protocol headers，提取 protocol GUID、function signature、struct/type、参数方向和特殊 pointer 处理策略，生成 JSON 并静态嵌入 sandbox manager。运行时只先加载 protocol table；第一次遇到某 protocol function 时 lazy query function/type 信息，缓存后 DB query 平均约 55 cycles，首次 query 约 200-300 cycles。

最脆的部分是 **parameter pairing**。C 的 void* 或 Type* 本身不告诉系统 buffer size / array count；µEFI 先看类型，如果 pointer 指向 protocol 则按 handle/token 处理；否则用参数名模式（如 Buffer / BufferLength）和 function comments 判断 size/count 参数。对于 string 和 device path 等标准格式，运行时用 StrLen / GetDevicePathSize 等 library parse。分析失败的 void* 会标记为需要 manual handler。

数据传输按 interface semantics 复制和同步。输入 buffer 会复制到 callee 可访问的 transient memory，调用结束即可释放；输出 buffer 或多级 pointer 返回的数据生命周期更长，shadow service 会为 caller 分配对应 buffer，并把 caller-side buffer 与 callee-side allocation 建立层级关系，等 callee 释放原始对象时级联释放，避免跨 sandbox returned object 泄漏。

## 设计取舍

- **透明性 vs. TCB 增大**：µEFI 不要求改 binary module，这是它能处理 option ROM / legacy module 的关键；代价是 sandbox manager、trampoline、interface proxy、protocol DB 都进入可信路径，任何 metadata 或 copy/validation bug 都可能变成新攻击面。
- **自动 protocol analysis vs. 语义不完整**：对标准协议，离线解析能覆盖大量结构化参数；对隐式 payload、vendor-specific protocol、注释缺失或实现偏离 specification 的接口，仍需 manual effort 或只能 fail-stop。
- **细粒度 least privilege vs. policy 维护成本**：显式 GUID policy 更接近 security-by-contract，但部署成本高；启发式分类更简单，却可能过宽、过窄，或依赖测试覆盖发现缺失 capability。
- **page-table isolation vs. cross-call overhead**：隔离能阻止 stack/heap overwrite 直接污染其他模块或 core；每次 service/protocol call 都要经过 trap、validation、copy 和可能的 context switch，纯计算/纯内存路径会更敏感。
- **boot-phase focus vs. runtime/SMM 泛化**：论文主实验验证 DXE-to-ExitBootServices 的 boot path；discussion 提到 runtime services 和 SMM call proxy，但没有完整实现与评估。

## 实验与结果

- **安全评估**：作者构造 stack overflow、heap overflow、improper input validation 测例，映射 CVE-2021-39297、CVE-2023-39538 等案例。µEFI 不能消除 vulnerable module 内部 bug，但能把破坏限制在该 module sandbox，或在 cross-module call 边界阻止非法 pointer / oversized BufferSize。
- **真实攻击分析**：ThunderStrike 修改 DXE service table pointer 的 hook 被 per-sandbox shadow service table 局部化；BootHole/BlackLotus 类 signed component compromise 即使绕过 Secure Boot，也难以直接写其他 module/core memory 或插入跨模块 hook。
- **generality**：离线 analyzer 扫 EDK2 protocols。Protocol fields 只有 2 / 1147 需要 manual effort；compound type failure rate 约 0.26%（87 / 33278 fields）；function parameters 中 17.4% 属于需特殊处理 pointer 类，manual effort 为 90 / 3639，约 2.5%。
- **boot-time overhead**：在 EDK2 OVMF + QEMU/KVM 和 Raspberry Pi 4B 原型上，sandbox manager 空载增加 0.91% boot latency；每增加一个 sandboxed module 平均增加 0.17%；6 个模块（EnglishDxe、FAT、DiskIo 等）全部隔离时 DXE 到 ExitBootServices 的 boot-time overhead 为 1.91%。
- **module execution overhead**：FAT end-to-end 文件创建/读写/删除实验中，x86 VM 上只隔离 FAT 平均开销 0.35%，同时隔离 FAT + DiskIo 为 0.78%；Raspberry Pi 4B 上分别为 3.85% 和 4.11%。
- **非 I/O mock test**：把 DiskIo 的 I/O 替换成 memory operation 后，x86_64 128B baseline 为 5,646 cycles；sandbox FAT 后为 26,437 cycles；sandbox FAT + Mock-DiskIo 后为 30,870 cycles。这个实验暴露出 µEFI 的固定成本在 tiny calls 上并不小，只是在真实 firmware I/O 中被掩盖。
- **overhead breakdown**：x86_64 cross-sandbox context switch 平均约 1,126 cycles；cached DB query 平均 55 cycles；800B input buffer 相比 input object 多约 280 cycles；output buffer 的 caller allocation 和 data synchronization 是最大额外项之一。Raspberry Pi 4B context switch 平均约 5,262 cycles，主要与 trampoline/jump buffer cache invalidation 有关。
- **memory overhead**：每个 sandbox 基础额外内存通常低于 40KB，包括 17KB page table / heap metadata、8KB shadow system table、每个 acquired/installed interface 520B、每个 trampoline 128B；每次 sandbox call 还需要约 33KB transient memory（32KB stack、return trampoline、jump buffer 和参数 buffer）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| boot-path transparency has low measured overhead | six sandboxed modules add 1.91%; manager alone 0.91%; each module average 0.17%（§6.2，Fig. 8） | DxeMain to ExitBootServices on QEMU/KVM and Raspberry Pi 4 prototypes; not full OS boot | high |
| end-to-end FAT workload remains close to baseline | FAT-only 0.35% and FAT+DiskIo 0.78% overhead on x86; 3.85%/4.11% on Pi 4（§6.3，Fig. 9） | FAT create/read/write/delete workload, not all UEFI modules | high |
| tiny non-I/O calls expose high fixed cost | 5,646 cycles baseline vs 26,437 / 30,870 cycles（§6.3，Fig. 11） | 128B Mock-DiskIo memory-operation test on x86_64 | high |
| protocol analysis requires limited manual handling in EDK2 corpus | 2/1,147 protocol fields; 87/33,278 compound fields; 90/3,639 special-pointer fields（§5，Table 2） | EDK2 headers, not OEM/custom binary protocol semantics | high |
| cross-sandbox calls have measurable component costs | 1,126-cycle context switch; 55-cycle cached DB query; 800B input adds 280 cycles（§6.4，Fig. 12） | QEMU/KVM microbenchmark; not end-to-end boot latency | high |

## Critical Analysis

### 论证链条

论文的主链条比较闭合：UEFI 漏洞增长与共享高权限环境造成风险；UEFI 的 system table / protocol 机制提供可拦截边界；trampoline 保持 binary transparency；protocol database 让跨地址空间数据传输可自动化；实验显示常见 boot path 开销很低。这个链条对“boot-time UEFI module isolation”成立得不错。

但它把两个局部前提外推得比较大胆。第一，EDK2 protocol definitions 能代表 production firmware 的协议行为；第二，6 个模块上的透明运行能代表真实 vendor firmware supply chain。论文给了 EDK2-wide static analysis，但没有给出跨 OEM proprietary protocol corpus，也没有展示真实 closed-source option ROM 大样本。

### 假设压力测试

核心压力点在 protocol semantics。µEFI 能验证 pointer 是否属于 caller、buffer size 是否不越界，却难以判断逻辑合法性；论文自己承认 CVE-2023-39538 这类内部 integer overflow 不会被 interface proxy 发现，只能靠 isolation 降低 blast radius。如果攻击目标只是 compromise 某个关键 bootloader 本身，而不需要跨模块写别人的 memory，µEFI 的收益会下降。

第二个压力点是 policy。显式 declaration 与 [[seccomp]] 类似，安全性强但需要维护；启发式 module type detection 则依赖“第一个 non-generic protocol 足以代表模块功能”。如果一个 module 先碰到通用或误导性 protocol，或者正常功能需要跨类别访问，系统可能要么 fail-stop，要么放宽 policy。

第三个压力点是 deployment placement。µEFI 信任 UEFI core、sandbox manager、SEC/PEI 以及硬件初始化前提；这让它避开最难的问题，也意味着早期 firmware compromise、core bug、SMM bug、malicious protocol database 或 sandbox manager bug 都可能绕过论文保证。

### 实验可信度

实验选择覆盖了两个架构和 FAT/DiskIo 等复杂模块，这是优点。尤其是 FAT + DiskIo end-to-end 和 mock DiskIo 分开做，清楚说明“真实 I/O 路径开销低”和“纯内存路径固定成本高”不是同一个结论。

不足是 workload 规模仍偏 demo。只隔离 6 个模块，且评价区间是 DxeMain 到 ExitBootServices；没有大规模 vendor firmware、更多 closed-source option ROM、复杂 boot menu/network boot/graphics stack，也没有长时间 runtime services。安全评估主要是 test cases 和攻击分析，不是对真实 firmware images 的 exploit replay corpus。

baseline 公平性上，论文没有与其他 UEFI-specific isolation 系统直接比较，因为几乎没有同类系统；与 OS driver isolation 的比较主要是概念层。它更像是证明“UEFI 可以有一个透明 isolation layer”，而不是证明这是生产部署中唯一或最优的 tradeoff。

### 系统性缺陷

论文未充分讨论 observability 和 debugging。UEFI 本来就难调试；引入 trampoline、shadow table、lazy protocol DB、cascade memory tracking 后，故障可能表现为 early boot hang 或 fail-stop，生产 BIOS 团队如何定位 policy 缺失、metadata 错误或 vendor protocol handler bug 仍不清楚。

资源隔离也不是完整 multi-tenant 隔离。µEFI 限制 memory 和 service/protocol capability，但 firmware module 仍可能通过合法 hardware I/O、timing、device state 或 persistent NVRAM 造成影响。论文聚焦 memory safety 和 input validation，对 device-level side effects、availability attack、rollback/recovery 讨论较少。

最后，LLM-assisted parameter pairing 是有趣但也有维护风险的环节。论文报告 manual effort 很低，但没有说明 LLM 输出如何审计、版本化和回归测试；如果 analyzer 误配 BufferSize，安全边界可能变成“看起来有 validation，实际验证错对象”。

## 局限与 Future Work

- **局限 1：TCB 边界较硬。** µEFI 不保护 UEFI core、SEC/PEI、sandbox manager 自身和 protocol metadata 生成链路；后续可以用 fault injection / fuzzing 专门攻击 shadow service、trampoline decoder 和 interface proxy。
- **局限 2：protocol 语义覆盖依赖 EDK2 corpus。** 需要在真实 OEM/IHV firmware 和 closed-source option ROM 上统计 custom protocol 比例、manual handler 数量、policy miss rate 和 boot failure mode。
- **局限 3：policy 不是自动安全。** 显式 declaration 的维护成本、启发式分类的误判率、fail-stop 对用户设备可用性的影响都需要系统性 measurement。
- **局限 4：性能结论主要适用于 I/O-heavy boot path。** 对 runtime services、SMM proxy、network boot、graphics initialization 或 high-frequency protocol calls，需要单独测 tail latency、call-rate saturation 和 cache/TLB side effects。
- **Future work 1：构建 firmware isolation benchmark。** 收集多厂商 firmware images 和 option ROM，测 µEFI 的透明启动率、manual protocol handler 数、policy adjustment 次数和失败根因。
- **Future work 2：把 protocol DB 变成可验证 artifact。** 为 parameter pairing 输出 provenance、unit tests 和 differential checks，确保 metadata 更改不会悄悄削弱 validation。
- **Future work 3：扩展到 runtime/SMM 并量化收益。** 将 interface proxy 用于 UEFI runtime services 和 SMM calls，比较能阻断哪些真实 SMM/Runtime CVE，以及引入多少 latency 和 compatibility 风险。

## 相关

- **相关概念**：[[UEFI]]、[[Secure-Boot]]、[[Firmware-Security]]、[[Microkernel]]、[[Driver-Isolation]]、[[Sandboxing]]、[[seccomp]]
- **同类系统**：[[KSplit]]、[[Nooks]]、[[Redleaf]]、[[OROM-Sandbox]]
- **相关实现/生态**：[[EDK2]]、[[Option-ROM]]、[[SMM]]
- **同会议**：[[ATC-2025]]
