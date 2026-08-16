---
type: paper
name: Chen-LLMDataPipelines
full_title: "Teaching The Old Dog New Tricks: Building Efficient Data Pipelines for Large-Scale LLM Pre-training (Operational Systems)"
authors: [Luofan Chen, Chenhan Wang, Weidong Zhang, Jinxin Chi, Hequan Zhang, Zanbo Wang, Chenyuan Wang, Lishu Luo, Sijin Wu, Junqi Hu, Jun Wang, Cheng Chen, Lixin Huang, Liyang Zhao, Yong Tian, Jun Guo, Youhui Bai, Wencong Xiao, Kang Chen, Cheng Li]
venue: OSDI
year: 2026
tags: [llm-training, data-pipeline, hdfs, checkpoint, multimodal]
source_pdf: "[[osdi26-chen-luofan.pdf]]"
source_md: "[[osdi26-chen-luofan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 教传统存储理解大模型训练（OSDI 2026）

> **原题**：Teaching The Old Dog New Tricks: Building Efficient Data Pipelines for Large-Scale LLM Pre-training (Operational Systems)

> **一句话总结**：这篇 ByteDance 生产经验论文发现，大模型训练已经把传统 [[HDFS]] 的三个旧接口推到新瓶颈——异地 evaluation 被小 tensor 的 WAN 往返拖慢，同步恢复把少数 checkpoint 文件读成热点，多模态训练则主要卡在 CPU 解码而不是读盘；系统利用训练框架提前知道的 checkpoint、hot file 和样本顺序，分别把合并延迟降低 76.1%、总 checkpoint 加载时间降低 40.8%、数据转换引起的 stall 降低 63.2%。

## 问题与动机

大模型训练通常把注意力放在 GPU、并行策略和 collective 上，但千卡到万卡的同步任务会放大数据路径中的任何尾延迟：一个 rank 读慢，整组 GPU 都等；一次异地 evaluation 出结果晚，主训练会继续在已经退化的模型上烧卡；一段长视频解码慢，所有机器都卡在下一步 barrier。

ByteDance 已有 exabyte 级 HDFS 数据湖，直接迁移到全新 AI storage 成本很高。论文因此没有重新设计整个存储系统，而是问：**训练框架已经知道下一次会读什么、何时读、为何紧急，能否把这些未来信息提前告诉旧存储？** 三个优化都来自这个原则，但解决的是三个不同阶段的问题，并不是一个统一的数据面。

## 数据和证据范围

论文用了多组不同范围的 trace，不能混在一起：

| 用途 | 范围 | 论文中的作用 |
|---|---|---|
| 总体工作负载池 | 90 天、约 30,000 个训练 job trace | 从中选代表任务；不是说 30,000 个 job 都是万卡任务 |
| 五个代表任务 | 占总 GPU-hours 的 70%，文本和多模态、十亿到万亿参数、约 4K–20K GPU | 表 1–2 的详细 I/O characterization，覆盖 FSDP、FSDP2、[[Megatron\|Megatron]] |
| 异地 companion evaluation | 30 天、19 个 pre-training task、3,589 次 evaluation、156 次关键退化 | 分析 WAN 合并瓶颈和预测复制收益 |
| 启动热点实验 | 一个 2,048-GPU 训练任务 | 比较默认 3 副本和热点文件 128 副本 |
| 多模态转换 | 生产 MM-L trace | 分析 host CPU 长尾和 storage-side offload |

因此，“4K–20K GPU”描述的是选出的五个代表任务，不是整个 30,000-job 池；三个优化的结果也来自不同工作负载和观察窗口。

## 关键观察 / 隐含假设

- **观察 1：异地 checkpoint merge 不是简单的带宽不足，而是小 I/O 与高 RTT 不匹配。** MM-L 的 60% 以上 tensor 小于 16 KB，HDFS block 为 128 MB；按 tensor 取数产生约 1.5 倍 read amplification，并反复支付典型 100 ms 的 WAN RTT。即使链路可提供 60 Gbps，单任务吞吐仍经常很低（图 3–5）。
  - **隐含假设**：周期性 evaluation 和目标 DC 可提前知道，远端有空间接收缓存副本。
  - **可能失效**：evaluation 临时触发、checkpoint 很快失效，或跨地域复制受合规和 egress 成本限制。
- **观察 2：同步恢复的热点来自数据 read，而不是 metadata open。** 在 2,048-GPU 实验中，少数慢 read 占总等待的 67.97%；最热的 5% 文件贡献 38.8% 的峰值 QPS 压力（图 7–8）。全局 metadata 和去重后只保存一份的 replicated tensor 尤其容易变热。
  - **隐含假设**：并行策略、world size 和 tensor-to-rank 映射能在启动前准确给出热点集合。
  - **可能失效**：恢复计划因 elastic resize 或故障临时变化，或者热 tensor 与大块 sharded 参数被打包在同一文件中。
- **观察 3：多模态 data loading 的主成本是转换，不是 I/O。** MM-L 平均 5.35 s 的加载中，decode、crop 等转换占 5.05 s，也就是 94.4%；实际取数据平均只有 13.6 ms（表 5）。storage node CPU 只有 20%–30% 利用率，形成训练端 CPU 忙、存储端 CPU 闲的错配。
  - **隐含假设**：样本顺序确定，转换图可下推，存储节点长期有可用 CPU。
  - **可能失效**：在线随机采样、不可复现的 augmentation、CPU 很紧的存储设备或不允许执行用户转换代码的对象存储。
- **观察 4：三个瓶颈都能由“未来访问信息”缓解。** 定期 checkpoint、已知 world size 和离线生成的 sample order 都是应用层已有、存储层看不到的信息。
  - **隐含假设**：hint 足够准确，并且存储控制面能对错误、过期和恶意 hint 做限流与回收。

## 核心方法

### 1. 预测复制异地 checkpoint

Companion evaluation 通常每约 1,000 个训练 step 运行一次。原流程在 evaluation DC 按 tensor 读取训练 DC 的 distributed checkpoint，先 merge 成各 modality 的 safetensors，再 reshard 后加载。对 MM-L，一轮 evaluation 超过 4 小时，I/O 占 56.6%；merge 又占 I/O 时间的 84.8%，需要跨 WAN 读取约 2.6 TB（表 3、§3.2）。

Predictive Checkpoint Replication 在训练开始保存计划内 checkpoint 时便启动复制，把相关 shard 批成连续的大传输并缓存到 evaluation DC。轻量 namespace 服务 NNProxy 优先把读取重定向到本地缓存，从而绕过大量小 tensor 的跨域往返。对异常 loss 或 gradient 触发的紧急 evaluation，系统再根据模型规模、任务重要性和异常严重度生成 priority signal，让网络 scheduler 优先处理，而不是和归档流量一起 FIFO（§3.3）。

### 2. 在恢复前复制 hot file

普通 reactive replication 要先看到热点，再开始复制；但 checkpoint 恢复通常只持续几十秒，副本准备好时 I/O storm 已结束。训练框架因此通过 `SetReplicationHints` 提前告诉 HDFS：哪些全局 metadata 会被所有 rank 读取，哪些 replicated tensor 文件会被多少 rank 同时读取。系统根据预期并发度和单副本安全负载计算副本数，在恢复前铺开副本，并用 TTL 在启动阶段结束后自动回收（§4.3）。

这个设计只复制热点子集，不是把整个 checkpoint 都放大。它在 FSDP shard 分散、共享结构单独成文件时最有效；如果一个小热 tensor 与大量不热 shard 打包在同一文件中，文件粒度复制会额外复制无关数据。

### 3. 把多模态转换下推到存储节点

生产 dataloader 先离线生成全局确定的读取顺序。原始音频、视频、图像和文本放在 20 GB binary bin 中，约 10,000 个 map 文件、合计约 0.7 TB，负责把 sample ID 映射到 byte range；每步 info 文件给出精确的样本顺序（图 10）。这个确定性计划让存储层能提前准备下一步数据。

Pushdown Transformation Engine 有三部分。第一，训练启动时同步 dataset ID 和 step progress，存储节点自己解析后续 byte range。第二，存储端为每个 job 维护 consumer queue，在 GPU 计算 step N 时，提前读取并执行 step N+1 的 decode、random crop、normalize 等转换；视频先选 frame 再传回，避免把完整解码结果送过网络。第三，当 storage CPU 高于例如 80% 时，系统停止下推、返回原始 bytes，由训练 host 回退到本地转换（§5.3）。

离线预解码不适合这里：视频解码后空间大于原始数据 40 倍，图像也会扩大数十倍；§6 在讨论独立转换集群时估计跨网传输解码 tensor 可能放大 50–100 倍。两个数字针对的表述不同，但都说明永久保存或远距离搬运解码结果代价很高。

## 设计取舍

- **保留 HDFS 降低迁移成本，但需要跨层 hint。** 方案可复用现有 exabyte 数据和生态，代价是训练框架、namespace、replica manager 和 storage worker 都要改。
- **提前复制用空间和网络换等待时间。** 预测正确时消除尾延迟；预测错误时产生无收益流量、副本和缓存回收工作。
- **热点文件复制比全量复制便宜，但受文件布局限制。** tensor 级热度若无法映射到独立文件，复制会放大不热数据。
- **存储侧计算利用闲置 CPU，也扩大故障面。** transformation bug、资源争用或不可信代码现在会影响共享存储；80% fallback 保护可用性，却可能在全局高负载时把长尾重新推回训练端。
- **确定性带来可预测性，也限制通用性。** 论文的 dataloader 有固定全局计划；动态 sampling、RL 数据和频繁变化的 augmentation 不能直接获得相同收益。
- **适用边界。** 方法最适合大规模同步训练、集中式共享存储、可提前知道读取计划且 storage CPU 有余量的环境。

## 实验与结果

### 异地 companion evaluation

30 天内的 19 个训练任务共运行 3,589 次 evaluation，发现 156 次关键模型退化。代表性 MM-L evaluation 的 I/O 延迟很昂贵：156 次退化中，延迟反馈造成约 260 万 GPU-hours 浪费，而整个 evaluation 系统原本帮助节省约 550 万训练 GPU-hours（§3.2）。跨域链路平均还有 208 个任务并发竞争，单任务可用带宽经常少于 1 GB/s。

- **异地 evaluation**：在 30 天、19 个训练任务和 3,589 次 evaluation 的范围内，预测复制加优先级控制把平均 checkpoint merge latency 降低 76.1%，其中 T-S 降低 89.3%、MM-L 降低 70.8%；每次退化的 I/O 诱发浪费从 16,800 降至 4,000 GPU-hours，合计找回接近 200 万 GPU-hours（§3.4）。论文没有把两项机制分别消融。

### 初始化 I/O storm

MM-S trace 中，blocking file download 占启动时间的 39.95%。一个 111 分钟调试窗口内发生 4 次重启，每次平均下载 5 分钟，下载占 18.02% wall time；作者外推为全集群每年超过 100 万 GPU-hours 的损失（§4.1），这个年化值依赖该窗口是否有代表性。

- **启动热点**：在 2,048-GPU 受控实验中，把热点 metadata 和 replicated-parameter 文件从默认 3 副本提高到 128 后，**总 checkpoint loading time** 从 38.48 s 降至 22.78 s，改善 40.8%（图 9）；它不是单次 read 的平均延迟。论文没有报告额外复制字节、准备时间和 storage capacity 成本。

### 多模态转换

- **转换瓶颈**：在生产 MM-L trace 中，转换占平均 5.35 s data loading 的 5.05 s，即 94.4%，而 I/O 仅 13.6 ms；最慢 host 可达 42.72 s，host 间单 step 时间差可到 5 s，作者估计每天浪费超过 10,000 GPU-hours（表 5、§5.2）。

- **转换下推**：相对原有 host-side pipeline，storage-side offload 使生产 MM-L 的 P99 data-loading latency 降低 85.7%，转换 straggler 导致的 stall 降低 63.2%，MFU 相对提高 10.8%，训练 host 的 data-loading CPU 使用量降低 94%（§5.4）。论文没有给出 storage node CPU 增量、逐 modality 结果或 JIT/frame-sampling 消融。

## 论断—证据表

| 论断 | 证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 训练层的未来信息能显著改善异地 evaluation | §3.4：merge latency 平均降低 76.1%，浪费从 16,800 降到 4,000 GPU-hours/退化 | 单一公司、特定 WAN/HDFS；两个优化没有拆开 | 强 |
| 同步恢复主要被少数 hot read 拖慢 | 图 7–8：straggler read 占等待 67.97%，最热 5% 文件贡献 38.8% 峰值压力 | 2,048-GPU 受控任务 | 强 |
| 提前增加热点副本能缩短恢复 | 图 9：总加载 38.48 s 降至 22.78 s | 热文件增至 128 副本；没有成本核算 | 强 |
| 多模态加载主要卡在 CPU 转换 | 表 5：转换占 5.35 s 中的 5.05 s，I/O 仅 13.6 ms | 生产 MM-L trace；不代表文本或其他 dataloader | 强 |
| storage-side offload 能减少训练 stall | §5.4：P99 低 85.7%，stall 低 63.2%，相对 MFU 高 10.8% | 依赖确定顺序和空闲 storage CPU；缺少消融 | 中到强 |

## 批判性分析

### 论证链条

论文最强的部分是 production observation：它没有把“存储慢”当成一个笼统问题，而是分别定位到小 tensor 的 RTT、少量去重文件的读热点和多模态 CPU 转换，再让训练语义直接驱动机制。三条 observation→mechanism→before/after 的链条都很清楚。共同抽象是 application-provided future knowledge，但三个改动彼此松耦合，更像一组经过生产验证的设计经验，而不是一个统一的新系统。

### 假设压力测试

预测复制遇到异常 evaluation 或跨 DC 容量紧张时可能来不及；hot-file hint 遇到 elastic world size 和 restart burst 时可能过时；storage-side transformation 遇到 CPU scrub、compaction 或其他租户高峰时会回退。如果 random crop、decode library 版本或 seed 在 host 与 storage 两侧不同，即使性能更好，也可能悄悄改变训练样本和最终模型。

### 实验可信度

生产规模、跨训练框架与 HDFS 的联合 trace、GPU-hours 和 MFU 等业务指标，使问题真实性很强。主要不足是所有证据来自单一 hyperscaler，trace 仍处于“匿名后计划发布”状态；每项机制大多只有上线前后对比，没有完整 baseline、消融、误预测曲线或置信区间。论文也没有把 WAN、临时副本、storage CPU 和工程运维成本折算成净成本。

### 系统性缺陷

把 hint 和用户 transformation 引入共享存储，会带来新的控制面。论文没有说明 hint 的认证、配额、公平性和 admission policy，也没有覆盖 replica storm、TTL 回收失败、缓存一致性、transform sandbox、storage node failure 与 rollout rollback。尤其是 transformation correctness：确定性计划并不自动保证不同 CPU、codec、library 和随机种子产生完全相同的 tensor。

## 局限与后续工作

- **局限 1**：30,000-job pool、3,589 次 evaluation、2,048-GPU hotspot 实验和 MM-L offload 是不同证据集，不能把其规模和结果相互外推。
- **局限 2**：没有完整成本账本，也没有预测错误、租户竞争、故障和机制消融。
- **局限 3**：数据与系统来自单一公司，trace 尚未公开，外部难以复现。
- **后续工作 1**：扫描 prediction precision、lead time 和 TTL，报告每节省一个 GPU-hour 需要的 WAN bytes、replica GB-hours 和 storage CPU-hours。
- **后续工作 2**：注入错误 hot-file hint、突发 restart、storage node failure 和高 CPU 背景任务，测 P99 加载、回退率、恢复时间和其他租户性能下降。
- **后续工作 3**：记录 transformation graph、codec 版本、seed 和输出 hash，在 host/offload 两种路径逐 sample 比较 tensor，并做短期收敛等价实验。
- **后续工作 4**：在 HDFS、对象存储和一种 AI-native storage 上用同一公开 workload 重跑三项优化，区分通用训练语义收益与当前部署特有收益。

## 相关

- **相关概念**：[[LLM-Pretraining]]、[[Checkpointing]]、[[Data-Pipeline]]、[[Cross-Datacenter-Storage]]
- **相关系统**：[[HDFS]]、[[FSDP]]、[[Megatron-LM]]
- **同会议**：[[OSDI-2026]]
