---
type: paper
name: Chen-DataPipelines
full_title: "Teaching The Old Dog New Tricks: Building Efficient Data Pipelines for Large-Scale LLM Pre-training (Operational Systems)"
authors: [Luofan Chen, Chenhan Wang, Weidong Zhang, Jinxin Chi, Hequan Zhang, Zanbo Wang, Chenyuan Wang, Lishu Luo, Sijin Wu, et al.]
venue: OSDI
year: 2026
tags: [llm-training, data-pipeline, hdfs, checkpoint, multimodal]
source_pdf: "[[osdi26-chen-luofan.pdf]]"
source_md: "[[osdi26-chen-luofan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-01
---

# 给传统数据管线加上预测能力（OSDI 2026）

> **原题**：Teaching The Old Dog New Tricks: Building Efficient Data Pipelines for Large-Scale LLM Pre-training (Operational Systems)

> **一句话总结**：论文从 30,000 个生产训练 trace 中发现跨 DC 小张量读取、同步启动热点和多模态 CPU 变换是三类主要停顿来源，分别用预测性 checkpoint 复制、训练框架驱动的热点复制和存储侧 Just-in-Time 变换处理解决，使评估浪费从每次 16,800 降至 4,000 GPU 小时、启动加载时间下降 40.8%，数据加载停顿下降 63.2%。

## 问题与动机

大规模预训练的数据管线同时承载数据集、checkpoint 和 logits。论文研究的生产环境以 HDFS 为存储骨干，训练规模覆盖约 4K–20K GPU，数据量达到 PB 至 EB 级。训练、初始化和 companion evaluation 的访问模式不同，统一采用反应式存储策略会把短时突发流量放大成集群级等待。

作者分析 90 天内 30,000 个训练任务，并重点抽取覆盖约 70% GPU 小时的五类任务。核心主张是：这些瓶颈并非必须更换为 AI 专用存储系统，训练框架已知的确定性可以提前告诉存储层未来需求。

## 关键观察 / 隐含假设

- **观察 1：跨 DC 评估受 RTT 而非带宽主导。** MM-L checkpoint 中超过 60% 的 tensor 小于 16 KB；合并阶段读取约 2.6 TB，跨 DC I/O 占总评估时间约 56.6%，其中 checkpoint merge 占 I/O 时间 84.8%（图 3、表 3）。
  - **依赖假设**：评估周期可预测，且评估集群能够提前缓存目标 checkpoint。
  - **可能失效场景**：checkpoint 产生后立即触发的异常评估、WAN RTT 更低或 checkpoint 布局已连续化时，复制收益会下降。
- **观察 2：启动慢点来自少数共享文件的读竞争。** 在 2,048 GPU 实验中，straggler read 占总等待 67.97%；最热 5% 文件贡献 38.8% 峰值 QPS，常见来源是 metadata、common states 和去重后的 replicated tensor（图 7–9）。
  - **依赖假设**：并行策略和 world size 在提交时已知，热点集合可确定性计算。
  - **可能失效场景**：文件把共享 tensor 与大量 shard 混装时，文件粒度复制会带来额外存储成本。
- **观察 3：多模态加载已从 I/O-bound 变为 CPU-bound。** MM-L 中 transformation 占数据加载时间 94.4%（5.05/5.35 s），最慢主机单步可达 42.72 s；单个 161.9 MB 样本需要 41.5 s 处理（表 5、图 11–12）。
  - **依赖假设**：确定性 dataloader 能准确预测样本顺序，存储节点有可用 CPU。
  - **可能失效场景**：对象存储或存储设备 CPU 紧张时，卸载会与存储服务争抢资源。

## 核心方法

第一，预测性 checkpoint replication 利用固定的评估间隔，在 checkpoint 保存时就把评估所需 shard 批量复制到评估集群。NNProxy 通过全局 namespace 把评估请求导向本地副本；异常触发的评估则携带模型规模、任务优先级和异常程度信号，由调度器抢占后台流量。该设计直接回应观察 1。

第二，Proactive Hotspot Prediction 增加 `SetReplicationHints` 接口。训练框架根据 rank 到 tensor 的映射估计每个文件的并发需求，为 metadata 和 replicated tensor 提前扩容副本，并以 TTL 回收临时副本。实验将热点文件复制因子提高到 128，避免反应式复制在几十秒的风暴窗口内来不及生效。该设计回应观察 2。

第三，Storage-Side Transformation Offloading 把存储节点变成可编程的预处理引擎。存储层读取 per-step info，预测后续二进制块，在 Consumer Queue 中执行解码、裁剪、归一化和帧采样，并把结果按 JIT 顺序送回训练端。CPU 超过约 80% 时触发 backpressure，返回原始字节，由训练端处理，保留共享存储稳定性。该设计回应观察 3。

## 设计取舍

- **提前复制换取启动和评估延迟**：复制消耗额外存储与网络，TTL 和只复制热点文件降低了成本，但无法消除文件粒度布局不佳造成的放大。
- **存储侧处理换取训练端 CPU**：它利用已有存储集群的闲置 CPU，避免专用转换集群传输膨胀后的 tensor；代价是存储层需要理解变换图、维护版本和执行回退。
- **保留 HDFS 换取兼容性**：方案依赖既有数据湖和客户端生态，避免迁移 EB 级数据；代价是仍受 HDFS block 粒度、复制模型和文件布局限制。

## 实验与结果

- 预测性复制与优先级调度使平均 checkpoint merge 延迟下降 76.1%，T-S 达 89.3%、MM-L 达 70.8%；每次回归的 I/O 计算浪费从 16,800 降至 4,000 GPU 小时（§3.4）。
- 2,048 GPU 启动实验中，热点副本因子从默认 3 提高到 128，checkpoint 加载从 38.48 s 降至 22.78 s，下降 40.8%（§4.4，图 9）。
- 存储侧变换使 P99 数据加载延迟下降 85.7%，变换 straggler 导致的训练停顿下降 63.2%，MFU 相对提高 10.8%（§5.4）。
- 训练主机数据加载 CPU 使用量下降 94%（§5.4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 评估延迟主要由跨 DC 小 I/O 与竞争造成 | §3.2、图 3–5、表 3 | 19 个任务、3,589 次评估，生产 WAN | 强 |
| 预知访问模式能缓解启动热点 | §4.2–§4.4、图 7–9 | 2,048 GPU，HDFS，热点副本 128 | 强 |
| 存储侧 CPU 能吸收多模态变换长尾 | §5.2–§5.4、表 5、图 11–12 | MM-L 生产 trace，依赖存储 CPU 余量 | 中 |

## 批判性分析

### 论证链条

三组测量都能对应到具体机制，且结果覆盖评估、启动和稳态训练三个阶段。外推到“传统存储普遍适用”仍有限：实验主体来自单一生产环境和 HDFS，尚未证明对象存储、全 NVMe 或不同 checkpoint 格式下同样有效。

### 假设压力测试

确定性 dataloader 是存储侧预取和变换的基础。动态采样、在线数据增强、数据重访或强化学习工作负载可能破坏顺序预测。评估复制则需要足够提前量；紧急评估只能依赖优先级调度，无法完全避免 WAN 传输。

### 实验可信度

论文提供生产 trace、跨规模任务和消融式瓶颈分解，数字与图表定位清楚。存储侧卸载的对照主要是现有本地变换路径，未充分量化网络、存储 CPU 争抢、多租户隔离和不同 codec 的长期成本。

### 系统性缺陷

论文未详细讨论存储侧变换图的版本一致性、缓存/结果的可观测性、失败重试和安全隔离。临时副本也会增加副本生命周期管理压力；在共享 HDFS 上，TTL 回收与训练失败恢复需要额外运维验证。

## 局限与后续工作

- **局限 1**：存储侧卸载需要存储节点有 20%–30% 甚至更多 CPU 余量，云对象存储和轻量存储设备未必满足。
- **局限 2**：文件粒度复制在共享 tensor 与 shard 混装时会复制不相关数据。
- **后续工作 1**：设计面向恢复 fanout 的 checkpoint packing，把高去重、高读取并发的 tensor 放入独立文件，并测量不同并行策略下的存储放大。
- **后续工作 2**：利用样本大小、codec、分辨率和视频时长建立变换成本模型，验证 cost-aware batching 是否能进一步缩小跨主机 step time 差异。

## 相关

- **相关概念**：[[Checkpoint]]、[[Data Loading]]、[[HDFS]]
- **同类系统**：[[ByteCheckpoint]]、[[SiloD]]、[[Quiver]]
- **同会议**：[[OSDI-2026]]
