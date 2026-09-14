---
type: paper
name: USEC
full_title: "USEC: A User-Requirement-Driven Mandatory Access Control Framework for Operating Systems (Operational Systems)"
authors: [Yu Jiang, Wenhuan Liu, Fuchen Ma, Yuheng Shen, Yuanliang Chen, et al.]
venue: OSDI
year: 2026
tags: [mandatory-access-control, linux-security, lsm, selinux, policy-engineering, security-performance]
source_pdf: "[[osdi26-jiang-yu.pdf]]"
source_md: "[[osdi26-jiang-yu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-09-14
---

# 面向用户需求的 Linux 强制访问控制框架（OSDI 2026）

> **原题**：USEC: A User-Requirement-Driven Mandatory Access Control Framework for Operating Systems (Operational Systems)

> **一句话总结**：USEC 观察到 SELinux 的全覆盖钩子和进程/类型中心策略让部署成本、运行开销与兼容性难以接受，因此用资源中心的 JSON 策略、按能力裁剪的 LSM hook 集合和独立的缓存/状态实现选择性强制控制；在作者的测试中策略代码最多减少 10×，相对 SELinux 的开销降低 3.4%–17.1%，但其安全保证明确依赖于部署者完整声明所有关键资源。

## 问题与动机

Linux 的强制访问控制（Mandatory Access Control, MAC）能在内核层限制被攻陷进程访问文件、设备、IPC 和网络资源。论文认为，SELinux 等成熟方案在真实企业环境中常被关闭，主要原因不是安全目标不重要，而是策略难写、全路径检查成本高、严格策略容易破坏已有应用。

论文将问题拆成三部分：管理员需要以资源和应用能理解的方式表达“谁能读写某个高价值资源”；不相关的系统调用路径不应承担完整 MAC 引擎的固定成本；部署过程中还需要在不改变现有 SELinux 或应用行为的情况下逐步启用保护。USEC 的目标不是覆盖所有内核对象，而是在明确声明的资源集合上提供封闭的强制保护边界。

## 关键观察 / 隐含假设

- **观察 1：资源保护意图与 SELinux 的类型/域规则不匹配。** 摄像头设备案例中，SELinux 需要属性、类型、接口文件和多个规则片段，最小可用配置超过 300 行；USEC 用少于 20 行 JSON 表达同一控制目标（图 7–8）。
  - **依赖假设**：厂商主要想保护少量明确的高价值资源，而不是为所有进程建立完整的全局安全格局。
  - **可能失效场景**：若策略需要复杂的跨资源关系、动态状态约束或信息流控制，资源中心模型可能需要重新引入复杂的主体关系，优势会缩小。
- **观察 2：MAC 开销集中在实际经过安全相关路径的工作负载。** 在 UnixBench 中 SELinux 只造成 7.80% 的综合分数下降，但 Filebench 聚合下降 10.86%，Nginx 中吞吐下降更明显；这支持将检查集中到文件、socket、IPC 等真正相关的路径（表 3–5）。
  - **依赖假设**：能力到 hook 的映射能够完整覆盖受保护资源的所有读写、元数据、别名和间接访问路径。
  - **可能失效场景**：内核版本、启用的子系统或用户态栈变化时，同一高层能力可能依赖不同 hook；错误或过时的映射会形成安全盲点。论文通过版本匹配拒绝过时映射，但仍需维护映射字典。
- **假设 1：部署者能正确枚举安全关键资源。** USEC 不会自动推断遗漏的关键资源；未声明资源直接回退到 DAC 和可选审计。该假设是“低侵入兼容性”的来源，也是安全保证的主要边界，证据强度为强：威胁模型在 §4.1 明确排除了自动发现遗漏资源。
- **假设 2：Linux LSM、内核完整性及小型管理 TCB（如 `usecd`、`dbus-daemon`、`udevd`）可信。** USEC 的保证建立在这些组件不被攻陷且 LSM 正常工作的前提上，证据强度为强（§4.1）。

## 核心方法

USEC 将策略锚定在资源而非进程域：每个 JSON 条目描述文件路径前缀、设备节点、挂载点或 socket endpoint，并列出允许的 principal 与操作。principal 被编码为 identity bitmap；内核先构造资源描述符并查找紧凑规则表，只有命中显式保护资源时才执行 bitmap 和操作检查（§4.2）。未命中时不进入 USEC 策略路径，从而保留 DAC 语义。

策略编译器把高层 capability 同时展开为策略引擎权限和所需 hook。例如 `FILE_READ` 会展开为读、打开、属性查询等权限及对应的 `file_open`、`inode_permission`、`mmap_file` 等 hook；所有 capability 的 hook 集合取并集，最终用全局 bitmap 表示保留集合（图 5、表 1）。每个 hook 先做常数时间 bitmap 测试，未启用的 hook 立即返回，启用的 hook 才调用 `check_usec_perm()`。

为避免与既有 MAC 冲突，USEC 使用独立的 `usec_state`、策略数据库和 UAVC（USEC-specific AVC），并遵循 LSM stacking 的 blob 机制。它复用 SELinux 的策略格式和标签约定，但不共享内部策略状态，因此可以与 SELinux 并行运行（§4.4、表 2）。对旧式 mount 路径的共享字段，USEC 使用按任务索引的私有列表保存自身状态。

系统还提供 permissive/shadow 式部署流程和模板：管理员可通过应用标识、D-Bus 配置及资源描述生成兼容 SELinux 语义的规则，先观察潜在拒绝，再启用严格执行（图 11–12）。实现规模为内核 19,223 行、用户态 63,189 行，共 82,412 行新代码（§5）。

## 设计取舍

- **显式范围换取部署可行性**：未声明资源不受 USEC 的强制控制，因此不会因默认策略破坏应用，但安全性依赖资源枚举完整性。
- **能力驱动的 hook 裁剪换取性能**：减少无关路径开销，同时引入按 kernel version、子系统和软件栈维护 capability-to-hook 字典的工程负担。
- **复用 SELinux 格式换取迁移能力**：可以导入已有二进制策略并保持标签兼容，但实现仍携带 SELinux 策略模型的一部分复杂度，且论文没有证明对所有 SELinux 特性都能等价迁移。
- **资源中心抽象换取表达简洁**：对摄像头和 AT-SPI/DBus 这类明确资源很有效；对复杂主体关系、动态策略和全系统信息流约束的表达能力，论文未充分评估。

## 实验与结果

- 摄像头控制：USEC 用少于 20 行 JSON 完成控制；对应 SELinux 最小配置超过 300 行，并跨多个文件（图 7–8）。
- UnixBench：10 次运行中，LSM-disabled 分数为 3,993.15，SELinux 为 3,681.53（下降 7.80%），USEC 开销 2.96%，AppArmor 开销 3.21%（表 3）。
- Filebench：五个文件系统工作负载聚合下降分别为 SELinux 10.86%、USEC 6.87%、AppArmor 9.51%；例如 webserver 中 USEC 88,908.51 ops/s，SELinux 84,359.23 ops/s，基线 91,029.30 ops/s（表 4）。
- Nginx：USEC 平均 92,185.08 req/s，相对 LSM-disabled 吞吐下降 4.32%；SELinux 为 84,748.05 req/s，下降约 12.04%；USEC P50/P99 延迟为 3.569/12.140 ms，SELinux 为 3.710/12.990 ms（表 5）。
- 测试平台为 4 核 AMD Ryzen 7 3700U、16 GB 内存、Linux 4.19 的 UOS Desktop 20；每项实验重复 10 次。作者还报告 USEC 已被超过 210 家安全厂商采用，并在早期 2025 年部署到超过 800 万企业端点，但这些规模数据主要是部署报告而非可复现实验（§1、§6.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| USEC 能以显著更少的策略代码表达部分资源控制需求 | 摄像头实验图 7–8；引言中的 UOS 策略规模对比 | 两个代表性场景，未覆盖复杂全局策略 | 中 |
| 按需保留 hook 可降低 MAC 运行开销 | UnixBench、Filebench、Nginx 表 3–5 | 单一笔记本、Linux 4.19、有限工作负载 | 中 |
| USEC 能与 SELinux 并存并导入其策略格式 | §4.4、图 12 的策略迁移流程 | 展示了策略子集与测试服务，未证明所有 SELinux 特性 | 中 |
| USEC 的安全边界覆盖所有已声明资源的相关访问路径 | capability-to-hook 编译流程、版本检查、§4.1 威胁模型 | 映射字典和部署者枚举正确是前提，缺少形式化验证或全面攻击评测 | 中 |

## 批判性分析

### 论证链条

论文从“企业关闭 SELinux”的三个原因出发，分别给出资源中心策略、按需 hook 和兼容接口，整体设计链条是闭合的。实验也覆盖了策略规模、吞吐和兼容性迁移。不过“更简单”主要由两个案例支撑，“强保护”则更多依赖设计描述和导入策略的演示；论文没有给出系统性的攻击路径覆盖、遗漏资源检测率或与完整 SELinux 策略的等价性证明。

### 假设压力测试

USEC 的核心不是全局 MAC，而是对显式声明资源的闭保护。如果攻击者通过未声明的中间资源间接影响目标，USEC 是否仍能阻断，取决于部署者是否把所有相关对象和操作加入 capability 集合。作者考虑了 hard link、symbolic link、rename 和 file descriptor passing 等路径，但没有在大规模真实应用 trace 上量化遗漏风险。

hook 裁剪也有明显的版本和配置依赖。作者在 §7 承认最初的通用映射过于粗糙，并改用 kernel-aware 编译；这提高了可信度，却意味着每个 kernel family 和产品栈都需要持续维护映射。实验平台较旧且只有单台 4 核笔记本，无法直接外推到多核服务器、容器/虚拟机密集环境或新内核 LSM 实现。

### 实验可信度

Filebench 和 Nginx 比纯 CPU 基准更贴近 MAC 热路径，且重复 10 次并报告波动，比较方向合理。可是“相同安全要求”的策略构造细节有限，尤其 SELinux、AppArmor 与 USEC 的策略覆盖是否完全等价难以仅凭正文核验。兼容性部分主要是案例和策略迁移流程，而不是大量应用、故障率或运维成本统计。800 万端点和 210 家厂商是重要部署信号，但缺少独立审计、版本分布和失败案例数据。

### 系统性缺陷

论文未充分讨论 USEC 策略更新期间的一致性、回滚、故障恢复和可观测性；也未量化 UAVC 内存占用、规则查找在大策略下的扩展性以及多租户隔离。独立管理 TCB（尤其 `usecd`、D-Bus 和审计设施）扩大了必须保护的运维边界。与 SELinux 共存虽然避免共享策略状态，但可能产生双重拒绝、诊断困难和 hook 顺序相关的问题，论文只展示了有限场景。

## 局限与后续工作

- **局限 1：保护范围依赖人工声明。** 后续可在真实安装、更新和运行 trace 上评估资源枚举的召回率，并给出遗漏关键资源时的可检测性指标。
- **局限 2：能力到 hook 的映射需要内核版本维护。** 可验证方向是建立自动化内核路径覆盖测试：对每个 capability 生成系统调用、别名操作和间接访问测试，并检查所有路径是否命中预期 hook。
- **局限 3：实验规模和平台较窄。** 应在新内核、多路 CPU、容器、虚拟机、网络设备和高并发服务器上测量吞吐、P99/P999、规则规模和 UAVC 内存成本。
- **局限 4：复杂策略表达能力尚不清楚。** 应与 SELinux 的 RBAC、约束、类型转换、信息流和动态布尔策略建立逐项表达能力与迁移成功率对照，而不只比较资源型案例。

## 相关

- **相关概念**：[[Linux Security Modules]]、[[SELinux]]、[[AppArmor]]、[[Mandatory Access Control]]
- **同类系统**：[[Smack]]、[[TOMOYO]]、[[Yama]]
- **同会议**：[[OSDI-2026]]
