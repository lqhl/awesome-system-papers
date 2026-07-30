---
type: paper
name: TapeOBS
full_title: "Cost-efficient Archive Cloud Storage with Tape: Design and Deployment"
authors: [Qing Wang, Fan Yang, Qiang Liu, Geng Xiao, Yongpeng Chen, et al.]
venue: FAST
year: 2026
tags: [archive-storage, tape, object-storage, erasure-coding, huawei-cloud]
source_pdf: "[[fast2026-wang.pdf]]"
source_md: "[[fast2026-wang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# TapeOBS：具有成本效益的磁带存档云存储：设计和部署（FAST 2026）

> **原题**：Cost-efficient Archive Cloud Storage with Tape: Design and Deployment

> **一句话总结**：华为云 [[TapeOBS]] 在「drive 稀缺（1000 带仅 4 drive）、mount ~80s、append-only + 寻道慢」的磁带约束下，用 4% 容量的 HDD pool 做全异步缓冲 + batched erasure coding（12+2，冗余 1.17）+ dedicated drives + SSD 元数据引擎，把 restore/write 变成可 bulk 调度任务；10 年 TCO 比 HDD archive 低 **4.95×**（CapEx **2.68×**、OpEx **16.11×**），2024 正式商用后已存数百 PB。

## 问题与动机

云 [[Object-Storage]] 的 archive tier 面向医疗影像、备份、视频素材、日志等「长期保留、极少访问」数据。华为云在 TapeOBS 之前已有 HDD-based archive，但磁带在 CapEx（每 GB 价格低 50%+）、寿命（10 年 vs HDD 5 年）、能耗与 CO2e、存储密度（机房面积省 44%）上优势明显，且 LTO/IBM 3592 路线图清晰（2024–2034 单盒容量年均 +32%）。作者 claim 的核心不是「磁带便宜」这一常识，而是：**把磁带物理特性当成一等系统约束，holistic 重设计分布式 archive，而不是把 HDD 系统里的 medium 换成 tape**。

磁带 library 的三重瓶颈使 naive 替换不可行：(1) **drive-to-tape 比例极低**——TapeOBS 单库 1000 盒磁带仅 4 个 drive，每 drive 360 MB/s；(2) **mount 代价高**——切带约 80s（rewind 旧带 + 机械手搬运 + 新带定位），若每 23.2 GB 就切一次，有效带宽跌一半（drive thrashing）；(3) **append-only + 随机读需 wind/rewind**——与 shingled tracks 类似 [[SMR HDD]]，in-place update 不可行，metadata 随机读代价巨大。Archive workload 虽允许小时级 restore SLA（加急 3–5h、标准 5–12h），但用户 PUT 仍期望接近实时确认；tape pool 聚合带宽远低于 HDD staging，必须解耦用户路径与磁带路径。

## 关键观察 / 隐含假设

- **观察 1：生产 archive workload 极度写多读少，delete 多为 expiration 自动触发而非显式 API**。
  - **依赖假设**：Customer A 读操作仅占 0.000112%，B 最高也仅 0.674776%；多数客户读比为 0；delete 几乎全靠 bucket/object expiration。Dedicated drives 配置（2 写 + 1 读 + 1 internal）和 HDD pool 容量比（tape:HDD ≈ 100:4）都建立在此分布上。
  - **可能失效场景**：若客户批量 restore + 高频 GET（如合规审计、AI 训练回捞冷数据），read drive 与 HDD pool 临时区会成为瓶颈；论文未给出 read-heavy 压力测试。

- **观察 2：对象大小高度偏斜——<500 MB 对象占容量 93.81%，50–100 MB 区间 alone 占 69.95%**。
  - **依赖假设**：b-EC 在 service layer 内存聚合多个 object 再一次性 PLog append 可行；最大客户三大 bucket 平均对象 82–209 MB。Stripe 粒度（12×512 KB data + 2 parity = 7 MB）与对象规模匹配。
  - **可能失效场景**：GB 级大对象占比上升时，b-EC 聚合窗口、HDD pool GC、restore 单请求延迟可能偏离设计点；论文仅 1 个 bucket 平均 >1 GB（占 1.38% 容量）。

- **观察 3：restore 的小时级 SLA 允许把 tape pool 读写全部异步化，从而换取 bulk scheduling 空间**。
  - **依赖假设**：用户接受 restore 后才能在 HDD pool 临时副本上 GET；DataBrain 可按 ddl（小时粒度）收集、按 pt-id 分组、组内按 ⟨plog-id, offset⟩ 排序，制造磁带顺序读局部性。
  - **证据强度**：**强**——产品 SLA 写死 + 生产 24h throughput trace 显示 tape pool 读吞吐峰值仅 5.85Kops/min，远低于写路径。

- **观察 4：drive 切换与带内寻道是 tape library 内主导延迟，而非顺序带宽本身**。
  - **依赖假设**：每 80s 切带一次即有效带宽减半；现代磁带数百 wraps、相邻 wrap 方向相反，逻辑块顺序读会产生大量无效 seek。MetaStore 把 sub-PLog 元数据放 NVMe SSD（10 PB 库仅需 <50 GB）可避免带内随机 metadata 读。
  - **可能失效场景**：SSD 双故障时需从 tape metadata partition 或全带 DIF 扫描恢复，RTO 显著上升；论文给出机制但未量化恢复时间。

- **假设 1：HDD pool 作为持久写缓冲（非仅 restore 临时区）在 4% 容量 + 75% watermark 下可吸收写入突发与 tape library 短期故障**。
  - **证据强度**：**中**——24h 监控显示 HDD 利用率 71.6–71.7%，tape 消化速率平稳；整库故障时 25% headroom 可撑「数十小时」。但未模拟持续超 watermark 的写入风暴或 multi-pool 同时故障。

- **假设 2：按 expiration time（3 个月粒度）做 lifetime-based placement 可使同一磁带数据同时过期，从而把 tape pool GC 降为「整 EC group 删除」为主**。
  - **证据强度**：**中**——HDD pool 仍有周期性 GC spike，但 tape pool「无显著 GC traffic」；依赖用户正确设置 expiration 且删除时间可预测。显式 delete 极少（仅 0.013%）有利，但 lifecycle 策略变更或提前删除会破坏共删假设。

## 核心方法

**架构**：四层——service layer（[[OBS]] API + PLog-Client）、index layer（object ID → ⟨plog-id, offset, size⟩，[[LSM-Tree]] KV 分片复制）、persistence layer（tape pool + HDD pool + MDC）、DataBrain（非实时任务调度）。底层统一 [[PLog]] 抽象：append-only、seal 后不可变，plog-id 由 MDC 分配，pt-id = plog-id % N 映射到 EC group（partition view 存 [[ZooKeeper]]）。

**Tape pool 拓扑**：每 tape pool 14 个 tape rack（共享 service/index/DataBrain，独立 MDC），单 rack = head server（12-core×2、128 GB DRAM、2×3 TB NVMe SSD、25 Gbps×2）+ 单 tape library（Table 2：1000 盒、10.24 PB、4 drive）。多 rack 经 fibre channel 连库；EC 12+2（Huawei LDEC，MDS array code）跨 14 rack 分布，冗余 **1.17**。HDD pool 复用成熟 HDD-based OBS，容量约为 tape pool 的 **4%**。

**原则 1 — 最小化 drive thrashing**：
- **Dedicated drives**（§4.2）：4 drive 静态划分为 2 write + 1 read + 1 internal（GC、EC repair、consistency check）。写 drive 通过 MDC 保证每库仅 2 个 active partition，pin 到固定磁带 log-structured append 至满；读/内部任务分离避免互相切带。库满后 2 写 drive 转 1 读 + 1 internal。
- **Batched Erasure Coding（b-EC）**（§4.3）：不改 persistence 层语义，由 service layer 聚合多 object（如 5 个共 1.5 GB）一次 PLog append + seal，再水平切 12 data chunk。效果：单 object 大概率只落一条带，restore 不必同时 mount m 条带。**代价**：tape 故障时 degraded read 重建数据量从 S 增至 S×m（m=12）。

**原则 2 — 避免带内随机读**：tape-tailored local storage engine（§4.5）含 **VDB**（MetaStore + DataStore，固定长 KV 数组 + DRAM hash）、**TLS**（SCAN 读调度 + flow control 对齐 host 提交速率与 drive buffer，避免 drive 误选低速档）、**TLM**（机械手/drive 控制）。Tape 满后将 sub-PLog 元数据 dump 至 **metadata partition**；每 4 KB 数据附 DIF（plog-id、offset、checksum）支持自恢复与后台 consistency checking（含 CPU SDC 检测）。

**原则 3 — 全异步 tape pool + bulk scheduling**（§4.4）：写路径用户 → HDD pool（高可用 EC）→ DataBrain 按 delete time 分组 bulk flush 至 tape pool；读路径 restore 请求 → 异步从 tape 拷至 HDD pool 临时副本 → 用户 GET。Restore 调度：最小 ddl 任务集 → 按 pt-id 分组 → 组内 ⟨plog-id, offset⟩ 排序 → 顺序下发，配合 TLS 的 wrap-aware SCAN。

**正确性与修复**：4+2 示例用于讲解流程；生产为 12+2。Tape crash 或 checksum/parity 不一致触发 EC repair；GC 以 EC group 为单位重写有效对象后释放磁带。

## 设计取舍

- **成本 vs 层次复杂度**：引入 HDD pool、DataBrain、MDC、双 SSD 元数据层，显著增加控制面与运维组件，换取 TCO 4.95× 与数百 PB 可运营性；比「单池直连磁带」复杂得多，但作者认为这是 tape 上 archive 的必要 tax。
- **写吞吐 vs 读能力**：Dedicated drives 优先 2 写 1 读；archive 写主导合理，但 read drive 单点且不可弹性——论文建议可按小时粗粒度重分配 drive，生产未启用。
- **EC 强度 vs restore 并行度**：12+2 低冗余省空间、少写带宽，但无 b-EC 时单 object restore 需 12 条带；b-EC 缓解 thrashing 却放大 degraded repair 读放大。
- **异步 SLA vs 用户感知写延迟**：用户写完成点在 HDD pool + SSD DataStore（tape pool 写 stripe P50 **18.51 ms**、P99 **27.75 ms** 是 persistence 层「到 SSD 即完成」，非落带延迟）；真正落带异步，durability 边界需用户理解两层持久化。
- **边界条件**：单 AZ 部署；无 deduplication（加密数据压缩率低，压缩已在 service layer）；SCAN 只优化纵向寻道，未建模 wrap 切换纬度最优（相关 work 有更强算法）；tape 视为整盘故障域，不考虑 partial tape failure（对比 Quantum 2D EC）。

## 实验与结果

- **TCO 模型**（100 PB 起步、年增 50%、10 年）：tape vs HDD archive 的 CapEx **2.68×**、OpEx **16.11×**、总 TCO **4.95×** 优势。
- **部署规模**：2022 末灰度、2024 商用；单 pool 14 rack × 10.24 PB ≈ **140 PB**；多 cluster；截至撰写已存 **数百 PB** raw user data。
- **Workload**（§5.1–5.2）：对象容量 CDF 极度偏斜；TOP5 客户写占比 **99.33–100%**，读最高 0.67%；delete 几乎为 0。
- **容量与吞吐**（24h 代表 cluster，§5.3–5.4）：HDD pool 利用率 **71.6–71.7%**（watermark 75%）；tape 消化速率平稳。Tape pool 写吞吐均值 **118.81Kops/min**（每 op 7 MB stripe ≈ **831.67 GB/min**），读峰值 **5.85Kops/min**。HDD pool 写/读均值 **134.0/158.1 Kops/min**（读含向 tape flush + 周期性 GC spike）。
- **延迟**（§5.5）：tape pool 写 stripe 到 SSD 完成 P50 **18.51 ms**、P99 **27.75 ms**（网络 ~10 ms，DataStore 1–4 ms，余下为 EC/checksum/拷贝）。
- **故障**（§5.6，~1.25 年、<200 libraries）：17 起 tape-library 相关故障——drive 软件 bug / 硬件故障 / 不识带 / accessor 卡住 / head server 断连等；整库不可用时 HDD pool 25% headroom 可吸收继续写入「数十小时」。

## 批判性分析

### 论证链条

论文的 observation → design → result 在 **「archive = 写多读少 + 可小时级 restore」** 这一主线上较闭合：生产客户操作比、对象大小 CDF 直接支撑 dedicated drives、b-EC、HDD staging；80s mount 与 360 MB/s 带宽的 back-of-envelope 解释 drive thrashing 动机；24h utilization/throughput 与异步调度叙事一致。薄弱环节在于 **成本优势主要停留在自建 TCO 模型**，缺少与 AWS Glacier / GCP Archive / 自家 HDD archive 的端到端 $/GB-month 或 restore 费用对比；性能结果几乎是单 cluster 监控快照，缺乏 ablation（如无 b-EC、shared drives、无 lifetime grouping）量化各设计的边际收益。

论证还把「SSD 完成即 write latency」与「用户感知持久化」混在同一指标叙事里——18 ms 反映的是 staging 路径，真正 tape 落盘延迟与 durability window 未单独报告，对合规场景可能关键。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 写:读 ≫ 1 | TOP5 客户操作比 | 冷数据训练、诉讼取证导致 restore 风暴 |
| 对象以 50–200 MB 为主 | 容量加权 CDF | 大对象、小对象海量 metadata 混合 |
| expiration 可预测且 3 月粒度足够 | HDD GC 仍周期性发生 | 用户频繁改 lifecycle、提前删打破共删 |
| 4% HDD pool + 75% watermark 够缓冲 | 24h 稳态监控 | 多 rack 同时故障 + 持续写入高峰 |
| 单 AZ + 12+2 跨 rack EC 满足 SLA | 数百 PB 运营 | 区域级灾难需跨 AZ 复制；论文明确单 AZ |
| b-EC 聚合在 service 内存可扩展 | 设计描述 | 超大对象或极高 QPS 小对象聚合压力 |

### 实验可信度

- **优势**：真生产系统、数百 PB 规模、含失败表征（17 起故障分类）、workload 统计来自多客户；比纯仿真 tape 模型更有外部效度。
- **局限**：**无第三方 baseline**（Glacier、内部 HDD archive 同链路对比缺失）；性能章节是 **1 个 cluster 的 24 小时窗口**，无季节性/促销写入峰值；关键设计（b-EC、dedicated drives、lifetime placement、flow control）**无逐项消融**；TCO 模型假设 50% 年增长与特定运维成本，敏感性未展开。
- **指标覆盖**：重吞吐、容量、故障计数；**restore 尾延迟 SLA 达成率**、跨客户 fairness、GC 重写成本（字节数/能耗）未报告。

### 系统性缺陷

- **尾延迟与多租户**：flow control 稳定单 drive 带宽，但 **multi-tenant restore 同 ddl 截止**时的调度公平性、HDD pool 临时副本挤占 watermark 风险论文未量化。
- **故障恢复**：EC repair、accessor 卡住、head server 断连有描述，但 **RTO/RPO**、metadata partition 重建耗时、双 SSD 失效全带 DIF 扫描成本未给数字。
- **可观测性与运维**：DataBrain + MDC + partition view 增加状态面；drive 软件 bug 需人工升级固件——17 起故障中 drive 类占多数，长期 MTTR 未讨论。
- **安全与合规**：tape 硬件加密能力在背景提及，但 **租户隔离、密钥轮转、合规删除证明** 论文未展开。
- **扩展性**：单 pool 140 PB、单 AZ；跨 AZ/跨地域 archive 的延迟与成本论文未讨论。

## 局限与后续工作

- **局限 1**（论文自述）：Dedicated drives 在动态 workload 下可能 **资源欠利用**；粗粒度（如小时级）重分配可缓解但未生产验证。
- **局限 2**（论文自述）：b-EC 增加 **degraded read** 数据量（S → 12S）；tape 故障虽少但修复成本更高。
- **局限 3**（论文自述）：TLS 的 SCAN 只优化纵向维度，未利用 wrap 切换的完整寻道模型（相关 work 有更优算法）。
- **局限 4**（部署边界）：当前 **单 AZ**、**无 deduplication**、未启用 tape library 内置压缩（加密数据为主 + service 层已压缩）。
- **Future work 1**：在 **read-heavy / 大规模 restore 突发** trace 上测量 read drive + HDD 临时区瓶颈，量化动态 drive 重分配收益。
- **Future work 2**：对 **lifetime-based placement** 做敏感性分析——expiration 粒度、用户提前删除、跨租户 混写对 tape pool GC 字节重写量的影响。
- **Future work 3**：补充 **durability window** 测量：从 HDD 确认到 tape 落盘完成的 P99 时间，以及双 SSD / 整库故障时 MetaStore 重建耗时。
- **Future work 4**：与 **跨 AZ erasure** 或 **2D EC**（intra-tape + inter-tape）方案做 TCO–durability Pareto，评估单 AZ 假设放松后的代价。

## 相关

- **相关概念**：[[Erasure-Coding]]、[[Object-Storage]]、[[Garbage-Collection]]、[[Log-Structured-Write]]、[[SMR HDD]]、[[Cold-Storage]]
- **同类系统**：[[AWS Glacier]]、[[Google Cloud Storage]] Archive、Alibaba Cloud Archive、[[Pelican]]、[[SMRSTORE]]、[[LTFS]]、GLUFS、[[Tectonic]]
- **同会议**：[[FAST-2026]]
- **对比**（架构相近）：HDD-staged tape 系统 vs 纯 HDD archive——成本换复杂度与 restore 延迟
