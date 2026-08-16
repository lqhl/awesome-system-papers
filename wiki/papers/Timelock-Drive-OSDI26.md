---
type: paper
name: Timelock-Drive
full_title: "Timelock Drive: Isolated Time-Based Defense for Storage Systems"
authors: [Jonah Rosenblum, Juechu Dong, Peter M. Chen, Satish Narayanasamy]
venue: OSDI
year: 2026
tags: [storage-security, ransomware, trusted-computing-base, formal-verification, backup]
source_pdf: "[[osdi26-rosenblum.pdf]]"
source_md: "[[osdi26-rosenblum]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Timelock Drive：把时间锁隔离到物理块设备（OSDI 2026）

> **原题**：Timelock Drive: Isolated Time-Based Defense for Storage Systems

> **一句话总结**：Timelock Drive（TD）让一个约 400 行、形式化验证且与 host 隔离的 checker 控制每个 physical block 的“冻结—倒计时—可写”状态；即使 administrator、OS 和 versioning system 全被攻陷，也只能启动倒计时，不能立即覆盖旧版本。TD 用 append-only log 保存不可覆盖的 metadata，再让 untrusted host 缓存、checker 用 MAC 和 freshness counter 验证，使 SSD benchmark 的 execution/throughput overhead 约为 0.4%/0.5%。

## 问题与动机

普通 backup 仍受 host 的 credential 和 software stack 控制。攻击者一旦拿到 administrator 权限，就能删除 snapshot、修改 retention policy，或利用 versioning system（VS）/firmware 的 bug 清掉旧版本。把“最近版本几个月内不能删除”写进同一套 VS，仍然把复杂 VS 放在可信计算基（trusted computing base，TCB）里；已有 trimming attack 已证明 storage-side version management 也可能绕过 timelock check（§1–§2）。

TD 把安全目标缩成一个更低层的 primitive：某个 physical block 被 timelock 后，在规定时间内任何人都不能修改，包括 root 和完全 compromised VS。上层仍可自由选择 incremental checkpoint、version policy 和 garbage collection，但不再能取消 device enforcement。代价是 data 和 metadata 都不能原地更新，传统 filesystem/VS 常见的 checkpoint region、free-space map 和 version index 都必须重做（§1）。

时间锁不是永久防御。论文定义 intrusion detection latency `L` 和可回滚窗口 `R`；受保护窗口必须比检测时间更长，才能恢复到 intrusion 以前。patient attacker 如果潜伏到锁过期，仍可能销毁数据。timelock 的价值是延长攻击者必须等待的时间，让 detector、forensics 和 administrator 有机会先发现攻击；它不解决 data exfiltration、physical destruction 或 availability attack（§2、图 1）。

## 关键观察 / 隐含假设

- **观察 1：timelock policy 与 version policy 可以解耦。** checker 只需判断 physical address 当前能否写；logical version、checkpoint 和 placement 都可留在 untrusted host（§3.5）。
  - **依赖假设**：所有 storage command 必须经过不可绕过的 checker；device firmware、DMA path 或维修接口不能另开写入口。
- **观察 2：timelocked block 不应在创建时立即开始过期。** 用户通常不知道一个 live version 何时会被替换。TD 先无限 frozen，收到 `unfreeze` 后才开始完整的 duration countdown（§3.1、图 2b）。
  - **安全效果**：攻击者在 intrusion 后马上 unfreeze 最新版本，也必须再等待完整 interval，不能通过“提前启动的旧 timer”立即覆盖。
- **观察 3：append-only metadata 解决不可覆盖，却让正常 write 需要 scan 全 log。** TD metadata 缺乏足够 temporal locality，把完整 cache 放进小 controller 又不现实（§3.3–§3.4）。
  - **设计假设**：host 可以不可信但仍帮忙；checker 只验证 host 提供的 metadata/MAC，而不信任其内容。
- **观察 4：backup data 和 metadata 都必须有同样保护。** 只锁 data 而允许重写 logical-to-physical map，攻击者仍可隐藏所有有效版本（§4.4）。
  - **可能失效场景**：recovery code 若错误解释 append-only chain 或 intrusion timestamp，同样会选错版本；形式化 proof 没覆盖整套 VS recovery。
- **假设 1：checker 有单调不下降、跨重启保持的 secure clock。** 断电时 clock 可以停止，恢复供电后继续；这只延长锁，不缩短锁（§2）。
  - **证据强度**：中。TPM-like nonvolatile counter 是可行类比，但 prototype 并未实现和攻击真实 secure clock。
- **假设 2：trusted recovery 能确定一个可信 intrusion time。** time-of-lock 早于该时间的版本才可作为 pre-intrusion state（§4.7）。
  - **证据强度**：弱到中。论文把 forensic reconstruction 放在 scope 外，也建议尝试多个 candidate time 后人工验证。

## 核心方法

### block 状态机与隔离 checker

TD 在普通 SSD/HDD command path 中插入 TD-checker microcontroller（§3.1–§3.2、图 2）。`read` 与 `identify` 基本不变；`write` 只有在目标 block 为 free 时通过；`timelock-update` 可批量 timelock/unfreeze 地址；`get-next-td-hash` 在 reset/recovery 时顺序重建 metadata cache。

一个 block 有三种状态：

1. **Free**：可以写。
2. **Frozen Timelock**：调用 `timelock(addr, δ)` 后进入，expiry 为 infinity，不能写。
3. **Countdown Timelock**：调用 `unfreeze` 后进入，expiry 为 `unfreeze_time + δ`；完整 `δ` 过去后才回到 Free。

checker 还记录 time-of-lock。这个 state machine 把“何时不再需要旧 version”交给 VS，把“释放后至少保护多久”牢牢留在 controller。checker、clock、freshness state 和 secret key属于 TCB；privileged user、filesystem、driver、OS 与 VS 都在 TCB 外。

作者用 Dafny 写了约 400 LoC executable checker。证明分两部分（§6）：byte-encoded transition refinement 到 abstract state machine，保证不能从 Frozen 跳过 Countdown 直接到 Free；以及 transaction-log replay 与原执行得到同一 metadata state。Dafny 再 transpile 到 Rust。proof 不覆盖 unverified Rust ATA pass-through、真实 disk persistence model、clock hardware、BLAKE3 implementation、VS、ext4 或 recovery tool；论文在 §6.3 明确把 disk model 与 theorem prover correctness列为假设。

### 时间锁元数据：只追加日志与委托验证

每个 timelocked block 需要 state、duration、time-of-lock 和 expiry。metadata 本身若可覆盖，attacker 就能解锁 data；若和 data 一起锁住，Frozen→Countdown 又无法更新。TD-log 因此只 append：timelock 追加一条，unfreeze 再追加一条，最新有效 entry 决定状态（§3.3）。小 entry 通过 bulk `timelock-update` 合并进 4 KB block，避免每个 address 浪费整块。

正常 write 若每次扫描 TD-log 找最新 entry 会很慢。TD 采用委托但验证（delegate-but-verify）：host DRAM 保存完整 TD metadata cache；checker 对 metadata、TD address、4-byte freshness counter 和 256-bit secret key计算 BLAKE3-based MAC。host 发 command 时同时交 metadata 与 MAC；checker用自己保存的 current counter 重算，旧 metadata/旧 MAC 会失败（§3.4、图 2a）。

checker 只保存 counter，约 2 MB/TB；若在 controller 内保存足以避免 cache miss 的 metadata，则约需 2 GB/TB。4-byte counter若同一个 block 以 10 ms/write 不停更新，约 1.36 年才 wrap。reset、counter overflow 或 intrusion recovery 时，checker生成新 key、禁止 write，再用 `get-next-td-hash` 一次顺序扫描整个 TD-log，同时重建 counter 和 host cache。这个过程是 log length 的线性扫描，不是每 address 各扫一遍的平方成本。

### 不可信版本系统

作者用 BDUS 实现一个 Linux block driver，把 ext4 的 logical address space 映射到 TD physical block（§4–§5、图 4）。filesystem 更新 logical address `A` 时，VS 从 free list 分配新 block `Y`、写新 version、timelock `Y`，再 unfreeze 旧 block `X`。即使 attacker 随即 unfreeze `Y`，`Y` 仍在 countdown 中保护完整 interval；`X` 若更早过期，`Y` 仍是可恢复的较新版本（§4.2、图 3）。

为降低每-write version space，VS 使用一小时 epoch 的 incremental checkpoint。epoch 内对同一 logical address 可以产生多个临时 version，结束时只 timelock最后一个，并批量 unfreeze上一 checkpoint 对应的 block。因此 recovery 回到 intrusion 前最后一个 completed epoch，而不是最后一条 write；最多再丢一个 epoch（§4.3）。

VS mapping 也写入 timelocked append-only log。每条 8-byte entry 记录 logical→physical mapping，4 KB block 可放 511 条并留 8 bytes forward pointer。当前 block 在写出前就预留 next address；crash recovery 用 time-of-lock 判断最后一个 pointer 是否指向尚未写过的 block。[[Garbage-Collection|GC]] 不覆盖旧 list，而是在另一个 predefined head location 写 condensed list并锁住，再 unfreeze旧 list；两个 head location 交替（§4.4–§5.5）。

### crash order 与 spoof-free recovery

每个 committed epoch 按 `data → barrier → VS metadata → barrier → TD metadata/timelock → final barrier` 落盘。若 final barrier 前 crash，整个 incomplete epoch 在 recovery 时丢弃，避免 metadata 指向未持久化 data，或 TD state 和 VS mapping 不一致（§4.6）。

attacker在 intrusion 后可以写假 version、假 mapping 并合法 timelock，但不能伪造更早的 time-of-lock，因为时间来自 checker。trusted recovery只读 TD，扫描 version log，对每个 logical address 选择 time-of-lock 早于 intrusion time 的最新 entry，再彻底重置 untrusted stack（§4.7）。多 drive 还需要同步写 recovery-barrier sentinel，并为 clock drift 留 guard window；论文给出协议，但 prototype/evaluation只覆盖单 drive（§4.8）。

## 设计取舍

- **物理块 primitive 换小 TCB**：version policy 不进入 checker；需要修改 drive interface/controller，现有 commodity drive 不能直接部署。
- **Frozen 后再 countdown 换保守空间释放**：不需定期 refresh live block；误锁或永不 unfreeze 会长期占用容量。
- **append-only 换 recovery/space cost**：正常写不覆盖 protected metadata；log 随 write 增长，recovery、GC 和 defragmentation 都要扫描或复制。
- **host cache 换 cryptographic verification**：checker SRAM 从约 2 GB/TB 降到 counter 的约 2 MB/TB；每个 write 都要带 metadata/MAC 并信任 MAC/key/counter implementation。
- **一小时 epoch 换 version density**：metadata/space显著降低；intrusion 前最后一个 incomplete epoch 不能保证保留。
- **time-based defense 换 detection dependency**：credential theft 不能立即毁备份；patient attacker只要隐蔽超过 retention interval仍可成功。
- **clock 停止换安全保守性**：断电不会让锁提前过期；合法 GC 和 defragmentation 也无法前进，长期断电会延迟容量回收。
- **完整性换其他威胁留白**：TD 不阻止 read/exfiltration、host拒绝新 write、physical theft/destruction 或 traffic analysis。

## 实验与结果

- **平台与 baseline 边界**：workload包括 VM-Enterprise、Microsoft Exchange、TPC-C/TPC-E、finance、Apache web trace 和 filebench。trace先写 1 GB warm-up，再尽快执行前 100K command，并保守地 version+timelock每个 write。主要设备是 4 TB Seagate ST4000DMZ04 HDD，SSD test 用 1 TB Samsung MZ-77E1T0B。baseline是**没有 security/versioning 的 log-structured block device**，另测 version-only 与 LVM snapshot。Raspberry Pi 5 checker通过 Ethernet只用于§7.2 security test；其余性能 test 把 controller logic 和 host共置、通过 shared-memory IPC通信，避免 Ethernet bottleneck。因此结果测的是 TD software path 的增量成本，不含真实 isolated drive controller 的 command/crypto latency（§7.1）。
- **安全实验与 proof scope**：18 个 well-known ransomware family sample 都能恢复 filesystem state。Dafny proof验证 timelock state transition与 TD-log replay，而 18-sample test验证完整 prototype在这些已知攻击下工作；它们不覆盖 patient attacker、unknown firmware bypass、clock/key compromise、host DoS 或整套 VS implementation 的所有 bug（§6、§7.2）。
- **运行时开销**：Figure 5 的 100K-command trace中，I/O overhead geomean约 0.14%，最高约 0.29%；latency overhead 在 HDD/SSD 上的 geomean约 0.21%/0.35%，所有 SSD trace少于 1%。ext4+filebench 的 filesystem throughput overhead geomean约 0.18%（HDD）和 0.42%（SSD），最高约 0.60%；论文 Introduction 因而概括为 SSD execution约 0.4%、throughput约 0.5%。这些数字相对上述 log-structured no-security baseline，不是相对所有 production backup appliance（§7.3.1–§7.3.3、图 5–6）。
- **host cache 是低开销的关键 ablation**：若 checker 自己只有 4 KB cache，Exchange trace latency overhead 达 400.3%；1 MB cache在 write-heavy trace 仍超过 30%，256 MB 在部分 workload 仍有明显 miss/seek cost。host full cache + checker verification 将图中 overhead压到接近 0，但要求 host每次提供metadata/MAC，并让 checker保留约 2 MB/TB counter（§7.3.4、图 7）。
- **recovery 比 LVM 慢但为线性**：模拟 attack 时先跑完整 trace、snapshot，再覆盖所有地址。TD 扫 version log，Figure 8 的恢复约 7.8–58 s；LVM约 7.4–45 s，TD在所有 trace略慢，差距依 write count而变。测试只到这些 100K-command trace，月级/年级 log在 GC policy 下的 worst-case recovery没有展示（§7.4、图 8）。
- **space overhead 随写入增长**：每 100K operation，TD+VS metadata最高略高于 3 MB，geomean约 1.35 MB；约四分之一到三分之一 log以后可回收。LVM每 snapshot metadata约 2 MB且近似固定，所以短 trace中TD常更小，长时间频繁 write时LVM更省。TD还必须等 timelock expiry才回收，实验没有量化为六个月 retention预留多少 version data space（§7.5、图 5c）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| compromised host不能提前覆盖 timelocked block | 隔离 checker state machine；Dafny refinement proof（§3、§6） | checker/clock/key/command mediation可信；Rust pass-through和真实 disk model未验证 | 中到强 |
| untrusted VS仍可恢复 pre-intrusion checkpoint | data+metadata都锁、time-of-lock过滤 spoof、18个 ransomware sample全部恢复（§4、§7.2） | intrusion time必须可确定；只测已知 sample和单 drive | 中到强 |
| delegate-but-verify让 normal write开销很低 | host cache路径 SSD execution/throughput约0.4%/0.5%；checker-cache ablation最高400.3%（图5–7） | 性能 controller与host共置，不含真实 isolated hardware latency | 强（prototype内） |
| append-only metadata的恢复/空间成本可接受 | 100K-command trace recovery 7.8–58 s；metadata最高略超3 MB（图5c、图8） | log长度小；长期 retention、GC、wear与fragmentation未测 | 中 |
| 小 TCB比 storage-side VS更易验证 | checker约400 Dafny LoC，VS/OS在TCB外（§3.2、§6） | interface、compiler、Rust glue、clock、crypto、firmware仍在实际TCB | 中到强 |

## 批判性分析

### 论证链条

论文把“backup software也可能被攻陷”转成最小 physical-block invariant，再逐层解决这个 invariant带来的metadata recursion、normal-path scan、crash ordering和spoof-free recovery，逻辑很连贯。delegate-but-verify特别关键：host做大状态管理，checker只保留 secret+counter，既不扩大 trust又避免 scan。较大的外推是从400-line Dafny core称为完整 secure backup guarantee；真正系统还依赖未验证的 command path、clock、crypto、storage persistence和recovery code。

### 假设压力测试

最直接的反例是patient attacker：先取得host控制，持续生成看似正常的新checkpoint并unfreeze旧块，等完整retention过去再破坏，TD本身不会检测。第二个压力点是capacity；retention越长越安全，version data、append log、GC等待和write amplification也越大。第三个是intrusion time：若forensics只能给很宽窗口，recovery必须回到更早checkpoint并丢更多合法数据。多drive还依赖正确的barrier和最大clock-drift bound。

### 实验可信度

workload覆盖真实trace、filebench、HDD/SSD、LVM、cache ablation、recovery和18个ransomware sample，证据维度较全，也明确报告TD recovery略慢。最大问题是性能实验取消了论文安全架构中的物理隔离：checker与host共置，Raspberry Pi/Ethernet只做security test。因此少于1%的数字不能证明真实controller、ATA/[[NVMe|NVMe]] interception、HMAC和secure clock集成后仍同样快。trace只取前100K command，也不足以支撑长期log/GC/wear结论。

### 系统性缺陷

TD保护integrity却不保护availability。attacker可以停止backup、填满free space、让所有live block长期Frozen、持续触发expensive operation，或直接阻止recovery。firmware update、key rotation、counter wrap、bad-block remapping、SSD FTL GC和SMART/power-management command都需要进入verified interface；prototype只实现实验所需ATA subset。底层SSD会在FTL内部搬迁/擦除physical flash，而论文的“physical disk block”实际是device-visible LBA，真实firmware如何保证每个LBA的timelock与内部GC一致没有prototype证明。append-only log和out-of-place versioning也可能加剧SSD wear，论文未测。

## 局限与后续工作

- 在可编程SSD/NVMe controller中实现checker、secure clock、key storage和全command mediation，分别报告read/write p50/p99与throughput。
- 扩大formal model到Rust pass-through、barrier persistence、MAC verification、counter wrap/key rotation和recovery selection，并做compiler/runtime trusted-base审计。
- 运行月级write trace，扫描retention从5天到6个月时的capacity、write amplification、GC pause、fragmentation、SSD wear和worst-case recovery。
- 加入free-space reservation、rate limit和emergency policy，验证compromised host不能用合法timelock命令耗尽device造成永久DoS。
- 对patient attacker建模：持续潜伏、删除新checkpoint、等待old lock到期，测detector latency与retention/capacity的安全曲线。
- 在multi-drive setup上注入power loss、clock drift和partial barrier，验证recovery sentinel不会让drive回到不一致epoch。
- 明确LBA remapping、bad block、FTL GC、secure erase、firmware update和device replacement如何保持timelock invariant。

## 相关

- **相关概念**：[[Ransomware]]、[[Trusted-Computing-Base]]、[[Append-Only-Log]]、[[Formal-Verification]]
- **同会议**：[[OSDI-2026]]
