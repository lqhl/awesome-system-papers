---
type: paper
name: ShieldReduce
full_title: "ShieldReduce: Fine-Grained Shielded Data Reduction"
authors: [Jingyuan Yang, Jun Wu, Ruilin Wu, Jingwei Li, Patrick P. C. Lee, Xiong Li, Xiaosong Zhang]
venue: ATC
year: 2025
tags: [storage, deduplication, delta-compression, sgx, secure-storage]
source_pdf: "[[atc2025-yang-jingyuan.pdf]]"
source_md: "[[atc2025-yang-jingyuan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ShieldReduce：细粒度屏蔽数据缩减（ATC 2025）

> **原题**：ShieldReduce: Fine-Grained Shielded Data Reduction

> **一句话总结**：观察到 backup workload 中 delta compression 的 base chunk 物理局部性会随版本累积而碎裂、在 [[SGX]] enclave 内按需加载 base chunk 会放大 ECall/OCall 与 disk I/O 开销后，ShieldReduce 用 bi-directional delta compression + hybrid inline/offline 设计在 enclave 内跑完整 dedup→delta→local compression pipeline，相比 forward-only baseline 上传吞吐最高 +3.5×，α=0 时压缩比与明文 fine-grained reduction 持平（Web 25.8× vs DEBE 13.1×）。

## 问题与动机

外包备份要同时满足 **存储节省** 与 **数据机密性**，二者天然冲突：常规对称加密使跨 client 冗余不可压缩，而 [[Encrypted-Deduplication]]（convergent encryption / message-locked encryption）虽保留 dedup，但加密后高熵数据无法再做 delta compression 与 local compression，且确定性加密会泄露 chunk 频率信息。

一条直接路线是：在 [[Trusted-Execution]] 环境（本文选 [[Intel-SGX]] enclave）里，对多 client 明文 chunk 先做完整 fine-grained data reduction（dedup → delta → local compression），再用常规对称密钥加密 reduced output 后落盘——这与 DEBE 的 deduplication-before-encryption 思路一致，但 DEBE 未解决 delta compression。难点在于：delta compression 需要为每个新 chunk 检索相似 base chunk；enclave 内存装不下全部 base chunk，按需从持久化存储加载又会叠加 **disk I/O** 与 **ECall/OCall**（约 8000 CPU cycles/次，对比 syscall ~150 cycles）双重开销。

已有 LoopDelta 等 backward delta 主要缓解 chunk fragmentation，未系统处理 shielded execution 下的 I/O-performance-security 三角；MeGA 类性能导向方案则通过跳过大量 delta 机会换速度，牺牲存储。ShieldReduce 的 claim 是：在 SGX 约束下同时逼近明文 fine-grained reduction 的压缩比与可接受的 inline 上传性能。

## 关键观察 / 隐含假设

- **观察 1**：backup workload 具有强 **修改局部性**——相邻版本的小改动往往落在相邻 chunk，且修改 chunk 的 base chunk 在上一版本中物理上也相邻；因此按 batch（默认 128 chunks）加载 base chunk 时，base chunk 通常集中在少数 container（4 MiB）内，可摊销 I/O。
  - **依赖假设**：chunking 用 content-defined（[[FastCDC]]，4/8/16 KiB），相似性检测用 Finesse 三特征；持久化以 container 为单位组织 I/O；备份序列呈渐进式小改而非全量重写。
  - **可能失效场景**：全量镜像替换、跨版本大范围随机改写、或 chunking 边界剧烈漂移时，q/n（base chunk 所在 container 数 / batch 大小）迅速上升，forward delta 退化为 scattered I/O。

- **观察 2**：随备份版本累积，**物理局部性单调下降**——fine-grained reduction 倾向把最早见到的新特征 chunk 选为 base，导致新版本的 delta 越来越指向更老版本里分散的 base chunk；仅 forward delta 会使 container 读取次数随版本数增长。
  - **依赖假设**：chunk 相似性对称（M′ 相似于 M 则 M 也相似于 M′），允许 backward delta：把新 chunk 升格为 base，把旧 base 及已 delta 化的 chunk 重新编码到新 base 上，从而重建物理局部性。
  - **可能失效场景**：backward delta 需要重读、解密、delta-decompress 旧 chunk 并更新 delta/backward index；若相似 chunk 比例低（如 SimOS），offline 收益有限，额外 I/O 可能不划算。

- **观察 3**：SGX enclave 资源与边界调用是性能主导瓶颈，而非 delta 算法本身 CPU 成本——microbenchmark 显示 bi-directional delta（含 locality detection）仅占 write path 计算时间 2.8–8.8%，feature generation 在 Linux/Docker 上占 52–56%。
  - **依赖假设**：dedup 后仍剩大量 non-duplicate chunk 需提特征（Linux DEBE 压缩比仅 5.8×，dedup 收益低）；enclave 内并行度有限（默认 3 线程提特征）。
  - **可能失效场景**：高 dedup 率 workload（如 SimOS 59.3×）下 feature 开销占比骤降，系统瓶颈可能转向加密、网络或单线程 enclave 并行；论文未讨论 TEE 代际迁移（[[AMD-SEV]]、Intel TDX）下的对比。

- **假设 1**：部署模型为「组织在不可信云里托管 enclave-enabled VM，多 client 经一次性 session key（DH + 互认证）把加密 chunk 送入 enclave」；云运营商与部分被 compromise client 为 adversary，但 enclave 内容与代码完整性可远程 attestation 保证。
  - **证据强度**：强——威胁模型、协议与 DEBE 扩展一致，安全讨论覆盖索引泄露与 reduction 量侧信道；侧信道攻击本身显式排除在 scope 外。

- **假设 2**：实验 workload 以长期版本化备份为主（Linux 源码 209 版、网站 78 版、Docker 镜像 95 版、SimOS 合成 OS 快照 30 版），跨 client 冗余通过多 VM 同镜像模拟。
  - **证据强度**：中——Linux/Docker/SimOS 可公开复现，Web 数据集私有；未用真实企业生产 trace，multi-tenant 行为与加密文件比例可能不同。

## 核心方法

ShieldReduce 在 DEBE 的 **frequency-based deduplication** 之上扩展 delta + local compression：enclave 内用小指纹索引（256 K chunks）做第一阶段高频 dedup，enclave 外用全量 fingerprint index 做第二阶段 dedup，减少 enclave 内索引体积与 OCall。

**Locality-based inline compression**（回应观察 1）：每个 batch 去重后，为每个 chunk 用 Finesse 提 3 个特征查 feature index，统计对应 base chunk 分布在多少个 container 上。若 q/n ≤ 阈值 t（默认 0.03），判定 **物理局部性强**，从磁盘加载加密 base chunk 入 enclave、解密、local decompress 后做 **forward delta**（Edelta）+ local compression（LZ4），再 AES-256-GCM 加密落盘；无 base 的 chunk 直接作新 base。同时更新 delta index（base fingerprint → delta fingerprints）供后续 backward 使用。

**Tunable offline compression**（回应观察 2）：若 q/n > t，write path 仅 local compress + 加密存储，把「待 backward delta 的 chunk ↔ 旧 base」映射写入 bounded backward index（默认上限 256 MiB，满则 fallback forward delta）。备份上传完成后，离线阶段按 backward index 选 **最近的新 chunk** 作新 base，对旧 base 及所有相关 delta chunk 做 **backward delta**，并更新 feature/fingerprint/delta index 与 file recipe；用 mark-and-sweep 回收旧物理副本。

**Tunable α**（storage-performance 旋钮）：监控 offline 阶段当前压缩比 α_current = S_current / S_inline，按每个旧 base 关联的 delta chunk 数量升序处理 backward，直到 α_current < α 或处理完毕；剩余旧 base 跳过 backward，直接更新 feature index，以存储换 offline 时间。α=0 追求最大压缩，α=1 仅更新元数据不做 backward。

**存储与元数据**：base chunk 与 delta chunk 分容器类型存储，便于 inline 只拉 base container；fingerprint/feature/delta/backward index 在不可信内存，fingerprint 用 meta key 加密，feature 用 collision-allowed hash 降低可推断性。file recipe 记录每文件 chunk 指纹及 delta 关系，用 per-client master key 加密。下载时 enclave 验证 client、按 recipe 重建明文并经安全通道返回。

与 LoopDelta 的差异：ShieldReduce 根据物理局部性 **自适应 forward/backward**，而非固定 backward；并显式处理已 delta 化 chunk 的重新编码以避免恢复链过长。与 MeGA/SecureMeGA 的差异：不通过跳过 scattered base 的 delta 来换速度，而是用 offline backward 重建局部性。实现约 10.5K LoC C++，基于 Intel SGX SDK 2.15。深度细节回 [[atc2025-yang-jingyuan]] / [[atc2025-yang-jingyuan.pdf]]。

## 设计取舍

- **安全 vs 压缩效率**：选择 shielded reduction + 常规加密，而非 [[Encrypted-Deduplication]] 的弱机密性换跨 client dedup；代价是必须信任 SGX 硬件与 attestation 链路，且 enclave 内完整 pipeline 带来边界调用开销。
- **Inline 延迟 vs 存储**：物理局部性弱时把 delta 推到 offline，避免 write path 随机读大量 container；代价是备份提交后还需数百秒级 offline 作业（Web 上 t=0.05 时 offline ~389s），且 backward 期间 storage 临时膨胀（旧副本 mark 后 sweep）。
- **压缩比 vs offline 成本**：α 越大，跳过越多 old base 的 backward，offline 时间显著下降（Figure 10），但 Web 上压缩比从 58.6×（α=0）降到 14.0×（α=1）；SimOS 因相似 chunk 少，α 对压缩比影响小。
- **索引放 untrusted memory vs enclave 解密开销**：delta/backward index 明文存放可观测相似性关系；全文加密索引可行但增加 enclave 内加解密开销——论文列为开放问题。
- **边界条件**：长期、渐进修改的 multi-version backup（Linux/Web）收益最大；高 dedup、低相似度（SimOS）场景主要吃 dedup 红利，bi-directional delta 优势收窄；10 client 并发后 enclave 资源争用使聚合上传从 826.7 MiB/s 降到 578.1 MiB/s。

## 实验与结果

- **平台**：Alibaba Cloud ecs.r7t.xlarge（32 GiB RAM、4 核 Xeon SGXv2、3 GbE），1 TiB SSD；batch=128，t=0.03，α=0（除非专门扫参）。
- **压缩比**（Table 1，α=0）：Linux 25.8×、Web 58.6×、Docker 14.9×、SimOS 63.6×；与 ForwardDelta（25.1/60.6/15.0/63.3×）基本持平，比 DEBE（5.8/13.1/8.6/59.3×）高出一个 delta 量级；比 SecureMeGA 在 Web 上高 **3.6×**（58.6 vs 16.1）。
- **Inline 上传吞吐**（Exp#3）：相对 ForwardDelta **1.1–3.5×**；相对 DEBE 慢 1.5–2.2×（因 delta 开销）；与 SecureMeGA inline 速度相当，但 offline 后多最高 3.6× 存储节省。
- **多客户端**（Exp#4）：4 client redundant 聚合上传 826.7 MiB/s，10 client 降至 578.1 MiB/s；redundant 下载 1024.6 MiB/s vs unique 738.1 MiB/s（container cache 命中）。
- **Enclave 开销**（Exp#7）：相对 ForwardDelta，ShieldReduce inline OCall 总数最高降 **83.3%**（Linux）；开启 offline offloading 后每 OCall delta 减缩量最高 **4.6×**（Linux 65.9 vs 14.3 KiB/OCall）。
- **参数敏感性**：t 从 0.05→0.1 使 Web inline 从 12.4s 升到 25.5s，但 offline 从 389.3s 降到 155.7s；index 开销 fingerprint+feature 最高 0.39% logical size（Linux）。

## 批判性分析

### 论证链条

逻辑链闭合度较好：measurement 表明 forward-only 在版本增加时 base chunk 跨 container 分散（Figure 3）→ 提出对称相似性下的 bi-directional delta 重建局部性 → hybrid inline/offline 把 scattered 情况移出 write path → Exp#3/#7 显示吞吐与 OCall 效率提升，Exp#1 显示 α=0 时压缩比追平 ForwardDelta。薄弱环节在于 **「inline 速度与 SecureMeGA 相当」** 这一 claim 依赖 MeGA 自身大量跳过 delta 的激进策略，而非同等压缩比下的公平比较；另外 offline 阶段的延迟与 storage 峰值未纳入端到端 SLO 讨论，生产备份窗口是否可接受需结合 α 调参，论文仅给出平均秒级 offline 时间。

### 假设压力测试

- **Workload**：Linux 源码与 Docker 镜像代表开发/容器场景，但 Web 数据集不公开；真实敏感备份可能含高熵已压缩媒体，delta 收益会下降（论文未测）。
- **硬件**：SGXv2 on 32 GiB VM、PL0 SSD（10K IOPS）；下载实验换 PL3（1M IOPS）才测高聚合带宽，说明性能结论与云盘 tier 强绑定。SGX 在虚拟化/cloud 中的 EPC 分页开销被引用但未单独 ablate。
- **规模**：最长序列 209 个 Linux 版本；若上千版本 enterprise backup，backward index 压力、mark-and-sweep 重写 container 的频率与 **恢复路径深度**（多级 delta 链）可能非线性恶化——论文未测 restore latency 随版本数 scaling。
- **多 tenant**：Redundant multi-client 实验基于同一 CentOS 镜像受控修改，真实跨 client OS 镜像 dedup 收益已知（VM disk 研究），但 client 上传时序、quota、恶意填充对 backward index 的影响未建模。

### 实验可信度

- **Baseline 较强**：DEBE（同 lineage）、ForwardDelta（明文 fine-grained 上界）、SecureMeGA（MeGA 适配 shielded），覆盖「无 delta / 全 forward / 性能导向跳过」三个对照。
- **公平性**：各方案共享 DEBE dedup、相同 chunking/batch/线程 defaults；ForwardDelta 与 ShieldReduce α=0 压缩比接近，说明 backward 未显著损伤压缩语义。
- **Ablation**：t 与 α 敏感性、offline offloading 对 KiB/OCall 的对比（Table 4）、microbenchmark 步骤分解（Table 2）支持设计分解；缺少「仅 backward 无 locality detection」「固定 forward + LoopDelta 式 always-backward」等中间变体。
- **Metrics**：覆盖压缩比、inline/offline 时间、吞吐、OCall 计数、index 开销、CPU 利用率；**未系统报告 restore/download tail latency 随版本深度变化**，也未量化 offline 期间 storage amplification 峰值。

### 系统性缺陷

- **尾延迟与 SLO**：multi-client 实验给出聚合均值，无 p99 upload/restore；offline compression 与 mark-and-sweep container rewrite 可能引入长尾 I/O，论文未讨论。
- **故障恢复**：enclave crash、offline 作业中断、backward 中途失败时的元数据一致性与重试策略论文未讨论；delta index + backward index + deletion map 的多阶段更新增加失败窗口。
- **可观测性与运维**：t、α、backward index 容量需运维调参；论文承认未来 adaptive t，但当前仍依赖 workload 专家经验。10 client 后性能下降归因于 SGX 并行局限，Occulum 等多进程 enclave 仅为 future work。
- **安全残余风险**：adversary 可通过 reduction 量与 index 更新模式推断 dedup/delta 关系（§3.5 承认）；padding / selective deduplication 防御会增加存储开销，prototype 未实现。

## 局限与后续工作

- **局限 1**：安全分析排除 SGX 侧信道与 enclave 提取攻击，依赖硬件与 attestation 理想化假设；delta/backward index 相似性泄露的「实际损害」仍为 open question。
- **局限 2**：Web 数据集不公开，最高压缩比结论（58.6×）难以独立复现；feature generation 在 Linux/Docker 上占主导 CPU，成为 inline 瓶颈但未探索硬件 offload 或更轻量特征。
- **局限 3**：offline compression 带来额外时间与临时存储开销，α 旋钮缓解但未给出面向 SLA 的自动策略；multi-client scaling 在 10 VM 即出现 enclave 争用瓶颈。
- **Future work 1**：基于 workload 特征 **自适应配置 t**，在测量 q/n 分布与 inline/offline 时间之间在线学习最优阈值，而非固定 0.03。
- **Future work 2**：量化 **restore path depth** 与 **tail latency** 随版本数、α 的变化，验证 backward delta 是否在生产恢复 SLO 下可接受。
- **Future work 3**：在 Occulum 等多进程 SGX 框架上扩展并行度，并评测 encrypting delta/backward index 的完整安全-性能 trade-off。

## 相关

- **相关概念**：[[Deduplication]]、[[Delta-Compression]]、[[SGX]]、[[Trusted-Execution]]、[[Encrypted-Deduplication]]、[[FastCDC]]
- **同类系统**：DEBE、LoopDelta、MeGA/SecureMeGA、Finesse、SeGShare、S2Dedup、SGXDedup
- **同会议**：[[ATC-2025]]
- **对比**：ShieldReduce 在 shielded execution 下相对 ForwardDelta 换 bi-directional + offline 换 I/O 效率；相对 SecureMeGA 用更多 delta 计算换最高 3.6× 存储
