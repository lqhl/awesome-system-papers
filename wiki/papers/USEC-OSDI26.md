---
type: paper
name: USEC
full_title: "USEC: A User-Requirement-Driven Mandatory Access Control Framework for Operating Systems (Operational Systems)"
authors: [Yu Jiang, Wenhuan Liu, Fuchen Ma, Yuheng Shen, Yuanliang Chen, Lei Zhang, He Li, Quan Zhang, Chijin Zhou]
venue: OSDI
year: 2026
tags: [operating-system-security, mandatory-access-control, linux, lsm, access-control]
source_pdf: "[[osdi26-jiang-yu.pdf]]"
source_md: "[[osdi26-jiang-yu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向用户需求的操作系统强制访问控制框架（OSDI 2026）

> **原题**：USEC: A User-Requirement-Driven Mandatory Access Control Framework for Operating Systems (Operational Systems)

> **一句话总结**：安全厂商通常只想保护少量高价值资源，USEC 因而用 resource-centric JSON 描述“谁能对哪个资源做什么”，再从能力声明编译出必要的 LSM hook 并用 bitmap/UAVC 跳过无关检查；camera 案例从 SELinux 的 300 多行降到两份合计少于 20 行的 JSON，Nginx 吞吐为 92,185 req/s、优于 SELinux 的 84,748 req/s，但保护范围完全依赖管理员有没有列全关键资源。

## 问题与动机

强制访问控制（Mandatory Access Control，MAC）在普通自主访问控制（Discretionary Access Control，DAC）之外，由内核判断进程能否访问文件、设备、IPC endpoint 或 socket。即使应用进程已被攻陷，MAC 仍可限制它接触关键资源。Linux 通常通过 [[Linux-Security-Modules|Linux Security Modules（LSM）]] 承载 SELinux、AppArmor 等模块。

论文认为 SELinux 在企业部署中有三个现实障碍。第一，策略围绕 subject domain、object type 和 allow rule 展开，一个业务意图会散落在 label、attribute、module 和 constraint 中。第二，大量 hook 长期开启，即使某条内核路径和部署的保护目标无关，也要进入 MAC dispatch、cache 和 policy engine。第三，全局、细粒度的限制容易让按照 DAC 语义编写的安装器和旧应用失败；操作员难以定位 denial，最后可能直接关闭 SELinux（§1–§3）。

USEC 不是要对所有 kernel object 做 complete mediation。它面向安全厂商和企业 endpoint：部署方显式列出少量关键资源，只对这些资源提供强制保护，未命中的资源继续交给 DAC 和其他 LSM。论文的主要问题因此是：能否用更接近管理员意图的接口缩小策略和执行面，同时保留所声明资源上的强制检查与现有 Linux 软件兼容性（§4.1）。

## 关键观察 / 隐含假设

- **观察 1：厂商通常从“要保护什么”出发，而不是从“每个进程能做什么”出发**。例如，endpoint agent 关心自己的 data、log、key 和 device，资源数量远少于系统中的 domain–type 组合。把规则锚定在资源上，可直接表达允许哪些 principal 执行 read、write 或 execute（§3.1、§4.2）。
  - **依赖假设**：保护目标确实稀疏，而且部署方能枚举完整；若漏掉 credential、socket 或间接依赖，USEC 会回退到 DAC，而不是默认拒绝。
  - **可能失效场景**：目标是全系统 information-flow control、复杂 role/MLS constraint，或资源在 container、mount namespace 中快速生成和变化。
- **观察 2：MAC 开销应随声明的能力集合增长，而不必随内核全部 hook 数量增长**。能力编译器把高层能力展开成 TE permission 和所需 hook 的并集；运行时 bitmap 让无关 hook 立即返回，只有相关路径进入 permission cache 和 policy database（§4.3、图 5）。
  - **依赖假设**：capability-to-hook dictionary 对目标 kernel 和启用的 subsystem 是完备的；少一个 hook 不是性能退化，而可能成为安全绕过。
  - **可能失效场景**：kernel 升级改变控制流、hook inventory 或别名路径，但 mapping 没有同步更新。USEC 会在版本不匹配时拒绝编译，不过 mapping 的语义正确性仍需维护者保证。
- **观察 3：兼容问题常来自对未声明资源也执行严格策略**。显式 opt-in、permissive mode 和与其他 LSM 分离的状态，允许厂商先观察，再逐步给关键资源加保护（§3.3、§4.4）。
  - **依赖假设**：未声明资源依赖 DAC 是可接受的安全基线；“不破坏应用”优先于“默认覆盖所有对象”。
  - **证据强度**：中。论文给出两个迁移/配置案例和大规模采用数字，但没有兼容性应用全集或故障率。
- **假设 1：内核、LSM 框架和管理 TCB 可信**。威胁模型信任 `usecd`、`dbus-daemon`、`udevd` 与 audit infrastructure，只考虑能通过正常 kernel interface 发起访问的非特权或应用级攻击者（§4.1）。
  - **证据强度**：设计前提；论文不防 kernel compromise，也不自动发现被遗漏的关键资源。

## 核心方法

资源中心策略模型（resource-centric policy model）把每条 JSON 规则放在一个 resource descriptor 上，例如 file path prefix、device node、mount point、D-Bus interface 或 socket endpoint。规则列出资源属性、可用操作，以及获准 principal；principal 由 identity bitmap 表示。编译器把 JSON 变成紧凑的 bitmap 和 rule table，内核把实际对象规范化后查询。只有匹配到声明资源时才做 identity 与 operation 检查；没有规则就回退 DAC 和可选 audit（§4.2、图 4）。

这不是简单按 pathname 放行。对于受保护文件，USEC 尽量围绕 kernel object state 保持闭合：hard link、symbolic link、rename、file-descriptor passing、memory-mapped write 和 metadata update 都要落到能力相关 hook。以 FILE_READ 为例，字典会展开为 `read`、`open`、`getattr` 等 permission，并关联 `file_open`、`inode_permission`、`mmap_file`、`file_read`、`file_close`；文件完整性还要保留 `inode_setattr`、`inode_link` 和 `inode_rename`（§4.1、§4.3、表 1）。

按需执行（demand-driven enforcement）分两步缩小热路径。编译时，高层 capability 先映射到资源集合和操作，再按目标 kernel 的 inventory 求出所需 hook 并集，物化为全局 bitmap；编译器预期版本和 kernel 导出版本不同就拒绝生成。运行时，每个 hook 先做常数时间 bitmap membership test；bit 未设置就立即返回，设置后才调用 `check_usec_perm()`，先查 USEC 自己的 access-vector cache（UAVC），cache miss 才进入 policy engine（§4.3、§5）。

兼容接口（compatibility-oriented security interface）处理两类共存。对厂商自定义逻辑，LSM 先进入 USEC runtime dispatcher；厂商注册 hook 时，USEC 校验参数、返回类型和 function pointer 与原 LSM prototype 一致，再放入 mapping table 和 hook chain。对 SELinux 等标准 LSM，USEC 使用 stacking 和独立 security blob；`usec_state`、`upolicydb`、`usidtab`、`usec_uavc` 与 SELinux 的对应结构分开，加载或更新一方策略不会修改另一方 cache（§4.4、图 6、表 2）。

USEC 复用 SELinux 的 policy model、binary format、label syntax 和 on-disk extended attribute，便于导入已有策略，但把无关功能裁掉。对仍共享 `fs_context.security` 的旧 mount hook，它不用该字段保存自己的 option，而是按调用 task 放入私有内核列表，mount 完成时再应用。用户态由 `usecd`、`libusec` 生成和加载策略，`usecfs` 负责传入内核；实现共 82,412 行新代码，其中 kernel 19,223 行、用户态 63,189 行（§4.4–§5）。

策略接口虽然短，底层并不小。UOS V25 的部署实例中，USEC 使用 11 个 module 和 949 KB policy file，而对应 SELinux 为 320 个 module、2.1 MB；`file_contexts` rule 从 5,428 降到 1,577，`homedirs` rule 从 408 降到 65。这里体现的是“把常见保护模式做成模板并缩小声明范围”，不是删除内核中的授权逻辑（§1）。

## 设计取舍

- **显式保护换 complete mediation**：未声明对象不受 USEC 强制限制，减少误伤和开销；安全性却取决于 resource inventory 是否完整。USEC 更像 targeted hardening，而不是全系统默认拒绝的 SELinux 替代品。
- **高层 capability 换 mapping 维护**：管理员不必手写 hook，但系统维护者必须为每个 kernel/version 正确维护 capability dictionary；论文把这一点列为唯一主要人工工作。
- **简单策略接口换大型实现与审计面**：用户看到的是短 JSON，底层却包含 82k 行 kernel/user-space code、独立 policy database、cache、编译器和 dispatcher；其中哪些组件属于可信计算基仍需按部署划分，但整体维护面并不小。
- **缓存与在线更新换一致性复杂度**：UAVC 降低重复决策成本，但 policy hot update 必须正确失效旧 allow/deny。论文声称支持在线更新，没有单独评测并发更新窗口。
- **LSM stacking 换组合语义**：独立 state 避免内存纠缠，但一个请求仍可能同时经过 DAC、USEC、SELinux 和 vendor hook；denial 来自谁、顺序怎样、audit 如何归因，会增加运维难度。

## 实验与结果

- **策略配置与表达能力**：camera device 的 SELinux 最小可工作版本需要三个以上 attribute、跨 `.te`/`.if`/kernel module 的规则，总计超过 300 行；USEC 用两份合计少于 20 行的 JSON 定义 camera resource 和获准 application（§6.1.1、图 7–8）。对 AT-SPI 的 D-Bus interface/method，SELinux 需要把 interface string、object path、message type 和 attribute 重新拼起来，USEC 则直接写 bus type、interface、member list 和 operation（§6.1.2、图 9–10）。论文摘要另称等价需求下 policy code 最多减少 10 倍，但没有给出统一行数统计、编写时间或错误率。
- **评测环境与 UnixBench**：所有性能实验都在一台 AMD Ryzen 7 3700U（4 core/8 thread）、16 GB DDR4、512 GB SSD 的 HONOR 笔记本上运行 UOS Desktop 20 与 Linux 4.19；SELinux、USEC、AppArmor 被配置成相同高层保护目标，每项重复 10 次。UnixBench 综合分数从 LSM-disabled 的 3,993.15 降到 SELinux 的 3,681.53、USEC 的 3,875.07、AppArmor 的 3,864.81，对应下降 7.80%、2.96%、3.21%；这是偏 CPU 的宽泛基准，作者也只把它当背景证据（§6.2、表 3）。
- **Filebench**：五类 workload 汇总下降为 SELinux 10.86%、USEC 6.87%、AppArmor 9.51%。例如 webserver 为 baseline 91,029、USEC 88,909、SELinux 84,359 ops/s；但 Random Write 中 USEC 只有 45,610，低于 SELinux 的 52,736 和 AppArmor 的 53,507 ops/s，说明优势并非逐 workload 成立（§6.2、表 4）。
- **Nginx**：LSM-disabled、USEC、SELinux、AppArmor 吞吐分别为 96,350、92,185、84,748、81,775 req/s，即 USEC 相对 baseline 下降 4.32%，SELinux 下降 12.04%。USEC P50/P99 为 3.569/12.140 ms，SELinux 为 3.710/12.990 ms；AppArmor 的 P99 12.120 ms 略低于 USEC，但吞吐更低（§6.2、表 5）。
- **兼容案例**：一个案例用 APPID template 和 D-Bus identifier 为 calculator service 生成 SELinux-compatible rule；另一个把已有 SELinux binary policy subset 导入独立 `upolicydb`/`usidtab`，然后恢复 enforcing mode（§6.3、图 11–12）。论文展示了流程可行，没有给出应用通过率、denial 数或与原 SELinux 逐请求一致的测量结果。
- **部署事实**：作者报告超过 210 家安全厂商采用 USEC，包括 QiAnXin、360 和 NSFO-CUS；截至 2025 年初，超过 8,000,000 个企业 endpoint 已部署，涉及金融、能源与交通（摘要、§1）。这强力支持“可部署”，但论文没有提供安全事件、漏拦截率或 endpoint telemetry，不能把规模直接当成保护有效性的实验证据。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Resource-centric policy 能显著减少配置代码 | §1、§6.1、图 7–10 | UOS production count；camera 与 AT-SPI 两个案例，统计口径未统一 | 强 |
| 按需 hook 与 UAVC 通常比 SELinux 的全覆盖路径开销低 | 表 3–5：UnixBench、Filebench 汇总、Nginx | 单台 Linux 4.19 笔记本；策略由作者声明为相同高层目标；Random Write 有反例 | 中强 |
| 显式声明资源可得到闭合的强制保护边界 | §4.1–§4.3 的 capability expansion 与 alias hook 设计 | 依赖完整资源清单、正确 hook mapping、可信 kernel/管理 TCB；无攻击 corpus | 中 |
| USEC 可与 SELinux 共存并复用其策略 | §4.4、§6.3、图 11–12 | 两个流程型案例；未报告大规模 compatibility suite 或组合顺序故障 | 中 |
| USEC 已达到大规模生产可部署性 | 摘要、§1：210 多家 vendor、800 万以上 endpoint | 作者报告的采用规模；没有公开统计方法或运行质量指标 | 中强 |

## 批判性分析

### 论证链条

论文从三个痛点分别导出 resource-centric policy、capability-driven hook set 和 compatibility interface，再用配置案例、性能表与产业采用支撑，作为 Operational Systems 工作是完整的。最明显的逻辑跳步在“strong MAC”或“SELinux-level protection”：设计确实能保护被声明且 mapping 完备的资源，但实验没有证明两者在同一攻击集合上阻断相同行为；未声明资源本来就不在 USEC 的强保护边界内。

### 假设压力测试

系统把最危险的错误从“规则写得太严导致应用坏掉”转成“关键资源漏列后静默回退 DAC”。在 container namespace、overlay filesystem、bind mount、动态 device、IPC proxy 或 file descriptor 跨进程传递中，资源身份和必要 hook 更难枚举。论文说明 hard link、rename、mmap 等路径要闭合，但没有系统性证明 capability dictionary 对每个 kernel 都没有遗漏。注册接口校验 prototype 只能防 ABI 不匹配，不能证明 vendor hook 的语义正确或无副作用。

### 实验可信度

表 3–5 报告十次运行的平均值、标准差和 volatility，并加入 Filebench、Nginx 这类 MAC-sensitive workload，比只跑 UnixBench 更可信。可是硬件、OS 和 kernel 只有一个较旧配置；没有多核 server、新版 LSM stacking、container 或不同 capability-set 大小的扩展实验。所谓“相同保护目标”由作者配置，缺少公开 rule-to-rule coverage 检查。摘要中的 3.4%–17.1% 相对 SELinux 开销优势也无法从三个汇总 degradation row 直接重建，应以各表的原始数值为准。

### 系统性缺陷

每次 kernel 版本或 subsystem 改变都可能要求重建 hook inventory 和 mapping，version check 只能发现“版本不同”，发现不了“版本相同但 mapping 漏了控制流”。独立 USEC 与 SELinux state 增加内存、policy update、cache invalidation 和 audit attribution 的复杂度；82k 行实现也扩大了需要维护和安全审计的代码面。论文没有量化在线 policy update 的原子性、UAVC stale entry、dispatcher failure、多个 LSM 拒绝结果的可观测性，或管理 TCB 被攻陷后的 fail-safe 行为。

## 局限与后续工作

- **局限 1**：保护只覆盖显式声明的资源与 capability；资源遗漏不会触发 fail-closed。
- **局限 2**：性能只在单机 Linux 4.19/UOS Desktop 环境评测，不能直接外推到现代 server、container host 或不同 hook inventory。
- **局限 3**：兼容性只有两个案例，没有应用集合、升级矩阵、denial rate 或回归测试结果。
- **局限 4**：210 多家 vendor 与 800 万 endpoint 是采用证据，不是攻击阻断能力或策略完整性的独立验证。
- **后续工作 1**：建立 capability-to-hook coverage 测试：对 file、mount、namespace、D-Bus、socket 和 device 的别名/间接路径做 kernel fuzzing，并要求每个受保护 operation 都命中预期 hook。
- **后续工作 2**：在 Linux 4.19、5.15、6.x 与至少两种 container runtime 上运行同一 policy/attack corpus，对比 USEC 与 SELinux 的 allow/deny history，报告漏拦截、误拒绝和性能。
- **后续工作 3**：并发执行 policy hot update 与高频访问，检查 UAVC entry 是否在规定窗口内全部失效，并报告 stale allow 数为 0 的客观验收结果。
- **后续工作 4**：从实际 endpoint 采集匿名化的 shadow-mode coverage，量化未声明资源、policy conflict 和应用 denial，再验证自动提示能否降低配置遗漏率。

## 相关

- **相关概念**：[[Mandatory-Access-Control]]、[[Linux-Security-Modules]]、[[Least-Privilege]]、[[Access-Vector-Cache]]
- **相关系统**：[[SELinux]]、[[AppArmor]]、[[UOS]]
- **同会议**：[[OSDI-2026]]
