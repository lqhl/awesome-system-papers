---
type: paper
name: Poby
full_title: "Poby: SmartNIC-accelerated Image Provisioning for Coldstart in Clouds"
authors: [Zihao Chang, Jiaqi Zhu, Haifeng Sun, Yunlong Xie, Kan Shi, Ninghui Sun, Yungang Bao, Sa Wang]
venue: ATC
year: 2025
tags: [smartnic, container, coldstart, serverless, rdma, image-provisioning]
source_pdf: "[[atc2025-chang.pdf]]"
source_md: "[[atc2025-chang]]"
---

# Poby: SmartNIC-accelerated Image Provisioning for Coldstart in Clouds (ATC 2025)

> **一句话总结**：Poby 的关键观察是 coldstart 中真正拖慢 image provisioning 的常常不是 download，而是占比至少 68.8% 的 extraction；它把 download、decompression、transmission、unpack 分派到 RNIC、SmartNIC accelerator、PCIe/host memory 和 host CPU 上，用 block-based data-driven pipeline 与 best-effort distributed registry 将 coldstart 相比 containerd / iSulad 平均加速 11.5× / 7.1×，并把 host CPU usage 相比 iSulad 降低 87.5%。

## 问题与动机

论文处理的是 container / serverless coldstart 中的 image provisioning。现有 coldstart 工作常把关注点放在 warm start、snapshot recovery、lightweight isolation 或 fast image download 上；这些路线分别依赖预测命中、状态可恢复、隔离机制替换或只优化网络传输。Poby 的立场更窄也更系统：即使 warm start 和 snapshot 能覆盖热点请求，生产中仍会有新 image、预测失败、突发扩容和冷门函数，因此完全绕开 image provisioning 不现实。

作者的核心 claim 是：image provisioning 不能只看下载，还必须同时优化 download、decompress、unpack 这条完整路径。论文用 containerd 和 iSulad 在多种 runtime image 上的测量说明 extraction 至少占 provisioning latency 的 68.8%，并且 extraction 会对共置业务造成严重 host CPU / IO 干扰；Redis 与 containerd / iSulad 共置时 p99 latency 可上升超过 110×。

Poby 选择 [[SmartNIC]] 不是简单地“把活挪到 NIC 上”。论文明确指出 naive offload 会失败：BlueField-2 这类 SoC SmartNIC 的 ARM cores 弱，若把完整 extraction 放到 on-NIC CPU，计算会变慢；若在 NIC 上 unpack 成大量小文件，再经 PCIe 传回 host，又会把 PCIe transaction 和小 IO 变成瓶颈。因此 Poby 的设计重点是把不同 operation 拆开，映射到各自更适合的硬件。

这篇论文也在回应一个部署层面的痛点：cloud provider 已经大量部署 SmartNIC / DPU，若能把 coldstart 的基础设施税转移到 NIC-side accelerator，同时保持与 OCI image / Docker API 的兼容性，就比要求新 image format 或替换整个 container runtime 更容易落地。

## 关键观察 / 隐含假设

- **观察 1**：image extraction 是 image provisioning 的主导开销，而不是 fast download 文献默认聚焦的网络下载。
  - **证据**：Figure 2 中 Golang、Python、Node.js、PHP runtime 在 containerd / iSulad 下 extraction 均超过 provisioning latency 的 68.8%；Figure 14 进一步显示 iSulad 的 extraction 对 small / medium / large image 都仍是主要时间来源。
  - **依赖假设**：workload 使用传统 compressed container image，需要在启动前完成 decompress + unpack；若平台转向 lazy loading、新 image format 或长期 snapshot cache，这个比例会改变。
  - **可能失效场景**：网络远弱于测试环境、registry 跨地域、image 层已本地缓存、或者 storage backend 已经把 unpack 小文件写入做得极快时，download / metadata / filesystem 可能重新成为瓶颈。

- **观察 2**：extraction 不只是慢，还会显著干扰共置应用。
  - **证据**：Figure 3 中 Redis 与 containerd / iSulad 共置时 p99 latency 最高上升超过 110×，而 Poby 的曲线在 coldstart 后很快恢复，因为 decompression 和 control path 大多离开 host CPU。
  - **依赖假设**：host CPU 是业务和基础设施任务共享资源，coldstart 与 latency-sensitive workload 共置，且 decompression / file writing 对 CPU 和 kernel path 有足够压力。
  - **可能失效场景**：云平台为 provisioning 隔离专用 CPU、使用专用 image service 节点，或把 coldstart 与在线业务调度隔离时，Poby 的“减少干扰”收益会小于论文展示。

- **观察 3**：SmartNIC offload 的收益来自“选择性分解”，不是完整 offload。
  - **证据**：论文挑战 C1 指出 on-NIC CPU 弱、unpacked small files 经 PCIe 传输会低效；Figure 6 显示 decompression accelerator 对大于 16 MB block 平均比 host zlib 快 7×，但 unpack 仍留在 host CPU。Figure 12a 还显示单独加 RDMA 或 accelerator 只比 host CPU workflow 降低约 20%，CPU-side pipeline 再降 34%，仍与完整 Poby 有明显差距。
  - **依赖假设**：SmartNIC 具有可用的 decompression accelerator、足够的 RNIC bandwidth、可编程 control path，并且 host 与 NIC 间传大块数据比传大量小文件更划算。
  - **可能失效场景**：没有 compression accelerator 的 RNIC、PCIe bandwidth / NUMA topology 更差、或 container image 内小文件 unpack 不是主要 host-side work 时，Poby 的硬件映射未必最优。

- **假设 1**：gzip-format OCI image 仍是主流，兼容传统 image distribution 比换格式更有价值。
  - **证据强度**：中。论文引用 Docker Hub 分析称 gzip 占 96.3%，并强调兼容性；但这个数据来自公开 image corpus，未必等同于大型云厂内部 runtime image 的未来格式演化。

- **假设 2**：best-effort distributed download 能在不主动缓存的前提下拿到足够多的 provider。
  - **证据强度**：中。Figure 13b 显示 10% distributed hit rate 已优于 Kraken，70% 可接近 FaaSNET，但 hit rate 本身是实验参数，不是从真实生产 trace 中自然测得。

- **假设 3**：unpack 留在 host CPU 是可接受的 residual bottleneck。
  - **证据强度**：强于“可用”，弱于“已解决”。Figure 14 说明 Poby extraction 平均降 76.1%，但 unpack 在 Poby 总时间中仍占 71.6%；这证明设计避开了最坏路径，也暴露了下一阶段瓶颈。

## 核心方法

Poby 将 image provisioning 拆成四个 data-path operation：image download、image decompression、image transmission、image unpacking。download 使用 [[RDMA]] 进入 SmartNIC memory；decompression 使用 BlueField-2 上的硬件 accelerator；transmission 将解压后的大块数据经 PCIe 传到 host memory；unpack 则保留在 host CPU。这个映射直接回应观察 3：on-NIC ARM core 只做 control path 和调度，不承担高 IPC 的 extraction 计算；host CPU 只处理目前最难 offload 的 filesystem unpack。

这个 disaggregated architecture 还有一个重要顺序调整：先在 NIC 侧把 compressed block 解压成较大的连续块，再传到 host unpack。它牺牲了网络/PCIe上传输的字节数，但避免了“在 NIC 上 unpack 后传大量小文件”的 PCIe transaction 放大。论文认为在 100/200 Gbps RDMA 和 accelerator decompression 的组合下，这个取舍是划算的。

第二个设计是 block-based redundant pipeline。传统 container runtime 常按 layer 并行，但 layer 数量少且大小差异大；time-sliced pipeline 又会被 download、decompression、unpack 这些 stage 的速率不匹配制造 bubble。Poby 把 layer 切为 block，经验选择 16 MB 作为默认粒度：Figure 8 显示 accelerator startup latency 约 6.9 ms，小 block amortization 不够；过大 block 又降低 pipeline 并行度。redundant pipeline 允许本地 accelerator 忙时请求 sender 先做 remote decompression，也允许 host-side unpack thread pool 吸收不同 block 的 unpack 时间差。

第三个设计是 data-driven workflow。block header 携带 `block_index` 和 `block_status`：前者用于定位 block 在 layer / image 中的位置并追踪完成度，后者标记数据是 compressed 还是 decompressed。这样 on-NIC controller 初始化后不需要为每个 block 发送集中控制消息，各 stage 根据 block metadata 自驱动地把数据送往 decompression queue 或 transmission queue。这个设计回应 C2：pipeline 细粒度化后，如果仍靠 centralized controller 调度每个 block，控制消息会吃掉并发收益。

第四个设计是 best-effort distributed image download。Poby 不像 [[Kraken]] / [[FaaSNET]] 那样主动维护完整 P2P cache，而是只从“刚好已有该 layer/image”的节点拉取，失败或 miss 时回退到原 registry。Image Metadata Index（IMI）维护 `Image_IMI` 和 `Node_IMI`：前者记录 image digest 到 provider node 列表，后者记录 node IP 与 active download task count。download plan 按 layer 粒度把任务分配给当前负载较低的 provider，并在 IMI 不一致或 checksum mismatch 时回退 / 重拉。

实现上，Poby 基于 NVIDIA BlueField-2：RNIC 负责 RDMA，multi-core ARM SoC 承担 controller，hardware accelerator 负责 decompression，DOCA 封装硬件交互；host-side 使用 memory pool 管理 block，使用 folly thread pool 做 unpack 并行；data-driven RPC 基于 two-sided RDMA verbs 和 epoll。实验 testbed 只有两台带 BlueField-2 的 worker，加一台带 ConnectX-5 的 registry / IMI server，因此系统层面展示的是 prototype 可行性，而不是完整生产部署规模。

## 设计取舍

- **取舍 1**：Poby 为兼容传统 [[OCI-Image]] 和 Docker API，没有要求新 image format；代价是仍要完整 decompress / unpack，不能像 lazy loading 系统那样按需加载未触达文件。
- **取舍 2**：把 decompressed block 经 PCIe 传回 host，可以避免小文件 PCIe transaction 爆炸；代价是压缩率高时传输字节数增加，论文用 remote decompression 的 18.0% overhead 说明该成本在其 testbed 中可接受。
- **取舍 3**：unpack 保留在 host CPU，降低 SmartNIC implementation complexity，也绕过 on-NIC CPU 弱的问题；代价是 host kernel/file-writing path 成为 Poby 的 residual bottleneck，Figure 14 中 unpack 仍占 Poby 总时间 71.6%。
- **取舍 4**：best-effort distributed download 避免主动 cache 的存储和同步开销；代价是性能依赖历史运行留下的 image locality，hit rate 不稳定时只能退回 centralized registry。
- **取舍 5**：IMI service 与 registry 共置，metadata 小、实现简单；代价是它仍是 centralized control metadata service，论文主要讨论传输瓶颈，没有深入评估 IMI 高并发、故障恢复和多 registry consistency。
- **边界条件**：Poby 在 gzip-compressed image、大块 layer、RDMA-capable datacenter、SmartNIC 带 decompression accelerator、coldstart 与在线 workload 共置时最优雅；在 tiny image、全本地 cache、非 gzip dominant、storage/unpack 极慢或无 SmartNIC accelerator 的环境中收益会变脆。

## 实验与结果

- **端到端 latency**：在 DeathStarBench、OpenWhisk runtime、FunctionBench image 上，Poby 平均比 containerd 快 11.5×、比 iSulad 快 7.1×；最大 speedup 分别为 13.2× 和 8.0×。large image 下 containerd 超过 90 s，iSulad 为 55.3 s，Poby 约 6-7 s。
- **硬件 feature 不是全部答案**：RDMA 或 accelerator 直接套在原 workflow 上只将 latency 降约 20%；CPU-side pipeline 进一步降 34%，但仍与 Poby 有明显差距，说明 disaggregation + block pipeline + data-driven scheduling 才是主要组合贡献。
- **concurrency**：8 个并发 coldstart request 下，Poby latency 相对单 request 增至约 6×，瓶颈转向 network bandwidth；但仍比 iSulad / Kraken 快 4.8×。实验未限制 iSulad 可用 CPU（最多 96 cores），因此 Poby 的优势不是因为 baseline 被 CPU quota 压住。
- **distributed download scalability**：5 节点实验中，Poby-0% hit rate 因单 provider 容量不足 latency 增加 30%；只增加一个 provider 可改善 22%；10% hit rate 已明显优于 Kraken，70% hit rate 接近 FaaSNET。
- **latency breakdown**：Poby 将 extraction time 相比 iSulad 平均降低 76.1%；增加第二个 unpack thread 平均再降 9.1%，medium / large image 超过 11.0%，但更多 unpack threads 没有收益，因为 storage bandwidth 已成为瓶颈。
- **host resource**：large image coldstart 中，Poby 用 6.8 s，iSulad 用 54.6 s；Poby host CPU time 比 iSulad 少 47.8 s（87.5%）。Poby user-mode CPU 占 14.1%，iSulad 为 59.4%；on-NIC CPU peak 16.3%，average 3.0%。
- **block / memory pool**：16 MB block 与 3 个 preallocated blocks 在 medium / large image 上最稳；small image 对更小 block 更友好，但收益有限。这个结果支持 16 MB 作为 throughput-oriented default，而不是所有 image 的绝对最优。
- **network-wide offload**：remote decompression 平均只比 local decompression 多 18.0% latency，额外 network bandwidth 为 2.2 Gbps，即使 image 平均压缩率为 2.7。该结果说明用其他节点 SmartNIC 吸收 accelerator contention 是可行方向。

## Critical Analysis

### 论证链条

论文的主链条相当闭合：先证明 coldstart 仍不可避免，再证明 image provisioning 中 extraction 是被忽略的主瓶颈和干扰源，然后解释为什么 naive SmartNIC offload 不够，最后用 disaggregated pipeline 把各 operation 放到合适硬件上。Figure 12a 的 RDMA / Acc / CPU-Pipeline 对照很关键，因为它避免了“只要有 SmartNIC 就能快”的简单叙事，说明主要贡献是 workflow decomposition。

最强的部分是 observation 到 design 的映射：extraction 慢，所以 offload decompression；on-NIC CPU 弱，所以只放 control；PCIe small file 代价高，所以 unpack 留 host；serial workflow 慢，所以 block pipeline；central registry 会被 RDMA 放大，所以 best-effort distributed download。每个设计都有明确的问题来源。

较弱的跳步在 distributed download。Poby 的 best-effort 策略合理且简单，但论文把 hit rate 作为实验参数，而不是从真实 production image reuse trace 推导。因此“10% 就有收益、70% 接近 FaaSNET”说明机制有效，但还不足以证明实际云环境自然能达到这些 hit rate。

### 假设压力测试

Poby 对硬件假设比较敏感。BlueField-2 的 decompression accelerator、RDMA、DOCA 和 on-NIC programmable controller 是设计的基础；如果部署环境只有普通 RNIC，Poby 仍可借 remote accelerator，但此时性能取决于跨节点资源可用性和额外网络路径。若未来 SmartNIC accelerator 支持的 compression format 与 image ecosystem 脱节，兼容性优势也会削弱。

workload 假设也很明显：论文强调 gzip image 占 Docker Hub 96.3%，但真实 serverless 平台可能有内部基础镜像、预热策略、layer cache、dedup storage 或 lazy loading。对于已经高度优化 image locality 的平台，Poby 的 download 和 distributed registry 部分收益会下降；对于大量小 image，16 MB block 和 accelerator startup amortization 也不是最佳点。

unpack 是最大残留压力点。Poby 把 decompression/control 从 host 移走，但 filesystem write、metadata update、小文件 unpack 仍落在 host kernel path。论文显示 2 个 unpack threads 后 storage bandwidth 成为瓶颈，这意味着在更快 NIC / accelerator 下，Poby 可能更快撞上 storage stack，而不是继续随硬件线性扩展。

### 实验可信度

baseline 选择基本公平：containerd 是主流，iSulad 是更快的 industrial baseline；Kraken 和 FaaSNET 用于 distributed download/scalability 对照也符合问题背景。论文还包含 RDMA-only、accelerator-only、CPU-Pipeline 的内部 ablation，对解释系统贡献很有帮助。

实验边界也很清楚：testbed 是两台 BlueField-2 worker + 一台 registry server，scalability 实验是 5 节点 RDMA cluster，并非大规模生产验证。workload 来自 DeathStarBench、OpenWhisk 和 FunctionBench，覆盖 microservice 与 FaaS，但缺少真实平台 trace 下 image reuse、coldstart arrival burst、tenant isolation 与 registry cache 状态的联合评估。

metrics 覆盖 latency、CPU usage、on-NIC CPU usage、memory block configuration、remote decompression overhead，已经能支撑“Poby 能加速 image provisioning 并降低 host CPU 干扰”。但论文没有深入报告 tail latency distribution of coldstart、failure recovery time、IMI service availability、multi-tenant isolation、SmartNIC power / cost amortization，也没有把 boot / application initialization 计入完整 coldstart latency。因此 claim 的边界应理解为 image provisioning acceleration，而不是端到端 application readiness 的全量解决。

### 系统性缺陷

Poby 引入了跨 host、NIC、accelerator、registry/IMI 的多组件状态机。data-driven block metadata 简化了 per-block control message，但也把 correctness 压到 block ordering、checksum、failure fallback、RDMA connection lifecycle 和 host/NIC memory pool 管理上。论文讨论了 IMI 不一致和传输中 image deletion，用 checksum + re-download 兜底，但没有系统性评估这些异常路径的 latency 和资源影响。

资源隔离方面，Poby 降低 host CPU interference，但把新干扰面移到 SmartNIC。论文测到 on-NIC CPU average 3.0%、peak 16.3%，这对单 workload 很乐观；但实际 SmartNIC 可能同时跑 storage、network virtualization、安全策略、telemetry 或其他 offload。Poby 对 accelerator queue、RNIC bandwidth、NIC DRAM 的多租户隔离没有展开。

可观测性和运维复杂度也未充分讨论。传统 container runtime 的 pull/extract path 已经有成熟日志、重试、registry auth、layer cache 和 security scanning 集成；Poby 把 download / decompress 放到 NIC-side RPC 和 accelerator queue 中，需要新的 tracing、debugging 和 fallback 机制。论文强调 API compatibility，但 operational compatibility 还需要更多证据。

## 局限与 Future Work

- **局限 1**：实验规模偏 prototype，scalability 只到 5 个 RDMA 节点，无法证明 IMI、best-effort provider selection 和 RDMA connection management 在数千节点 burst coldstart 下的行为。
- **局限 2**：distributed download 的 hit rate 是参数化实验，不是 production trace replay；需要真实 image reuse / layer locality trace 才能判断 best-effort 策略在无主动缓存时的长期收益。
- **局限 3**：Poby 仍把 unpack 留在 host，且 unpack 在 Poby 总时间中占 71.6%；当 decompression 更快或 NIC 更多时，storage / filesystem path 会成为更硬的上限。
- **局限 4**：论文没有完整讨论 registry authentication、image security scanning、multi-tenant isolation、SmartNIC 与 host runtime 之间的 failure semantics，这些都是生产 image provisioning path 的关键边界。
- **局限 5**：Poby 以 gzip / OCI image 为主，虽然作者称设计 orthogonal to compression format，但实际 accelerator support、block split、checksum 和 compatibility 都会随 format 改变。
- **Future work 1**：用真实 serverless / microservice trace replay IMI hit rate、provider churn、image deletion 和 burst arrival，量化 best-effort download 在生产 locality 下的收益分布。
- **Future work 2**：把 unpack path 继续拆解为 filesystem metadata、small file write、layer merge / overlayfs 操作，测量哪些部分可由 storage offload、batching 或 image layout 改造客观降低。
- **Future work 3**：评估 Poby 与 snapshot recovery、lazy loading、layer cache、warm pool 的组合，而不是只作为单独 provisioning accelerator；指标应包括 end-to-end application readiness、tail latency 和资源成本。
- **Future work 4**：建立 SmartNIC multi-tenant isolation benchmark：在 Poby 与 network/storage/security offload 共存时，测 accelerator queue、RNIC bandwidth、NIC DRAM 和 on-NIC CPU 的 interference。
- **Future work 5**：为 data-driven block pipeline 增加可观测性和 fault-injection 测试，客观验证 block loss、checksum mismatch、provider timeout、IMI stale entry、NIC reset 下的 fallback latency。

## 相关

- **相关概念**：[[SmartNIC]]、[[RDMA]]、[[Container-Coldstart]]、[[OCI-Image]]、[[Serverless]]、[[FaaS]]、[[Image-Provisioning]]、[[Data-Driven-Pipeline]]
- **同类系统**：[[containerd]]、[[iSulad]]、[[Kraken]]、[[FaaSNET]]、[[DADI]]、[[LineFS]]
- **同会议**：[[ATC-2025]]
- **对比**：[[SmartNIC-Offload]]、[[Container-Image-Distribution]]
