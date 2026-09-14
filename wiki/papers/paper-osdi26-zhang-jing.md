---
type: paper-report
name: vBPF
full_title: Virtualizing eBPF with Late-Binding
authors: [Jing Zhang, Xiaguannan Song, Dong Du, Yubin Xia, Binyu Zang, Haibo Chen]
venue: OSDI
year: 2026
source_pdf: "[[osdi26-zhang-jing.pdf]]"
source_md: "[[osdi26-zhang-jing]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-13
---

# 用晚绑定实现 eBPF 虚拟化（OSDI 2026）

> **原题**：Virtualizing eBPF with Late-Binding

> **一句话总结**：论文观察到原生 eBPF 把租户程序静态绑定到全局 hook，导致 singleton 冲突、状态污染和无关程序广播执行；vBPF 用资源级事件归属、按命名空间哈希分发和编译器辅助状态隔离实现晚绑定，在跨租户场景下将 lmbench 高频系统调用延迟降低最多 3.9×，并使 PostgreSQL 吞吐提升 29%。

## 问题与动机

云平台通常由平台管理员加载可信 eBPF 程序，但让租户加载自己的程序可以实现应用感知的调度、网络、存储和观测优化。问题在于 Linux eBPF 的抽象默认只有一个信任域：程序在加载时绑定到物理 hook，事件触发时执行固定的全局程序集合。

这种静态绑定造成三类冲突。基于 `struct_ops` 的 singleton hook 只能由一个实现占用；多个程序共享同一个执行上下文，可能修改报文或 kprobe 返回值而破坏其他租户；即使程序与事件无关，也会被调用并执行过滤逻辑。论文以 TC 重定向循环和 `getpid` 测试说明，两个各自合法的程序组合后可能破坏正确性，单个无关 tracing 程序也会显著拖慢系统调用。

已有方案分别依赖租户自行过滤、cgroup 上下文、平台集中编排或加载时拒绝冲突程序。它们不能同时覆盖中断上下文、singleton hook、运行时低开销分发和内核状态隔离。

## 关键观察 / 隐含假设

- **观察 1：中断事件通常携带稳定的资源身份，而不是可靠的进程身份。** 网络包、块 I/O 完成事件分别可通过连接五元组或 request/bio 关联到先前在进程上下文中建立的资源（§4.1、图 4）。
  - **依赖假设**：资源创建或初始化路径能够被覆盖，且资源标识在异步处理期间可用。
  - **可能失效场景**：资源被合并、拆分、迁移或复用时，映射生命周期和 namespace 集合传播必须保持正确；没有明确租户归属的 IPI、热插拔等硬件事件只能归入 host。
- **观察 2：eBPF 程序只通过 verifier 可见的 helper/kfunc 边界访问内核状态。** 这使编译期默认拒绝不安全接口成为可能（§4.3）。
  - **依赖假设**：不存在绕过这些边界的可利用路径，且内核开发者会正确标注允许修改全局状态的接口。
  - **证据强度**：中。原型基于 helper 和 verifier 类型信息；论文明确说当前实现尚未完整覆盖 kfunc。
- **观察 3：多租户分发的瓶颈不是程序执行本身，而是为找到目标程序而线性检查所有租户程序。** 160 个 kprobe 程序的测试中，哈希索引使跨租户路径保持平坦，而原生执行和手工条件过滤随程序数线性恶化（图 11b）。
  - **依赖假设**：namespace 查找可以稳定地 O(1) 完成，且单一租户内部程序链长度有限。

## 核心方法

vBPF 在物理 hook 上只安装一个轻量的 virtual hook multiplexer。它先确定事件所属的 eBPF namespace，再晚绑定到该 namespace 的逻辑程序集合，而不是把每个租户程序直接挂到全局 hook 上。vBPF namespace 采用层次结构，可通过 `clone`、`unshare` 和 `setns` 与容器运行时集成；父 namespace 可以观察子 namespace，支持平台审计。

**Snifer** 解决中断上下文中的归属问题。进程上下文阶段在 `bind()`、`connect()` 或 I/O 提交等路径记录“资源—namespace”映射；中断阶段从 `xdp_md`、`sk_buff` 或 request 中提取统一 key 并查询映射。网络、存储和 task teardown 分别使用专门 sniffer。这个设计回应了观察 1，但将正确性责任转移到资源生命周期处理。

**Dispatcher** 用 namespace keyed hash table 直接定位租户入口，再遍历该租户的连续程序数组。对于需要父 namespace 观察子 namespace 的 tracing 场景，系统把从当前 namespace 到 root 的调用链预计算成数组；运行时只需按 bottom-up 顺序迭代。父程序可以看到修改后的上下文，并覆盖子程序的返回码。

**State Isolation Framework** 分两层工作。静态分析器对 helper/kfunc 做 taint 分析，默认拒绝会修改全局状态的接口，并要求 `vbpf_safe` 显式放行；同时利用 verifier 的指针类型识别租户私有栈、local map 和只读区域。变量库用声明式 API 将普通全局变量映射为 per-namespace 实例；对不能复制的复杂对象，则基于 BTF 反射生成语义 patch，在 namespace 切换时应用和恢复。热路径使用预解析的字段 offset，支持整对象 capture 或字段级 update。

## 设计取舍

- **晚绑定换取隔离，代价是 hook、资源生命周期和 namespace 管理的内核改造。** 原型包含约 12K 行内核代码和 1K 行 Clang 插件。
- **路径扁平化用内存换关键路径延迟。** namespace 或父程序更新时必须原子维护预计算数组。
- **状态 overlay 避免页表切换的高成本，但并非所有状态都适合虚拟化。** 修改频繁或结构复杂的对象会增加 patch 内存；全局 timer 等资源仍应对租户保持不可变。
- **默认拒绝提升安全性，依赖内核维护者审计。** 错误的 `vbpf_safe` 标注可能重新引入跨租户副作用。

## 实验与结果

- 在 Xeon Gold 6330、512 GB DRAM、Linux 6.12、LLVM 20 上，vBPF 与原生 eBPF 共置时额外延迟最高为 syscall 4.81%、`select` 5.18%、进程创建 3.39%、网络 2.51%（§6.1）。
- 跨租户 lmbench 中，NULL call、read、write 延迟分别为 0.258、0.319、0.288 μs，相比原生 eBPF 分别降低 3.7×、3.8×、3.9×；RPC/UDP、RPC/TCP 和 TCP/IP 延迟改善 1.4–1.5×（图 8、图 9）。
- tcx tracing 分解显示 Snifer resolve 约 134–136 ns、namespace lookup 32–33 ns、program lookup 60–74 ns；相对于 1135 ns 的基础 tcx 程序，vBPF 额外开销约占 2.1%（图 10）。
- 160 个 kprobe 程序竞争 `sys_read` 时，跨租户 vBPF 相比原生 eBPF 最多 54×，相比手工条件过滤最多 11.4×（图 11b）。
- PostgreSQL tracing 场景吞吐提高 29%、延迟降低 23.6%；Apache 配合 netobserv 时吞吐最高提高 2.8×（图 12、图 13）。
- `sched_ext` 案例中，原生 `scx_central` 使 7z 提升 10%，却使 Redis 吞吐下降 18%；vBPF 只对 7z 使用该调度器，同时保持 Redis 接近 vanilla Linux（图 14）。
- State overlay 对常见 `sk_buff` 和 `file` 的 capture 延迟为 118.8 ns 和 100.9 ns，apply/restore 约 42–44 ns；预计算布局最多降低 31.4× 开销（图 15）。Snifer registry 是主要内存成本，Apache 和 fio 峰值约 39 MB，而 PostgreSQL 仅 11.6 KB（表 3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| vBPF 能避免无关租户执行并降低关键路径延迟 | lmbench NULL/read/write 结果（图 8） | 单机 Xeon、sysdig、选定 syscall 和网络 workload | 强 |
| 哈希分发能随租户密度扩展 | Snifer/Dispatcher 延迟 131.7–136.6 ns、lookup 58.3–60.7 ns（图 11a） | namespace 数量 10–100；未覆盖更大生产规模 | 中 |
| 晚绑定能同时提供应用定制与性能隔离 | PostgreSQL、Apache、sched_ext（图 12–14） | 特定 monitor、工作负载、CPU 划分和单机环境 | 强 |
| 状态隔离的成本可接受 | overlay 操作延迟与内存表（图 15、表 3） | 只修改一个字段；高频复杂对象更新未充分评测 | 中 |

## 批判性分析

### 论证链条

从静态绑定导致广播执行，到运行时按 namespace 分发，再到跨租户性能恢复，主论证链条是闭合的。实验也覆盖了微基准、真实 tracing 和 `sched_ext`。但“通用 eBPF 虚拟化”的结论仍依赖 Snifer 对资源类型的覆盖，以及状态 overlay 对可修改内核对象的适配；论文没有证明任意 hook 或任意 kfunc 都能自动纳入该模型。

### 假设压力测试

网络五元组、I/O request 和 task 映射适合论文选择的场景，但 NAT、连接迁移、多路径网络、request merge/split 和资源复用会增加映射歧义。论文提到这些问题并给出 namespace set 传播，但没有端到端故障注入或长期 churn 实验。父 namespace 的 bottom-up 链条也可能使平台审计程序重新成为所有租户的共同成本。

### 实验可信度

基线包含 vanilla Linux、原生 eBPF 和手工过滤，能够分离隔离收益与 vBPF 固定开销；消融和 breakdown 也支持 Dispatcher/Snifer 的设计分解。限制是硬件、内核版本和 monitor 选择较窄，主要 workload 没有覆盖高并发 namespace churn、真实多租户 trace、复杂 kfunc 写入或故障恢复。内存实验只修改一个字段，不能代表密集 overlay。

### 系统性缺陷

Snifer registry 的空间随活跃资源映射增长，Apache/fio 已达到约 39 MB；大规模短生命周期连接可能需要更强的回收和配额机制。状态一致性目前假设相关访问已有锁保护，论文明确未充分处理 RCU reader。静态分析器和变量注解增加内核版本升级的维护工作；可观测性、恶意资源耗尽、namespace 销毁竞态及 verifier/JIT 失效后的隔离边界也未被完整评估。威胁模型不覆盖管理员、内核/verifier/JIT 漏洞、硬件故障和微架构侧信道。

## 局限与后续工作

- **局限 1**：当前实现主要围绕 helper，kfunc 的稳定性和完整状态审计尚未验证。
- **局限 2**：RCU 读者、复杂共享对象和高频写入下的 overlay 一致性仍是开放问题。
- **局限 3**：Snifer 需要针对资源类型编写提取与生命周期逻辑，难以宣称完全通用。
- **后续工作 1**：在真实 Kubernetes 多租户 trace 上测量 namespace churn、映射回收、尾延迟和 registry 配额，并注入连接迁移及 I/O merge/split 情况。
- **后续工作 2**：建立覆盖 kfunc 的自动化状态摘要与审计工具，量化错误注解、RCU 访问和复杂对象 overlay 对安全性的影响。

## 相关

- **相关概念**：[[eBPF]]、[[Linux Namespace]]、[[BTF]]、[[RCU]]、[[sched_ext]]
- **同类系统**：[[Cilium]]、[[KRAKENGUARD]]
- **同会议**：[[OSDI-2026]]
- **代码**：[vBPF artifact](https://github.com/vbpf-osdi-2026)
