---
type: paper
name: Try
full_title: Controlling Opaque-Component Effects with Semisolates and Try
authors: [Evangelos Lamprou, Tianyu Ezri Zhu, Grigoris Ntousakis, Georgios Liargkovas, Di Jin, et al.]
venue: OSDI
year: 2026
tags: [sandboxing, filesystem, effect-control, shell, software-safety]
source_pdf: "[[osdi26-lamprou.pdf]]"
source_md: "[[osdi26-lamprou]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用 Semisolate 控制 Opaque Component 的副作用（OSDI 2026）

> **原题**：Controlling Opaque-Component Effects with Semisolates and Try

> **一句话总结**：container 隔离会切断当前环境，直接执行又让 package/script/AI command 产生不可逆 filesystem effect；`try` 用 unprivileged namespace+OverlayFS 构造 semisolate，执行原 command 后可 inspect、selectively apply、stack 或 discard effect，在五类真实 case 保持 filesystem equivalence，通常比 Docker 快 1.1–225.7×，但相对 vanilla 代价可达 8.3×。

## 问题与动机

现代 script、package hook、shell pipeline 和 coding agent 会调用 opaque/polyglot component。它们必须读取当前 host 环境才能有用，却可能误删 user file、修改 `/etc` 或产生难以回滚的 build effect。native `--dry-run` 各自实现且未必忠实，container 可隔离但需 copy/mount 新环境，无法自然让后续 command 看见尚未 commit 的前序 effect。

semisolate 介于直接执行与完整 isolate：component 看见当前 environment，但 write 被暂存；调用者决定 effect 的 visibility/lifetime。目标是 command-agnostic、language-agnostic、unprivileged，并支持串联 speculative execution。

## 关键观察 / 隐含假设

- **观察 1**：多个场景共享的不是“禁止 effect”，而是 capture 后 inspect/apply/discard/stack/manipulate（§2）。
  - **依赖假设**：主要 external effect 是 filesystem/path operation，可由 mount/tracing mediation。
  - **可能失效场景**：network request、IPC、database/cloud API、device、signal 或 irreversible external action。
- **观察 2**：后续 opaque command 需看见未 commit effect，stackable OverlayFS layer 可提供“似乎已发生”的 view（§2–4）。
  - **依赖假设**：filesystem layer order/whiteout 语义覆盖 rename/delete/link 等操作。
- **假设 1**：open/path syscall tracing 足够推断 read/write dependency；对已 open fd 的细粒度 operation 默认不全 trace。
  - **证据强度**：中。case equivalence通过，mmap/fd passing等 corner需定制 filter。
- **假设 2**：用户/上层 policy 能审查 effect list；大量文件或恶意命名会产生 review overload。
  - **证据强度**：中弱。

## 核心方法

`try <command>` 创建 user/mount namespace，把 host directories 作为 OverlayFS lowerdir、临时 writable upperdir 组成 component view；选择性 bind device与标准 fd。command原样执行，filesystem mutation进入upperdir/whiteout，不先触碰host。

结束或streaming期间，try枚举 effect，支持全部/逐项 apply、discard、隐藏 host path、filter/aggregate。`-N env`保存 layer而不commit，`-L env`把前一 layer叠入下一 invocation，使 speculative pipeline 看见依赖；可最终按正确 order commit或回滚。

需要 dependency/spec mining时，Seccomp-[[eBPF|BPF]]只拦预配置 path syscall（open/mkdir/unlink等）并借strace记录，避免每次read/write；用户可扩filter。apply阶段把upperdir object移动/复制回host并解释whiteout。

## 设计取舍

- **partial isolation 换 compatibility**：读真实host、write可控；未中介的network/device effect仍外泄。
- **OverlayFS copy-up 换透明执行**：无需改component，首次写大文件/海量文件成本高。
- **selective syscall tracing**：较低overhead，dependency completeness依赖filter。
- **实际执行式 dry-run**：比native模拟忠实，必然比不做work的native dry-run慢。

## 实验与结果

- 五类case：[[LLM|LLM]] risky script、dependency tracking、third-party hook、dry-run、specification mining；以全filesystem tree checksum/manual inspection验证 apply 后 output/effect与vanilla等价（§5、表2）。
- 综合case相对vanilla overhead 1.0–8.3×，相对Docker速度提高1.1–225.7×；作者不报geomean因配置/目标异质（§5）。
- LLM/script case相对vanilla 1.1–1.9×，相对Docker快1.3–225.7×；dependency case overhead 1.0–1.7×、快Docker 1.1–18.7×（§5.1–5.2）。
- native dry-run平均0.03 s，try实际执行再discard平均0.26 s，慢4.9–82.6×；但比Docker快1.2–3.2×（§5.4）。
- microbenchmark中165 ms echo的OverlayFS setup 42 ms（25%）、mkdir 37 ms（22%）；10,000 small files使namespace exit达6.3 s（§5.6、图3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| semisolate可控制且最终保持filesystem effect等价 | §5、表2：五类case checksum/manual equivalence | Linux filesystem effect、所选command | 强 |
| 比完整container轻 | §5：相对Docker快1.1–225.7× | setup/copy模式差异很大 | 强 |
| 对vanilla开销case-dependent且可显著 | §5：1.0–8.3×，native dry-run 4.9–82.6× | short command/trace/file count敏感 | 强 |
| 支撑research speculative/incremental system | §6：hS/Incr使用并报告9.3×/373.3× | 外部project结果，非本论文controlled baseline | 中 |

## 批判性分析

### 论证链条

论文从不同use case抽取统一effect algebra，semisolate abstraction比“更轻container”更有价值；try展示Linux实现可行。equivalence/case覆盖强，但“controls all relevant effects”严格限定到配置过的filesystem effect，不是安全sandbox。

### 假设压力测试

恶意component可发network、访问shared service、fork daemon、写未overlay mount或利用ioctl，effect不可回滚。即便filesystem内，hard link、bind mount、mmap、open fd继承、setuid/xattr与concurrent host writer可能破坏snapshot/apply语义。selective apply可能产生应用级不变量断裂。

### 实验可信度

case异质、公开artifact、filesystem checksum与Docker/vanilla三方对比可信；不强行报geomean也合理。缺少系统化POSIX filesystem test suite、concurrent mutation/fault injection、安全escape评估；最大225.7×由Docker copy/setup outlier驱动，不代表一般性能。

### 系统性缺陷

effect审查UI面对node_modules/compile等数万file不实用，需semantic summarization但会引入漏报。apply中途crash可留下partial state，论文未给transactional commit。OverlayFS/namespace/kernel差异限制macOS/Windows与某些NFS/FUSE；unprivileged namespace常被hardened environment禁用。

## 局限与后续工作

- **局限 1**：主要控制filesystem，不是完整security isolation。
- **局限 2**：海量small files、copy-up与short command overhead显著。
- **局限 3**：selective apply与concurrent host mutation缺少transaction guarantee。
- **后续工作 1**：对网络/IPC/db effect加入pluggable transactional proxy，并明确不可回滚action的fail-closed policy。
- **后续工作 2**：跑xfstests/POSIX corner与并发writer/crash injection，验证stack/apply/rollback一致性。
- **后续工作 3**：实现journaled atomic commit和effect provenance/diff summarization，测10k+ effect的review error与恢复。

## 相关

- **相关概念**：[[Sandboxing]]、[[OverlayFS]]、[[Effect-System]]、[[Speculative-Execution]]
- **同类系统**：[[Docker]]、[[Podman]]、[[strace]]
- **同会议**：[[OSDI-2026]]
