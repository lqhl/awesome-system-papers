---
type: paper
name: Sieve
full_title: "Understanding and Detecting Fail-Slow Hardware Failure Bugs in Cloud Systems"
authors: [Gen Dong, Yu Hua, Yongle Zhang, Zhangyu Chen, Menglei Chen]
venue: ATC
year: 2025
tags: [fail-slow, fault-injection, distributed-systems, reliability, static-analysis, cloud-systems]
source_pdf: "[[atc2025-dong.pdf]]"
source_md: "[[atc2025-dong]]"
---

# Understanding and Detecting Fail-Slow Hardware Failure Bugs in Cloud Systems (ATC 2025)

> **一句话总结**：Sieve 的核心判断是 fail-slow hardware bug 不是“任意 I/O 都可慢”的问题，而是细粒度慢 I/O 穿过 synchronized / timeout 机制后逃过粗粒度健康检查；基于 48 个真实 FSH failure 的 study，它只在这两类 I/O 上注入一次细粒度 delay，在 ZooKeeper、Kafka、HDFS 上检测到 6 个未知 bug 和 1 个已知未修 bug。

## 问题与动机

Fail-slow hardware 指硬件仍然可用、功能也没有完全失败，但性能降到异常低的状态，例如 NIC 吞吐从 1 Gbps 掉到 1 Kbps，或 NVMe SSD 在现场进入长时间慢响应。它比 fail-stop 更麻烦：系统的 heartbeat、leader election、timeout handler 往往还看到“节点活着”，但某些 I/O path 已经慢到让上层同步、超时、错误处理逻辑进入错误状态。

论文把这类由 fail-slow hardware 触发的软件 bug 称为 FSH bug，把由此导致的系统故障称为 FSH failure。动机来自两个事实：一是生产系统定位非常慢，文中举到 AWS 网络延迟事件用了 9 小时定位，PagerDuty 的 ZooKeeper fail-slow NIC 案例用了 5 个月；二是现有 [[Fault-Injection]] 工具多以 crash、partition、fail-stop disk/NIC 等粗粒度故障为对象，无法稳定触发“只有一部分 I/O 慢、其他探针仍正常”的状态。

作者的目标不是做一个生产 fail-slow detector，而是在 release 前用 fault injection 找出这些 bug。关键设计选择是先做 bug study，再让 study 缩小 injection space：如果不缩小，所有 I/O、所有上下文、所有 delay 组合会让测试空间爆炸；如果缩得太狠，又会漏掉需要细粒度 fault point 的 bug。

## 关键观察 / 隐含假设

- **观察 1：48 个 studied FSH failure 都落在 synchronized 或 timeout 机制附近。** Study 覆盖 ZooKeeper 11 个、HDFS 18 个、HBase 10 个、MapReduce 4 个、Cassandra 5 个 failure。根因上，indefinite blocking 占 41.6%，buggy internal checker 占 35.4%，data race 占 16.7%，这三类合计 93.7%；它们都和“慢 I/O 被同步结构放大”或“慢任务与 timeout handler 竞争”有关。
  - **依赖假设**：公开 JIRA issue 里能定位到的 FSH failure 足以代表云系统中最值得测试的 failure shape；尤其是假设 synchronized / timeout 机制是主导风险，而不是样本选择造成的偏差。
  - **可能失效场景**：闭源系统、异步 runtime、actor/event-loop 架构、kernel bypass I/O 或高度自定义 scheduler 可能把同样的 fail-slow 风险藏在不同抽象里，Sieve 的 pattern 需要扩展。

- **观察 2：触发 FSH bug 通常需要细粒度 slow fault，而不是粗粒度 fail-stop。** 论文反复用 ZooKeeper 例子说明：如果 leader 的 serializeNode 在 synchronized block 内因为 fail-slow NIC 变慢，但 heartbeat 仍可运行，cluster 会维持 liveness 幻觉并阻塞写请求；如果直接 fail-stop NIC，follower heartbeat 能检测故障并触发 leader election，反而恢复到健康路径。
  - **依赖假设**：细粒度故障能逃过系统内部健康检查，这是 Sieve 比 coarse-grained injection 更有效的前提。
  - **可能失效场景**：如果系统的 detector 已经做 per-operation latency attribution，或者故障影响的是整个 device / node 而不是 subset I/O，Sieve 的优势会下降。

- **观察 3：单个 fail-slow hardware 已经足够覆盖大多数 studied failure。** Study 中 89.6% failure 由一个 fail-slow hardware 触发，client request 参与 83.7%，多 fail-slow hardware 只有 10.4%。
  - **依赖假设**：release 前测试优先覆盖 single-fault 场景是合理的，组合故障可以后置。
  - **证据强度**：中。48 个案例支持这个工程取舍，但 evaluation 中 5 个 study bug 明确需要 multiple fault injections，说明 single-fault 不是完整 fault model。

- **假设 1：I/O 延迟注入足以代表本文目标 FSH fault。** Sieve 的 fault model 承认 fail-slow hardware 还可能造成 partial I/O exception，但实现只模拟第一类：partial I/O operations 变慢，并且每个 test run 只注入一次 delay。
  - **证据强度**：中。它能找到 7 个 bug 并复现 34/48 study bug；但未复现案例里有多故障、silent symptom、复杂 interleaving 和静态分析 blind spot。

- **假设 2：轻量静态分析能把风险点筛到足够小又不过度漏报。** Sieve 只识别 synchronized / timeout-protected I/O，依赖 Java bytecode 里的 lock、wait、await、tryacquire、join、nanoTime、currentTimeMillis 等 pattern。
  - **证据强度**：中偏强。三套系统的 static fault point 明显减少：ZooKeeper 从 1905 个全部 I/O 到 1266 个 S/T I/O、856 个 grouped S/T；Kafka 从 1953 到 1090、780；HDFS 从 4216 到 1974、1568。但 HBase FIFO queue 相关 bug 就超出了当前分析能力。

## 核心方法

Sieve 分两阶段工作。第一阶段是 fault point analysis：对目标 Java cloud system 做 [[Static-Analysis]]，找 synchronized I/O 和 timeout-protected I/O，并用 Javassist 在这些点前插入 fail-slow agent。第二阶段是 fault injection testing：workload driver 驱动系统，agent 在运行时向 injection controller 发送 call stack、thread ID、instrumented position 等信息，controller 决定是否对当前点注入 delay，failure checker 观察日志、节点状态和客户端进度。

同步 I/O 的识别分两种 pattern。第一种是 critical region，也就是 lock/synchronized 形成的临界区。难点在于 bytecode 里 branch 和 return 会产生多个 exit point，Sieve 用一个实用规则匹配“最后一个没有紧跟 return 的 exit point”，再把临界区内 I/O 视为 synchronized I/O。第二种是 hard barrier，例如 notify/wait 让 Task1 必须先于 Task2，barrier 前的 I/O 被视为同步相关。

Timeout-protected I/O 也分两种 pattern。第一种是 wait(timeout) 形成的 soft barrier：Task2 可以 timeout 并调用 handler 处理 Task1。第二种是 get-time based timeout：系统用 nanoTime/currentTimeMillis 记录 startTime/endTime，再计算 `elapsedTime = endTime - startTime` 并和 timeout 比较。Sieve 收集 get-time 变量，寻找 `A = B - C` 且 A 被 if 使用的表达式，由此推断 timeout scope，并把 scope 内 I/O 作为候选点。

Injection controller 的核心是两个剪枝策略。**Grouping** 把同一个 basic block 内的多个 fault point 合并，只在最后一个点插桩，因为作者假设这些点处在同一高层系统状态、共享类似 fault-tolerance handler。**Context-sensitive injection** 用 call stack 和 thread ID 区分同一个 fault point 的运行时上下文，避免在完全相同上下文重复注入，也允许同一静态点在不同调用路径下被测试。

Delay duration 按 fault point 类型决定。Synchronized I/O 默认注入 5 分钟 delay，用来触发 indefinite blocking，又避免测试时间无限变长。Timeout-protected I/O 按 Algorithm 1 使用 timeout 值派生 delay，让慢任务和 timeout handler 产生可控重排；这里的目标不是模拟某一块具体硬盘的完整物理行为，而是构造能暴露 timeout 逻辑缺陷的 timing relation。

Failure checking 有两层。Log error checker 扫描 FATAL、ERROR、WARN 和 uncommon exceptions。Gray failure checker 是简化版 Panorama：如果系统内部 checker 认为节点 healthy，但客户端报告错误，或只有部分客户端无法完成 workload，就把 test run 标为 suspicious。作者也强调 checker 可扩展，比如加入 correctness specification 或性能/一致性 oracle。

## 设计取舍

- **Study-guided pruning vs completeness**：Sieve 用 bug study 把 injection point 限定在 synchronized / timeout-protected I/O，换来测试效率和 bug yield；代价是所有不经过这些 pattern 的 fail-slow bug 都可能漏掉。
- **Single-fault model vs fault-space explosion**：每个 test run 只注入一个 delay，符合 89.6% studied failure 的统计；代价是无法覆盖需要多个慢点、异常和特定顺序的 failure。
- **静态 pattern 简单性 vs runtime 语义精度**：Soot bytecode 分析和 keyword/pattern matching 足够可实现、可移植到 Java 系统；但 synchronized data structure、custom async abstraction、跨语言系统和复杂 queue 语义会成为盲区。
- **通用 checker vs false positive**：log/gray failure checker 能跨系统复用；但它们只提供 suspicious signal，仍需要人工读日志、查设计文档、和开发者确认。
- **细粒度 instrumentation vs deployment realism**：agent-level sleep 可以精确慢某个 I/O 点；真实 DM/TC 只能慢整个 device/network path，不能做到这种 fine-grained injection。因此 Sieve 的 injection 更像 testing perturbation，不是完整硬件仿真。

## 实验与结果

- **目标系统与 workload**：ZooKeeper 3.9.0 用 create/read/update/delete znode，Kafka 3.6.0 用 producer/consumer performance test，HDFS 3.3.6 用 read/write/move/put file。三者分别部署在单机 Docker cluster 上，ZooKeeper/Kafka 3 节点，HDFS 4 节点。
- **测试成本**：每个系统 2000 个 test runs；ZooKeeper、Kafka、HDFS 总实验时间分别为 20.9 小时、24.9 小时、29 小时。静态分析每个系统 3 分钟内完成，最多 8GB 内存。
- **未知 bug**：Sieve 检测到 7 个 bug，其中 6 个 unknown bug 和 1 个 known but unfixed HDFS-15869；ZK-4836 和 KAFKA-16412 已被开发者确认。症状包括 node hang、uncaught exception、node crash、semantic violation。
- **Study bug 复现**：Sieve 复现 34/48 个 studied bugs。未复现的 14 个包括 5 个需要 multiple fault injections 的 bug，6 个 silent symptom 但缺少准确 checker 的 bug，1 个需要复杂 thread interleaving 的 deadlock，以及 2 个静态分析无法处理 synchronized FIFO queue 的 HBase bug。
- **与 baseline 对比**：Random 没找到 bug；FATE、Legolas、Chronos 都漏掉若干 FSH bug。Sieve 是表中唯一检测到全部 7 个 bug 的方法。Chronos 能检测 ZK-4817 和 KAFKA-16412 也依赖 Sieve 实验里的 broad log checker；按 Chronos 原论文的 crash/hang checker，本应检测不到这两类症状。
- **Fault point 数量**：Random/FATE/Legolas/Chronos 在每个系统都跑满 2000 dynamic fault points。Sieve 动态探索更少：ZooKeeper 705、Kafka 967、HDFS 658，同时不降低 bug count。Grouping 也减少 static candidate：ZooKeeper S/T 1266 到 S/T+Gr 856，Kafka 1090 到 780，HDFS 1974 到 1568。
- **Runtime overhead**：instrumented fault-free run 相比 baseline 为 1.1x 到 4.9x；含一次 fault injection 的 average test time 为 1.9x 到 6.3x。具体地，ZooKeeper baseline/info/test 为 9.41/13.17/37.64 秒，Kafka 为 7.12/34.89/44.86 秒，HDFS 为 24.87/27.36/52.23 秒。

## Critical Analysis

### 论证链条

论文的主链条比较闭合：48 个真实 failure 的 study 显示风险集中在 synchronized / timeout 机制；Sieve 将 fault point 收缩到这两类 I/O；evaluation 里 Sieve 比 all-I/O 或 timeout-only baseline 找到更多 bug、探索更少点。最有说服力的是 ablation：Sieve-I 说明只找 S/T I/O 还不够，Sieve-S 说明 context-sensitive 能找到更多有效上下文，完整 Sieve 说明 grouping 可以减少探索而不损失 bug count。

但它也有一个外推：从 5 个 JIRA-rich Java ecosystem 系统总结出的 pattern，被描述为适合“cloud systems”整体。Kafka 作为 out-of-study system 能提供一定外部验证，不过仍然是 Java、分布式存储/消息系统、公开 issue/workload 友好的场景。对 C++ storage engine、kernel data path、async Rust/Go 服务、GPU/accelerator 系统，论文没有证明 pattern 覆盖率。

### 假设压力测试

Sieve 最脆的地方是 workload 和 checker。Table 8 显示当前 simple workloads 不能触发所有 candidate fault points；如果 buggy path 需要复杂 client sequence、rare reconfiguration、rolling upgrade 或 long-running background task，Sieve 可能根本看不到对应 agent。另一方面，20.8% studied failures 是 data unavailability / inconsistency 这类 silent symptom，通用 log/gray checker 很容易漏掉，需要系统特定 correctness oracle。

第二个压力点是 fault model。真实 fail-slow hardware 可能同时带来延迟、异常、吞吐抖动、队列堆积、partial packet/drop、thermal throttling 或跨多个 I/O 的相关性。Sieve 当前把它简化成“一次 delay”，这适合暴露 synchronized blocking 和 timeout race，但不适合暴露持续性退化、周期性抖动、多个设备同时慢、或 exception + delay 混合的 bug。

第三个压力点是 delay choice。5 分钟 synchronized delay 可以稳定触发 blocking，却可能比真实生产中的慢 I/O 更强，导致 bug report 需要额外 realism validation。Timeout delay 则需要精确拿到 timeout value 和正确的 timing relation；如果 timeout 是 adaptive、分层、由外部服务动态配置，或多个 watchdog 叠加，当前 pattern 会不够。

### 实验可信度

主结果可信度较好：作者给了真实系统、版本、workload、cluster setup、2000 test runs、baseline 对比、ablation 和 false positive 处理流程。Kafka 没在 bug study 中出现，是一个有价值的泛化检查。发现的 bug 中有两个开发者确认，也提升了外部可信度。

不足在于 workload 偏小、部署在单台物理机的 Docker cluster，和生产规模差距很大。Fail-slow 的很多影响来自排队、跨机网络、shared storage、tenant interference 和长尾负载，单机 Docker 可能弱化或改变这些现象。另一个不足是 checker 很宽：log checker 扫 WARN/ERROR 可能把预期行为标为 suspicious，gray checker 的 differential observability 是必要非充分条件，所以最终 bug count 依赖人工确认流程。

### 系统性缺陷

Sieve 的工程复杂度不低：Java-only 静态分析、bytecode instrumentation、RMI controller、workload driver、failure checker、runtime context tracking 都需要接入目标系统。论文说核心组件约 8,100 SLOC，但没有深入讨论接入新系统时的维护成本、版本漂移、instrumentation 对 timing 的扰动，或如何处理 production-grade CI 中的 flakiness。

论文未讨论资源隔离和可观测性成本。大量 test runs 带 5 分钟 delay，CI 周期会很长；如果 checker 需要人工 triage suspicious reports，那么 Sieve 更像高价值但低频的 reliability campaign，而不是每次提交都跑的 quick test。它也没有覆盖 recovery / cleanup 风险：每个 test run 重启系统可隔离前一次 fault，但这掩盖了生产中残留状态、partial repair 和长期后台任务可能造成的问题。

## 局限与 Future Work

- **局限 1：fault model 只覆盖单次 delay。** 它漏掉 partial I/O exception、多个 slow point、delay + exception 混合、以及需要指定 fault order 的 bug。可验证的下一步是把 14 个未复现 study bugs 作为 regression set，分别加入 multi-delay、exception injection 和 order control，看覆盖率能否从 34/48 提升。
- **局限 2：checker 对 silent failure 不够强。** 6 个 silent studied bugs 未复现的原因是缺少准确 checker。下一步应该为 ZooKeeper/HDFS/HBase 这类系统加入 invariant / consistency oracle，区分“客户端看到错误”与“状态已经错误”。
- **局限 3：静态分析 pattern 依赖 Java 同步/时间 API。** Sieve 当前支持 synchronized、lock、wait、await、tryacquire、join、nanoTime、currentTimeMillis 等常见 keyword；下一步可以把 synchronized queue、async callback、future/promise、reactor event loop 作为独立 pattern。
- **局限 4：workload coverage 受限。** Simple workloads 无法触发所有 fault points。一个客观 future work 是把 coverage-guided fuzzing 或 trace replay 接入 workload driver，用 dynamic fault point coverage 而不是固定 workload 数量衡量进展。
- **局限 5：realism validation 仍靠人工。** Sieve 用 DM/TC 检查 non-blocking I/O false positive，但最终 suspicious test run 仍需读日志、查文档、联系开发者。后续可以把“真实设备慢 I/O 是否能复现 agent-level suspicious behavior”做成自动二阶段验证。

## 相关

- **相关概念**：[[Fault-Injection]]、[[Static-Analysis]]、[[Gray-Failure]]、[[Timeout-Mechanism]]
- **同类系统**：FATE、Legolas、Chronos、Panorama、IASO、OmegaGen、PERSEUS
- **同会议**：[[ATC-2025]]
- **相近论文**：[[CAFault-ATC25]]
