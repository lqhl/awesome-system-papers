---
type: paper
name: Try
full_title: Controlling Opaque-Component Effects with Semisolates and Try
authors: [Evangelos Lamprou, Tianyu (Ezri) Zhu, Di Jin, Grigoris Ntousakis, Georgios Liargkovas, Calvin Eng, Konstantinos Kallas, Michael Greenberg, Nikos Vasilakis]
venue: OSDI
year: 2026
tags: [sandboxing, filesystem, effect-control, shell, software-safety]
source_pdf: "[[osdi26-lamprou.pdf]]"
source_md: "[[osdi26-lamprou]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用 Semisolate 控制不透明组件的副作用（OSDI 2026）

> **原题**：Controlling Opaque-Component Effects with Semisolates and Try

> **一句话总结**：不透明命令既要读取当前环境，又可能留下不想要的修改；`try` 用 semisolate 把文件系统副作用暂存在 [[OverlayFS]] 层中，让用户检查、隐藏、叠加、选择提交或丢弃，五类用例中提交后的输出和文件系统副作用与直接执行一致，相对直接执行慢 1.0–8.3 倍、相对 Docker 快 1.1–225.7 倍，但它只处理日常失误，不是抵御主动恶意程序的安全沙箱。

## 问题与动机

开发者经常要运行自己并不了解内部实现的组件，例如安装脚本、第三方 package hook、shell pipeline，以及由 [[LLM]] 生成的命令。这些组件必须看到当前机器上的源码、配置和工具链才能正常工作；直接运行却会立刻修改真实文件系统，错误删除、覆盖或权限变更往往很难撤销。

完整容器解决的是“建立一个新环境并隔离它”，不完全适合这里的问题。把当前环境复制进容器、执行、再复制结果出来有额外成本，而且下一条命令也不容易继续看到上一条尚未提交的修改。各命令自己实现的 `--dry-run` 又不统一，有时只打印计划，不能忠实显示真实执行会产生的所有副作用。

论文因此提出半隔离环境（semisolate）：组件仍看到当前环境的内容，但写入先进入一个私有视图，调用者再决定哪些效果进入真实环境。目标是控制正常软件和误操作的外部效果；§2.2 明确把“完整中介主动、了解 `try` 的恶意组件”排除在外，因此不能把它当作强 [[Sandboxing|安全沙箱]]。

## 关键观察 / 隐含假设

- **观察 1**：LLM 命令、依赖跟踪、第三方 hook、通用 dry-run 和 specification mining 看似不同，实际都需要四种操作：检查效果（I）、提交或丢弃（A）、叠加未提交效果（S）和进一步操纵效果（M）（§2、表 2）。
  - **依赖假设**：这些场景中最重要且可恢复的外部状态主要表现为文件路径和文件系统修改。
  - **可能失效场景**：命令已向远端 API 发消息、更新数据库、控制设备或与外部进程交互时，只回滚本地文件并不能回滚真实世界的效果。
- **观察 2**：用户需要的是“在当前环境中试运行”，不是“在空白环境中重建运行条件”；未提交层还要能被后续命令读取（图 1、图 2）。
  - **依赖假设**：OverlayFS 的 lower/upper/whiteout 语义足以表示常见的创建、修改、删除和层叠操作。
  - **可能失效场景**：复杂 submount、pseudo-filesystem、物理设备和某些不支持 OverlayFS 的文件系统会改变这一透明性。
- **观察 3**：只跟踪 `open` 及带路径的系统调用，通常已经能恢复有用的读写依赖；不存在路径的失败访问也必须作为负依赖记录（§4.2）。
  - **依赖假设**：调用者选择的 Seccomp-BPF filter 覆盖了工作负载真正关心的效果。
  - **可能失效场景**：经继承文件描述符、`mmap`、`ioctl` 或自定义 IPC 发生的行为，可能需要额外 filter，默认 trace 并不保证完整。
- **假设 1**：操作者能看懂并正确选择要提交的效果。
  - **证据强度**：中弱。附录 B 有真实使用者案例，但论文没有做受控用户实验；§6 也承认效果过多会淹没用户，并另做了 LLM 驱动的 `try-summarize`。

## 核心方法

Semisolate 有三个阶段。创建阶段建立组件的私有环境视图；执行阶段运行原命令并收集效果；结束阶段让调用者检查、保存、提交或丢弃这些效果。默认控制整个子进程树，所以被包装命令启动的子命令也在同一效果范围内。`-i` 可在初始视图中隐藏路径，`-x` 可关闭网络，`-t` 记录有顺序的文件访问和失败访问。

文件系统视图以 [[OverlayFS]] 实现：真实环境是只读 lower layer，命令的写入进入 upper directory，删除用 whiteout 表示。由于 OverlayFS 不允许根目录与工作目录重叠，`try` 为 `/etc`、`/usr`、`/home` 等顶层目录分别建 mount；如果 upper directory 本身位于 OverlayFS 上，就先加一层 `tmpfs`。遇到 submount 时，再用 `mergerfs` 把目录展开为单一视图（§4.1）。这些处理提高兼容性，也构成固定的启动成本。

`try` 通过 user、mount、PID 和 network [[Linux-Namespaces|namespace]] 在无特权用户下建立这些 mount，并让组件获得 namespace 内的 root-like 权限。执行时可用 `strace` 观察效果，再由 Seccomp-BPF 只捕获预设的 `open`、`mkdir`、`unlink` 等调用；默认不跟踪每一次 `read` 和 `write`，以降低热路径开销。调用者可以增加 filter，补充已打开文件描述符上的操作。

结束时，`try` 递归解释 upper directory：普通文件替换真实文件，目录、符号链接和 opaque 标记按 OverlayFS 规则处理，whiteout 转为删除。`-y` 全部提交，`-n` 全部丢弃，`-e` 逐项检查，`-E` 和 `-I` 按规则过滤。选择性提交可能破坏依赖，例如只创建文件却不创建其父目录；此时 `try` 像 `mv` 一样警告，并保留 semisolate 供用户重新选择，而不是提供事务性提交。

未提交效果还可以跨命令使用。`-N` 把一个 semisolate 保存为命名层，下一次执行用 `-L` 把它加入 lower layers。后续命令看到的是“上一条命令似乎已经发生”的文件系统，但真实主机仍未改变；图 2 展示了隐藏路径、保存层、叠加层和最终应用的完整过程。

## 设计取舍

- **保留当前环境，牺牲强隔离**：组件无需重新打包，兼容现有工具链；代价是 semisolate 本来就不是针对主动攻击者的完整容器边界。
- **真实执行，牺牲原生 dry-run 的速度**：得到的是命令实际产生的修改，不依赖每个工具自己模拟；但工作本身仍会执行，无法像只打印计划的 `--dry-run` 那样便宜。
- **选择性 trace，牺牲默认完备性**：过滤少量系统调用降低开销；依赖挖掘是否完整取决于工作负载和 filter。
- **逐项提交，牺牲原子性**：用户能保留一部分结果，但跨文件不变量、并发主机写入和提交中途崩溃都没有事务保证。
- **Linux 内核机制换透明接入**：不修改被包装组件，但依赖 unprivileged user namespace、OverlayFS、mount 行为和特定的 pseudo-device 处理，跨 OS 可移植性有限。

## 实验与结果

- 表 2 覆盖 25 个 benchmark、五类用例；所有 `try -y` 运行的输出和文件系统副作用均通过人工检查或整棵文件树 checksum 与直接执行一致。各测试相对 vanilla 的运行时间为 1.0–8.3 倍，相对 Docker 快 1.1–225.7 倍；Docker 包含建容器、复制输入、执行、复制输出和清理，因此最大速度差主要反映复制与启动开销（§5）。
- 五个 ChatGPT 生成的 shell script 处理最多 100 万个文件或 1000 万行输入时，`try` 相对 vanilla 慢 1.1–1.9 倍、相对 Docker 快 1.3–225.7 倍；五个依赖跟踪程序相对 vanilla 为 1.0–1.7 倍、相对 Docker快 1.1–18.7 倍（§5.1–§5.2、表 2）。
- 五个带风险 pre-commit hook 的第三方仓库中，隐藏 `/etc/passwd` 后输出与文件副作用仍匹配预期；`try` 相对 vanilla 最多慢 1.3 倍、相对 Docker 快 1.4–4.2 倍。`frogmouth` 和 `kibble` 因危险工作被阻止，运行时间反而是 vanilla 的 0.8 和 0.9 倍，但这不等于对主动恶意代码的安全评估（§5.3）。
- 五种原生 dry-run 的平均时间为 0.03 秒，真实执行后丢弃的 `try` 平均为 0.26 秒，慢 4.9–82.6 倍；它仍比同配置 Docker 快 1.2–3.2 倍，并捕获了 `rsync` 原生 dry-run 之外的日志副作用（§5.4、表 2）。
- 微基准中，空 `echo` 总时长 165 毫秒，其中建立 OverlayFS 用 42 毫秒、建目录用 37 毫秒；创建 10,000 个 16 字节文件时，退出 namespace 并扫描 upper directory 用 6.3 秒，说明短命令和海量小文件是明显弱点（§5.6、图 3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| semisolate 能在当前环境中暂存、叠加并选择应用文件效果 | 图 2 给出四次调用的隐藏、保存、叠加与提交状态变化；表 2 的 25 个测试均通过输出和副作用等价检查 | Linux 用户态命令与作者配置的文件系统效果 | 强 |
| `try` 通常比为每次命令建立完整 Docker 环境更轻 | 表 2：相对 Docker 快 1.1–225.7 倍 | Docker baseline 包含复制输入输出，最大值不代表所有容器用法 | 强 |
| 效果控制会带来可观的、与工作负载有关的开销 | 表 2：相对 vanilla 为 1.0–8.3 倍；图 3：10,000 小文件的 namespace 退出为 6.3 秒 | 25 个 benchmark，没有生产分布或长期并发运行 | 强 |
| 默认系统调用 trace 足以支持有用的依赖与规格挖掘 | §5.2、§5.5 中结果匹配已有 PaSh 规格，并发现三个遗漏 | 只测所选程序；已打开 fd 和其他 IPC 需额外 filter | 中 |
| 人可以可靠审查并选择大量副作用 | §6 与附录 B 提供若干使用者经历 | 无受控用户研究，且作者承认效果列表会淹没用户 | 弱 |

## 批判性分析

### 论证链条

论文最扎实的部分不是“又一个轻量容器”，而是把五类需求归纳成同一个效果控制接口：先让命令读取真实环境，再暂存修改，最后把检查、叠加和选择应用变成外层命令可以组合的操作。OverlayFS 和 namespace 证明该抽象能用于完全不修改的 Linux 程序，表 2 再验证一批代表性命令的最终文件效果。

论证的边界也很清楚：实验支持的是“所选文件系统效果可以受控”，不是“任意外部效果都可逆”，更不是安全隔离。论文有时用 broader environment 描述 semisolate，但当前实现和主要评测仍以文件系统为中心；网络、消息 API、数据库写入和设备操作没有同等的提交协议。

### 假设压力测试

主动、了解 `try` 的组件可以尝试利用未覆盖的 syscall、共享服务或设备；这正是论文明确排除的威胁模型。即使没有攻击者，继承 fd、复杂 `mmap`、hard link、xattr、FUSE/NFS、bind mount 和并发主机写者都可能让“初始视图—upper layer—最终主机”之间的关系变复杂。论文没有用系统化 POSIX 或文件系统一致性测试覆盖这些角落。

选择性应用还把语义判断交给用户。两个文件可能必须一起更新，或后一个 effect 依赖前一个 effect；`try` 只在底层操作失败时警告，无法知道应用级不变量是否已破坏。保留 semisolate 允许重试，但不能撤销已经部分写回主机的状态。

### 实验可信度

评测覆盖脚本、build dependency、第三方 hook、dry-run 和 specification mining，且没有把异质测试硬凑成 geometric mean，这一点合理。最终文件树 checksum 比只比较 stdout 更强，artifact 和真实使用者案例也增加可复现性。

不足是 Docker 与 `try` 解决的环境访问方式不同：Docker 测试复制输入和输出，而 `try` 直接读取主机，因此 225.7 倍主要说明该打包方式很贵，不能外推为普遍的容器性能优势。实验也没有测并发修改、提交崩溃、权限角落、安全逃逸或用户审查错误；“等价”主要是最终文件树等价，不等于所有中间行为和外部交互都等价。

### 系统性缺陷

首先，提交不是 journaled transaction；大量效果写回一半时崩溃，可能留下难恢复的混合状态。其次，user namespace 内的 root-like 身份会绕过普通可写权限，某些以 UID 或权限判断行为的程序会走不同分支；进程也不能切换到其他用户。PID 和 user namespace 还形成无法关闭的 signal/IPC 屏障。

最后，可观察性本身可能成为瓶颈。`node_modules`、编译树或数据生成任务会产生数万项效果，逐项确认并不现实；外部 `try-summarize` 用 LLM 压缩列表，又引入漏报敏感修改的新风险。论文没有给出 effect provenance、风险分级、设备超时、审查策略版本化或跨平台实现。

## 局限与后续工作

- **局限 1**：当前实现主要控制 Linux 文件系统效果，不保证远端 API、数据库、设备和任意 IPC 可回滚，也不抵御主动恶意组件。
- **局限 2**：OverlayFS、user/PID namespace 会改变权限、身份和进程交互语义；部分 hardened Linux 环境会禁用 unprivileged user namespace。
- **局限 3**：选择提交不是原子事务，并发主机写入和提交中途故障没有冲突检测或恢复协议。
- **后续工作 1**：加入 write-ahead journal，在 1、100、10,000 个效果规模下做每个提交点的 crash injection，验证恢复后主机状态只能是提交前或提交后之一。
- **后续工作 2**：用 xfstests/POSIX corner case 加并发 writer 覆盖 rename、hard link、xattr、`mmap`、FUSE/NFS 和 inherited fd，并公开漏捕获矩阵。
- **后续工作 3**：为 HTTP、数据库和消息 API 设计可插拔的 prepare/commit handler；不能事务化的操作应在执行前阻断并给出明确原因。
- **后续工作 4**：对 10,000 项以上效果做盲测用户实验，比较原始列表、规则摘要和 LLM 摘要的敏感修改漏报率与审查时间。

## 相关

- **相关概念**：[[Sandboxing]]、[[OverlayFS]]、[[Linux-Namespaces]]、[[Effect-System]]、[[Speculative-Execution]]
- **同类系统**：[[Docker]]、[[Podman]]、[[strace]]
- **同会议**：[[OSDI-2026]]
