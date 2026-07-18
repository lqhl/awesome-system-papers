---
type: paper
name: 2DFS
full_title: On-Demand Container Partitioning for Distributed ML
authors: [Giovanni Bartolomeo, Navidreza Asadi, Wolfgang Kellerer, Jorg Ott, Nitinder Mohan]
venue: ATC
year: 2025
tags: [container, oci, distributed-ml, edge-computing, model-serving, image-build]
source_pdf: "[[atc2025-bartolomeo.pdf]]"
source_md: "[[atc2025-bartolomeo]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# On-Demand Container Partitioning for Distributed ML (ATC 2025)

> **一句话总结**：2DFS 的关键观察是 Docker/OCI 的线性 layer DAG 把 ML model split、权重更新和 image variant 绑定成级联重建问题；它用 `2dfs.field` 二维 allotment 矩阵把大文件变成可并行构建、独立缓存、按需导出的 OCI artifact，在 14 个模型上实现平均 56x split-image build 加速、25x update-cache 加速，并把 partition pull 额外延迟压到约 20 ms。

## 问题与动机

这篇论文解决的不是如何切分模型本身，而是切分后的模型如何继续用 [[Container]] 生态部署。作者的出发点是：distributed ML、split computing、continuous retraining 已经让模型在多个设备、多个 split、多个版本之间动态变化，但主流 MLOps 最终仍把模型、依赖和运行环境打进 Docker/OCI image。这样一来，模型权重和 partition 这种大而常变的数据被迫服从传统 layered filesystem 的顺序变化语义。

在传统 [[OCI-Image]] 中，一个 layer 的 hash 改变会让它上方的 layer、manifest、index 产生级联失效。这个机制适合表达「代码和依赖按 Dockerfile 顺序叠加」的构建历史，却不适合表达「多个模型 split 彼此独立、只需要按需组合」的部署需求。对 split computing 来说，如果每个可部署 partition 都预构建成独立 image，n 个 split 的组合空间会接近 2^n；如果只在应用启动时从模型仓库下载权重，又绕过了 container runtime 和 registry 已有的缓存与分发机制。

2DFS 的作者选择不重做 MLOps storage 或 runtime，而是在 OCI image format 上加一个新的 `2dfs.field` layer type，让 registry 继续承担内容寻址、缓存和分发职责。论文的核心 claim 是：只要把模型 split、权重、库、driver 这些静态大文件从线性 layer 序列中抽出来，放进二维 hash-pointer field，就能用较小的 registry 改动获得大幅 build/update 加速，同时保持 runtime 侧 OCI 兼容。

## 关键观察 / 隐含假设

- **观察 1**：distributed ML 的 deployment artifact 数量随 split 和设备变化爆炸，而 Docker image build 仍按顺序 layer 处理。
  - **证据**：ENv2L 最多 82 个 split；论文用 ENv2L 展示 split 数增加时 Docker build 时间从约 82 s 增到约 243 s，并指出预构建所有 partition manifest 会出现组合爆炸。Figure 8 中，为每个 split 预构建 Docker image 时，2DFS 平均快 56x，ENv2L 100% split capacity 下峰值快 120x。
  - **依赖假设**：生产环境确实需要频繁生成不同 split/partition，而不是长期固定少量 deployment profile。
  - **可能失效场景**：如果实际系统只部署 1-2 个稳定 partition，或者已有 centralized image baking pipeline 能提前隐藏构建延迟，2DFS 的主要收益会变小。
- **观察 2**：模型更新经常只改变部分权重或 split，但线性 layer cache 会让下游 layer 级联失效。
  - **证据**：模型 update 实验分别更新 25%、50%、75%、100% split。Top-down 更新下 Docker 平均比 2DFS 慢 25x；bottom-up 更新下最坏慢 75x，因为底部 layer 失效会迫使上层重算。
  - **依赖假设**：模型权重、架构文件、binary 可以被拆成互不覆盖、可交换的 allotment；更新粒度能与 allotment 粒度对齐。
  - **可能失效场景**：如果文件之间存在路径覆盖、安装脚本副作用、post-install mutation，或者更新总是整模型替换，allotment independence 就不再自然成立。
- **观察 3**：OCI registry 已经是一个可复用的 content-addressed object store，缺的是对「subset export」的 image-level 表达。
  - **证据**：2DFS partition pull 在 ENv2L/RN50 的 25%-100% partition 上比预构建 Docker image 平均只多约 20 ms；client bandwidth 基本持平；registry CPU 在 50th percentile 后约多 1%。
  - **依赖假设**：partitioner 的工作主要是 manifest/config rewrite 和 blob selection，而不是动态重新压缩大量数据；registry CPU、cache 和网络不会成为多租户瓶颈。
  - **可能失效场景**：公网 registry、跨区域 pull、冷 cache、多租户高并发、auth/policy 检查复杂化时，20 ms LAN 结果可能低估真实开销。
- **假设 1**：2D field 是足够好的用户接口。
  - **证据强度**：中。论文展示了 row/column 矩形 sub-field 和语义 tag `tag--x1.y1.x2.y2`，也在 appendix 讨论按权重、networking binary、inference lib、GPU driver 分区；但没有用户研究或复杂 workload 下的 layout tuning 成本评估。
- **假设 2**：OCI 兼容比 runtime 最优性更重要。
  - **证据强度**：强。设计明确把 partition 序列化回普通 OCI layer，让现有 runtime 无需修改；代价是受 Docker 等 runtime 的 127 layer 限制约束。

## 核心方法

2DFS 在普通 OCI image 上附加一种新的 `2dfs.field` media type。这个 field 是一个稀疏二维矩阵，每个格子是一个 allotment，记录 `row`、`col`、`digest` 和 `diffid`。allotment 指向标准 `.tar.gz` blob，本质上仍是 OCI artifact；新意在于这些 blob 不再表达 Dockerfile 的顺序历史，而是表达一组可独立选择、可独立缓存的静态文件集合。首次构建时，2DFS builder 把 base image 扩展成 OCI+2DFS image，并把 field metadata、allotment blob 和普通 image index/manifest 放进 cache。

这个设计回应了观察 1 和观察 2：模型 split 不再必须变成一串顺序 layer。只要开发者在 `2dfs.json` 中声明每个 split 或文件集合的源路径、目标路径和二维坐标，builder 就能并行计算每个 allotment 的 uncompressed DiffID 和 compressed blob digest。因为论文要求 allotment 之间满足 commutative、non-overlapping、serializable-to-OCI-layer 这几个属性，builder 可以跳过 Docker 那种「起 build container、copy 文件、提取 changeset」的顺序流程。

cache hierarchy 分为 Key Cache、Blob Cache、Index Cache。文件内容变化会先影响 file/content key，再影响 compressed blob key，最后重建 field/index metadata。和 Docker 的区别在于，变化只沿着单个 allotment 的构建链传播，不会因为 layer 顺序关系自动 invalidates 其他 allotment。这个机制的边界也很清楚：2DFS 把收益建立在「静态文件集合」上，而不是任意 Dockerfile 指令语义上。

image partitioning 是第二个核心。用户通过 semantic tag 表达矩形 sub-field，例如 `registry/repository/image:tag--x1.y1.x2.y2`。2DFS-compliant registry 在 manifest endpoint 解析这个 tag，取出对应 allotment blob，把它们 flatten 成普通 OCI layer，更新 config 中的 DiffID 列表，并返回一个 runtime 可以直接 pull 的普通 OCI image。runtime 侧透明，registry 侧需要增加 partitioner、semantic tag parser 和 `2dfs.field` deserializer。

论文的 ML split 生成不是贡献重点，但它决定了 evaluation workload。作者用 Keras API 根据 information bottleneck 选择 split point：避免 branch/shortcut 处切分以减少跨设备 tensor 传输，尽量增加 split 数以提高部署灵活性，并尝试平衡各 split 的 inference time。14 个模型覆盖 recognition、detection、segmentation，split 数从 RN50 的 18 到 ENv2L 的 82。

## 设计取舍

- **取舍 1**：2DFS 牺牲了 OCI image format 的纯标准性，换取现有 runtime 兼容。Registry 和 builder 必须理解 `2dfs.field`，但最终导出的 partition image 是普通 OCI layer，因此 Docker 等 runtime 不需要改。
- **取舍 2**：把 Dockerfile 的通用顺序语义换成静态 allotment 语义。收益是并行构建和细粒度 cache；代价是用户要自己保证 allotment 不互相覆盖、无顺序副作用、适合被任意顺序 apply。
- **取舍 3**：semantic tag 让 partitioning 不需要新 API endpoint，但也把一个结构化选择语言塞进 image tag。它简单且易接入现有 pull path，不过复杂 policy、可观测性和错误诊断可能变得不直观。
- **边界条件**：2DFS 在大模型权重、driver、binary、model variant 这类大而静态、可拆分、频繁局部更新的 artifact 上优雅；在需要运行安装脚本、产生大量小文件 mutation、依赖 layer 顺序覆盖语义的通用应用构建中会变脆。
- **兼容性边界**：论文指出当前只支持 OCI image，不支持 conventional `vnd.docker` format；同时传统 OCI runtime 通常最多处理 127 layers，所以 `2dfs.json` 需要保证单个 partition 不超过 127 个 allotment。

## 实验与结果

- **Build time for one full image**：在 14 个模型上，2DFS 构建 OCI+2DFS image 平均比 Docker 构建标准 OCI image 快 16x。ENv2L 这类大模型在 Docker 中存在 layer size 与 layer count 的 tradeoff，50% split capacity 附近较快；2DFS 则随 split 增多更容易并行，直到 I/O 接近瓶颈。
- **Build time for split partitions**：当 Docker 需要为每个 split/partition 预构建独立 image，而 2DFS 只构建一个 full field image 时，2DFS 平均快 56x；ENv2L 100% split capacity 下峰值快 120x。MNv2L edge 实验中，为 1-10 台设备动态重算 split 时，2DFS build 侧快 55.9x。
- **Builder resource usage**：2DFS 内存使用与 Docker 相近，但 CPU 使用更高，尤其 split capacity 增加后更明显。论文的解释是 2DFS 并行计算 DiffID 和 blob，瞬时 CPU 更高但总 build time 更短。
- **Partition pull overhead**：对 ENv2L/RN50 的 25%、50%、75%、100% partition，2DFS on-demand partition pull 比预构建 Docker image 平均只多约 20 ms；download bandwidth 基本一致；registry CPU 只出现约 1% 的轻微上升。
- **Model update caching**：top-down 更新时 Docker 仍能缓存底部 layer，但平均比 2DFS 慢 25x；bottom-up 更新时 Docker 需要重算上层，最坏比 2DFS 慢 75x。RN50 场景中，传统 container update 约 6-20 s，2DFS 约 1-1.5 s。
- **Edge split computing smoke test**：10 台 Raspberry Pi 4B 上运行 MNv2L split pipeline，吞吐从小于 1.3 requests/s 增到 7.6 requests/s，同时端到端响应时间随设备数线性上升，说明 pipeline parallelism 有吞吐收益但 network/fragmentation latency 仍存在。
- **Exported image size**：Appendix B 中 ENv2L/RN50 的 exported OCI+2DFS image 与 Docker image 大小几乎相同，说明 `2dfs.field` metadata 本身没有明显空间膨胀。

## Critical Analysis

### 论证链条

论文的主链条比较闭合：Docker/OCI layer DAG 对局部权重更新和动态 split packaging 不友好；2DFS 把静态大文件拆成独立 allotment；独立 allotment 让 build 和 cache invalidation 粒度变小；registry partitioner 再把需要的 allotment 导出为普通 OCI image。实验也覆盖了这条链的关键环节：build、update cache、partition pull、registry overhead、一个小型 edge deployment。

最强的地方是问题重构：作者没有把 split computing 的性能问题继续归因到模型切分算法，而是指出 packaging layer 已经成为实际部署瓶颈。这个角度很系统味，且 2DFS 的改动面相对克制。

跳步在于 generalization。论文多次暗示 2DFS 可用于 LLM shard、fat image、microservice packaging、federated learning，但实验主要还是 vision model split 与 Raspberry Pi LAN。对 LLM serving 来说，artifact packaging 只是 warmup/deployment 的一部分，真正线上瓶颈可能是 [[KV-Cache]]、scheduler、GPU memory、interconnect、checkpoint loading 和 multi-tenant admission control；2DFS 的收益需要另行证明。

### 假设压力测试

2DFS 最核心的压力点是 allotment independence。论文要求 allotment 可以任意顺序 apply 且不改变 final filesystem state，这对模型权重文件很合理，对通用 container filesystem 未必合理。许多 Dockerfile 依赖顺序覆盖、package manager state、symlink、permission、post-install script、generated cache。若这些行为进入 allotment，2DFS 要么要求用户手工重构 layout，要么需要更复杂的 conflict detection。

第二个压力点是 registry 负载。论文在 1Gb/s LAN、单 worker pull、有限模型集上展示 partition overhead 很小，但生产 registry 常常有 cold cache、WAN、auth、rate limit、scan/signature policy、multi-tenant noisy neighbor。partitioner 如果成为 manifest endpoint 上的动态计算路径，尾延迟和可用性需要更强的评估。

第三个压力点是 split layout。二维坐标把 partition 表达得很简单，但谁来决定 layout、如何演化 layout、旧 tag 如何兼容、新模型版本如何迁移，论文只给了直觉和 appendix example。对经常重训练的系统，layout stability 可能和缓存命中率一样重要。

### 实验可信度

build/update 实验比较可信，因为 baseline 是 Docker 27.3.1、BuildKit 默认配置，硬件信息充分，模型 zoo 有 14 个真实模型，重复 10 次取 median。它很好地证明了「当目标是打包大量静态 split 文件」时，Docker 的顺序 layer 构建和 cache invalidation 是主要开销。

不过 baseline 也有一个天然劣势：Docker 被要求模拟 2DFS 的 partition flexibility，需要构建多张 image。这个设定符合论文问题定义，但不是所有部署都会这么做；一些系统可能把权重放 object store、把 image 固定、用 sidecar/cache preload 弥补 runtime 缓存缺口。论文讨论了这些替代方案的工程成本，但没有直接实验比较。

pull-time 实验覆盖 download time、bandwidth、registry CPU，但没有覆盖并发 pull、cache miss、large registry state、失败恢复、security scanning、signature verification。edge 实验证明 2DFS 可以跑通 distributed split deployment，但更像 end-to-end demonstration，不足以证明 split computing 本身的性能优势。

### 系统性缺陷

论文未讨论的最大运维问题是 observability 和 debugging：当一个 semantic tag 动态导出 manifest，用户如何追踪它实际包含哪些 allotment、如何复现某次 pull、如何做 SBOM / vulnerability scan / provenance attestation，都需要系统设计。OCI artifact 和 registry 生态有现成机制，但 2DFS 把 artifact selection 延迟到 pull path 后，供应链工具是否仍然自然工作没有展开。

资源隔离也未充分讨论。Registry partitioner 变成主动计算组件后，需要限制单个请求的 partition complexity、concat sub-field 数量、cache 占用和 CPU 时间，否则 image pull endpoint 可能被滥用为计算热点。

正确性方面，2DFS 依赖 builder 保证 allotment commutativity，但论文没有给出静态检查或冲突检测机制的细节。如果两个 allotment 写同一路径、权限或 metadata 冲突，系统是拒绝、按顺序覆盖，还是产生未定义行为，这一点需要明确。

## 局限与 Future Work

- **局限 1**：当前只支持 OCI image；对 conventional Docker media type 的兼容需要额外处理。
- **局限 2**：为了让导出的 partition 能被现有 Docker/runtime 使用，单个 partition 实际受 127 layer 限制，超大模型或过细 allotment layout 会碰到上限。
- **局限 3**：实验主要在 vision model split、单 registry、LAN 环境中完成；没有证明公网、多租户、冷 cache、高并发 registry 下的 tail latency。
- **局限 4**：2DFS 假设 artifact 是静态文件集合，不覆盖通用 Dockerfile 指令语义，因此它更像「大文件/模型 artifact packaging layer」，不是 Docker build 的完整替代。
- **Future work 1**：实现 allotment conflict checker，客观测量不同模型/应用 layout 下的 path overlap、permission conflict 和 cache hit rate。
- **Future work 2**：在高并发 registry benchmark 中测量 partitioner 的 p50/p99 latency、CPU、memory、manifest cache 命中率，并与 object-store-plus-sidecar 方案对比。
- **Future work 3**：设计超过 127 allotment 的 runtime/storage driver，测量是否仍能保持 Docker 兼容路径上的简单性，还是需要转向 2DFS-specific runtime。
- **Future work 4**：把 2DFS 用在 LLM checkpoint/shard 部署上，分别测量 image build、checkpoint loading、GPU warmup、rolling update 时间，避免把 packaging 加速误当作 serving 加速。

## 相关

- **相关概念**：[[Container]]、[[OCI-Image]]、[[Split-Computing]]、[[Edge-Computing]]、[[MLOps]]、[[Model-Serving]]
- **同类系统**：[[vLLM]]、[[DeepSpeed]]、[[SkyPilot]]、[[MLflow]]、[[Kubeflow]]
- **同会议**：[[ATC-2025]]
