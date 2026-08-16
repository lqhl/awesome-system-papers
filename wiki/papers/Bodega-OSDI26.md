---
type: paper
name: Bodega
full_title: "Bodega: Localized Linearizable Reads at Anywhere Anytime via Roster Leases"
authors: [Guanzhou Hu, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: OSDI
year: 2026
tags: [consensus, linearizability, leases, geo-replication, key-value-store]
source_pdf: "[[osdi26-hu-guanzhou.pdf]]"
source_md: "[[osdi26-hu-guanzhou]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用响应节点名册租约实现本地线性一致读（OSDI 2026）

> **原题**：Bodega: Localized Linearizable Reads at Anywhere Anytime via Roster Leases

> **一句话总结**：已有 read lease 要么只让 leader 本地读，要么一遇到冲突写就撤销；Bodega 改为租约保护“哪些副本可以回答哪些 key”的 responder roster，并要求每次写入在提交前到达对应 responder，因此在五站点 WAN 的中等写入干扰下把平均读延迟降低到既有协议的 1/5.6–1/13.1，同时在 10% 写入的负载扫描中把吞吐上限从 Quorum Leases 的约 3.4k ops/s 提高到约 6k ops/s。

## 问题与动机

跨地域复制把副本放在多个站点以承受相关故障，但传统 [[Paxos]] 或 Raft 风格协议通常让读请求访问 leader 或法定人数（quorum）。客户端即使和一个 follower 在同一站点，也要付出一次跨地域往返。直接读取 follower 虽然快，却不能保证 [[Linearizability|线性一致性]]：本地副本可能尚未看到一个已经向其他客户端确认的写入。

Leader Leases 只证明当前 leader 是唯一 leader，因此只有 leader 能安全地直接回答。Quorum Leases 可以把读权交给 follower，但租约承诺保护的是单次写入；有冲突写时必须撤约，读请求随即重定向或等待。论文图 1 的 99% 读、1% 写示例已经足以让大量读离开最近副本，说明“读多”不等于“存在足够长的无写静默期”。

Bodega 的目标更窄也更明确：在异步网络和少数 fail-slow/fail-stop 故障下，不依赖外部成员管理服务，让用户指定的任意副本持续提供本地单 key 线性一致读；代价是写入法定人数必须覆盖这些副本。事务、跨 key snapshot、写密集负载和可容忍旧值的读都不是论文的主要目标（§2.1、§7）。

## 关键观察 / 隐含假设

- **观察 1：本地读的安全条件可以从“阻止写入”改写为“先让 responder 收到写入”**。若全体副本对 responder roster 有唯一、稳定的认识，而且写入只有在所有相关 responder 都回复后才能提交，那么 responder 的本地 log 不会漏掉已经确认的写入（§3.1–§3.2、§4.3）。
  - **依赖假设**：写入仍能找到“多数副本 + 全部 responder”的覆盖集合；responder 过多或不可达时，写延迟和可用性都会下降。
  - **可能失效场景**：所有站点都要求对所有 key 本地读时，写入接近 all-replica fan-out；频繁故障会让这一集合反复不可用。
- **观察 2：冲突写通常只是短暂地处于 accepted、尚未 committed 的状态**。因此 responder 不必立刻把读重定向到远端；把读暂存在对应 log slot 上，等 Commit 或足够多的 Accept 通知，通常更快（§3.2.2）。图 12 中，Bodega 的干扰窗口约 25 ms，而两种 Quorum Leases 会升到约 40 ms 的 leader RTT，并持续更久。
  - **依赖假设**：leader 与 responder 的链路在正常路径上健康，Commit 会在一次 RTT 内到达；客户端还需用 unhold timeout 防止 leader 失效后无限等待。
  - **可能失效场景**：leader 故障、严重丢包或长尾暂停会让 held read 超时并重新发送，延迟不再是本地量级。
- **观察 3：roster 的变化远少于普通请求，集群本来就会发送 heartbeat**。所以租约的 Renew/RenewReply 可以搭载在 heartbeat 上，稳定期不进入读写关键路径；只有 roster 改变时才发送完整内容（§3.3.3、§5.2）。
  - **依赖假设**：时钟速率漂移有已知上界；协议不要求时间戳同步，但 lease 的保守到期时间必须可信。
  - **证据强度**：中。协议沿用标准 lease 安全条件，实验使用固定 timeout；论文没有注入时钟异常或进程长暂停。
- **假设 1：key 的地域偏好与读写比例足够稳定，值得维护细粒度 roster**。默认策略只为读占比大于 95% 的 key 添加 responder，并选择承接该 key 超过 20% 读取的站点（§5.1）。
  - **证据强度**：中。图 17–18 与 Zipfian YCSB 展示了收益—成本曲线，但没有评测热点快速迁移时的控制面振荡。

## 核心方法

Bodega 把 leader 身份推广成响应节点名册（roster）。每个 roster 记录一个 leader，以及每个 key 或 key range 的 responder 集合；leader 可视为所有 key 的隐式 responder。每个新 roster 都绑定唯一且单调增大的 ballot，即使内容相同也被视为不同版本。用户、在线统计或故障检测都可以提出新 roster（§3.1）。

正常写路径仍是 MultiPaxos 风格的 Accept。不同之处只有提交条件：leader 除了收齐多数 AcceptReply，还必须收齐当前 roster 中该 key 的所有 responder 回复。这个 responder-covering quorum 是本地线性一致读的主要成本，也是安全性的关键；Bodega 没有改变写入顺序或另引入外部协调器（§3.2.1）。

读请求发给最近的 responder。稳定 leader 可直接返回最后一个已提交值；非 responder 立即把客户端引向 responder 或 leader；非 leader responder 则查看该 key 的最高 log slot。若它已经 committed，就直接返回；若只 accepted，就执行 optimistic holding，把读挂在该 slot 上，收到 Commit 后释放。可选的 early Accept notification 让各 acceptor 同时通知 responder；当 responder 看见可提交的覆盖集合时，便能提前确定该写最终会提交，论文估计正常情况下可把等待时间再减半（§3.2.2）。

Roster lease 解决“所有副本是否在使用同一个 roster”的问题。每个节点同时是 lease grantor 和 grantee，并与其他节点执行 Guard、Renew、Revoke。一个节点只有在持有至少多数、且都对应同一 ballot/roster 的 lease 时，才把该 roster 视为稳定。多数集合相交保证同一时刻至多有一个稳定 roster；由此 leader 知道必须覆盖哪些 responder，responder 也知道 leader 不会绕过自己提交写入（§3.3.1、§4.3）。

仅有多数 lease 还不够：刚加入 roster 的落后副本可能漏掉旧 ballot 已提交的 slot。为此 Guard 携带 grantor 见过的最高 accepted slot，responder 必须先提交到这些 threshold 中能覆盖多数交集的位置，之后才可本地读。论文的安全证明分三种 ballot 关系处理读之前已确认的写：更高 ballot 不可能已稳定提交；同 ballot 的写入法定人数必含 responder；更旧 ballot 的提交则由多数交集和 safety threshold 捕获（§3.3.1、§4.3）。

Roster 变更先撤销旧 lease，再为新 ballot 建立 lease。健康节点会回复 Revoke，因此常规变更只需撤销和 Guard 两轮消息；节点失联时则必须等待旧 lease 到期。实现把 Renew 和回复放进 120 ms heartbeat，默认故障检测约 1200 ms，Guard 和 lease 均为 2500 ms；完整 roster 只在发生变化时发送，其他 heartbeat 只带 ballot（§3.3.2–§3.3.3、§5.2）。

## 设计取舍

- **读 locality 换写入 fan-out**：responder 越多、覆盖 key 越广，本地读比例越高，但写入必须等待更多、可能更远的副本。图 17–18 直接显示读延迟下降和写延迟上升。
- **租约安全换故障恢复停顿**：正常读无需网络往返；失联节点仍持有旧承诺时，新 roster 必须等到 lease 安全到期，写入会停顿数秒。
- **optimistic holding 换尾延迟控制**：常见的短冲突不再远程重试，但故障时要靠客户端 timeout 向其他节点发同一 read ID；实现和调参比直接重定向复杂。
- **细粒度 roster 换控制面成本**：按 key 选择 responder 能保护写性能，却需要统计、存储、传播和审计映射。论文实现了简单阈值策略，没有解决最优在线策略。
- **经典共识扩展换有限语义**：机制容易叠加在 Paxos/Raft 风格复制上，但正确性论证只覆盖非事务命令；跨 key 线性一致 snapshot 需要新的协议。

## 实验与结果

- **正常负载**：论文在真实五站点 CloudLab WAN 和按 Google Cloud RTT 用 `netem` 模拟的五节点 GEO 上测试；50 个闭环客户端平均分布在五站点，访问 1k 个 8B key、128B value，写比例为 0%、1% 或 10%。对比 MultiPaxos、Leader Leases、EPaxos、PQR、两种 Quorum Leases 等协议。作者汇总称，中等写入干扰下 Bodega 的平均客户端读延迟比既有方案低 5.6–13.1 倍，同时写性能大体相当（§6.1、图 9）。
- **负载上升**：在 WAN、10% 写入的 open-loop 扫描中，Leader Leases 约在 1.8k ops/s 达到上限，PQR + Leader Leases 约 2.2k，Quorum Leases 约 3.4k；Bodega 因大部分读留在本地，平均延迟约低 1.5 倍，吞吐上限约 6k ops/s（§6.1、图 10）。
- **单次写入干扰**：每个 open-loop 客户端以 400 req/s 读取同一 key，随后注入一次写入。Quorum Leases 的读延迟升到约 40 ms；Bodega 把干扰窗口缩到约 25 ms，并可通过 holding 让受影响的读仍在本地完成（§6.2、图 12）。
- **Roster 变更**：WAN 实验在约 0.8 s 时杀死一个 responder；写入立即停住，健康节点约 1.1 s 后检测到故障，再等待约 2.6 s 的 lease 到期才恢复。显式发起且节点健康的 roster 变更只用约 75 ms，即约两次集群 RTT（§6.3、图 16）。另一个一百万模拟秒、每秒 0.5% 故障概率的夸张模拟中，Bodega 仍比 Leader Leases 最多高 2.2 倍吞吐，但该结果不是实际故障实验（§6.3、图 15）。
- **YCSB**：在 10k key 的 A/B/C/D/F 上，Bodega 在 Uniform 全覆盖和 Zipfian 每站点 top-20% 覆盖两种 roster 中，都能接近甚至超过 default ZooKeeper，并跟上 stale etcd（§6.4、图 19）。这些系统的对应模式只提供 sequential consistency 或更弱保证，不能作为同语义的公平性能胜出；纯读 C 中它们约为 0.3 ms，而 Bodega 和 Quorum Leases 因 1 ms batching 约为 1.2 ms。
- **形式化检查**：附录的完整 PlusCal/TLA+ 模型在 3 节点、1 个可故障节点、3 个 ballot、2 写 2 读、3 个 lease tick 和所有 responder 选择上检查线性一致性与 fault tolerance；96 核、768 GiB 机器运行 43 小时，探索 4,274,883,464 个不同状态（附录 A）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 任意稳定 responder 可在冲突写存在时安全地本地读 | §3.2–§4.3 的 roster 唯一性、覆盖写法定人数和 threshold 证明；附录 A 的 TLA+ 检查 | 非事务 key-value 命令、少数 fail-stop/fail-slow 故障、时钟速率漂移有界 | 强 |
| 写入干扰不会像 Quorum Leases 一样长期破坏读 locality | §6.1–§6.2、图 9、图 11–12 | 五节点 WAN/GEO，0%–10% 写入；本地站点被选为 responder | 强 |
| Bodega 在负载上升时提高吞吐上限 | 图 10：约 6k ops/s，对 Quorum Leases 约 3.4k | WAN、10% 写入、1k key、128B value、open-loop load sweep | 强 |
| 常规 roster 变更快，但故障变更受 lease 到期限制 | 图 16：约 75 ms 对故障路径约 1.1 s 检测 + 2.6 s 到期等待 | 单次节点崩溃、固定 heartbeat/lease 参数 | 强 |
| 能与生产协调服务达到相近性能且保持更强读语义 | §6.4、图 19 | YCSB、10k key；etcd/ZooKeeper 对照模式不是线性一致读 | 中 |

## 批判性分析

### 论证链条

论文最扎实的部分是把安全性拆成三个可检查条件：roster 唯一、写覆盖 responder、落后副本跨过 threshold。协议、简短证明和 TLA+ 模型对得上；实验又分别验证正常读、冲突写和 roster 变化，论证链条基本闭合。需要收窄的是“anywhere anytime”：只有被 roster 选中的节点才能本地读，刚加入且未追上 threshold 的节点不能读，故障时写入也可能停顿数秒。

### 假设压力测试

方法最依赖 responder 数量和 key locality。若每个站点对所有 key 都要求本地读，写入必须到达所有站点；一个慢 responder 就会进入写关键路径。热点若快速跨站点移动，默认的 95% 读比例与 20% 地域份额阈值可能频繁触发 roster 变更，反而造成 revoke、传播和 lease 等待。论文基于有界时钟速率漂移；系统 suspend、长时间 stop-the-world pause、虚拟机迁移和异常计时源需要单独验证。

### 实验可信度

协议基线覆盖 leader、leaderless、client quorum 和两种 read lease，且评测包含 WAN、负载曲线、延迟分布、写比例、value 大小、故障与 YCSB，证据面很完整。主要限制是只有五副本和受控实验；没有长期生产 trace、P99.9、时钟故障、部分网络分区或高速 roster churn。5.6–13.1 倍主要来自消除 WAN RTT，具体倍数会随拓扑和 responder 选择明显改变。图 15 是由图 9 数值驱动的 Monte Carlo 模拟，不能替代真实反复故障。

### 系统性缺陷

故障 responder 会立即阻塞写，而旧 lease 到期前不能安全删除它；这是协议保证换来的可见可用性代价。论文承认 heartbeat timeout 在部分网络分区下会伤害活性，只建议使用 pre-vote 和透明重路由，没有实现或评测。控制面还要可靠地观测每 key 的地域流量、解释 roster 决策并限制振荡。论文没有讨论大 key 空间下 roster 内存、全量传播、审计、回滚和错误配置的运维成本，也没有给出事务语义。

## 局限与后续工作

- **局限 1**：证明和实现面向非事务单 key 命令；不能据此推断跨 key snapshot 的线性一致性。
- **局限 2**：五节点实验没有覆盖 responder 数量很大、跨洲 RTT 极不对称或部分分区长期存在的部署。
- **局限 3**：自动 roster 策略只有固定阈值，没有报告 metadata 大小、变更频率或热点迁移期间的 P99 延迟。
- **后续工作 1**：用真实地域访问 trace 回放热点迁移，联合报告 roster churn、metadata 字节数、写放大、P50/P99 读写延迟，并与静态 roster 比较。
- **后续工作 2**：注入 clock-rate drift、进程暂停、单向丢包和部分网络分区，运行 Jepsen history 检查线性一致性，同时量化不可用窗口。
- **后续工作 3**：把 responder-covering 条件扩展到跨 key transaction，并用至少两个 key、并发写和故障重配置验证 snapshot linearizability。

## 相关

- **相关概念**：[[Consensus]]、[[Linearizability]]、[[Lease]]、[[Quorum]]、[[Geo-Replication]]
- **同类系统**：[[MultiPaxos]]、[[EPaxos]]、[[PQR]]、[[etcd]]、[[ZooKeeper]]
- **同会议**：[[OSDI-2026]]
