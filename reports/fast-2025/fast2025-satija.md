# Cloudscape: A Study of Storage Services in Modern Cloud Architectures

**作者**：Sambhav Satija, Chenhao Ye, Ranjitha Kosgi, Aditya Jain, Romit Kankaria, Yiwei Chen, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau (University of Wisconsin–Madison); Kiran Srinivasan (NetApp)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/satija
**源文件**：[fast2025-satija.pdf](../../papers/fast-2025/fast2025-satija.pdf)

---

## 一、背景

云计算已成为服务开发和部署的主导平台。2023 年，云计算基础设施投资占全球 IT 基础设施支出的约 60%，预计未来几年将以 16% 的复合年增长率持续增长。然而，尽管云的重要性日益增长，学术界对云系统的实际构建方式——特别是存储服务如何被选择和使用——缺乏系统性的理解。现有研究主要聚焦于计算服务（如 Serverless）或来自云厂商内部的集群分析（如 Google、Alibaba 的集群 trace），而从用户/开发者视角出发的、覆盖大量真实部署架构的研究几乎为空白。

---

## 二、要解决的问题

1. **缺乏真实云架构的大规模数据集**：现有工作要么聚焦特定公司内部系统（如 Google 的 GFS、Facebook 的 Haystack），要么关注单一服务类型（如 Serverless），没有一个涵盖数百个真实部署的全面数据集来揭示存储服务的使用模式。
2. **存储服务的选择缺乏实证指导**：从业者在设计云架构时，面对 S3、DynamoDB、RDS、EFS 等大量存储选项，缺乏来自社区集体经验的统一参考。
3. **研究方向与实际部署脱节**：存储系统研究者不清楚哪些服务、哪些使用模式在实际中最常见，导致研究资源分配可能不够合理（例如在分布式文件系统上投入过多，而对 object store 研究不足）。

---

## 三、洞察与设计

**关键洞察**：AWS 发布的 "This Is My Architecture" 系列 YouTube 视频（396 个）虽然是原始的非结构化视频内容，但每个视频都由开发者详细描述一个真实部署架构的服务组成和交互方式，构成了一个未被利用的、规模空前的云架构数据源。通过严谨的结构化标注方法，可以将这些视频转化为可查询的量化数据集。

基于此洞察，作者构建了 **Cloudscape** 数据集：

- **数据表示**：每个架构编码为有向图，节点为 AWS 服务，边分为 data edge（数据流动）和 meta edge（触发/确认）。边被组织为 workflow（同步的调用序列）。
- **服务分类**：将 134 个 AWS 服务分为 Compute、Storage、Network、Integration、Control Plane、Others 六大类。存储服务进一步细分为 File、SQL、NoSQL、Specialized、Object 五类。
- **标注流程**：三名团队成员先对 50 个架构进行迭代标注以确定编码规范，再训练另外三人完成剩余数据。最终 340 个架构（85.9%）可用于定量分析，176 个包含定性数据标注。
- **分析维度**：围绕三个核心问题展开——(a) 存储服务如何被选择和组合？(b) 存储服务与哪些服务交互、存储什么数据？(c) 专门化 ML/Analytics 服务如何使用存储层？

---

## 四、实现细节

Cloudscape 并非传统意义上的系统实现，而是一个数据集+分析工具。关键实现要素包括：

1. **数据采集与标注**：
   - 来源：AWS "This Is My Architecture" YouTube playlist，396 个视频，时间跨度 2019-2023，涉及 378 家企业，11 种语言。
   - 排除不描述架构的视频后，保留 340 个用于定量分析。
   - 总耗时超过 40 小时视频素材，18 个人月的标注工作量。

2. **图编码规则**：
   - 视频中出现多次的服务保留为多个节点（忠实编码）。
   - 当口述与画面不一致时，以口述为准。
   - 异步工作流（如 SQS 消息出队）拆分为独立 workflow。
   - 边附带序号以保留交互顺序。

3. **定性标注**：对 176 个架构额外标注了存储服务中实际存储的数据类型（如 logs、images、ML models、metadata 等）。

4. **功能目标分类**：将架构分为 Data Ingestion（45%）、Interactive（35%）、Compute Intensive（15%）、Control Plane（14%）四类（可多标签）。

5. **数据集与分析脚本开源**：https://github.com/WiscADSL/Cloudscape

---

## 五、实验结果

本文为测量研究（measurement study），核心发现整理如下：

### 存储服务普及度

| 存储类型 | 代表服务 | 使用比例 |
|---------|---------|---------|
| Object Store | S3 | 68% |
| NoSQL | DynamoDB | 41% |
| SQL | RDS | 31% |
| Specialized | RedShift, Neptune | ~11% |
| File System | EFS, FSX | ~4% |

### 存储异构性

| 指标 | 数值 |
|------|------|
| 使用 ≥2 种存储服务的架构 | ~50% |
| 使用 ≥3 种存储服务的架构 | ~13% |
| 单一 workflow 涉及 ≥2 种存储的架构 | 35% |

### S3 的核心地位
- 68% 架构使用 S3，22% 架构将 S3 作为唯一存储服务。
- S3 平均连接的上下游服务数量多于其他任何存储服务。
- 70% 使用 S3 的架构对其既有上传又有下载操作（非单纯 dump）。
- S3 存储内容包括：logs（16 例）、images（16 例）、web 内容（11 例）、视频（11 例）、ML 模型/代码（9 例）、metadata（7 例）、数据归档（6 例）。

### 存储与计算的交互
- Lambda 是存储服务最频繁的交互方（读写频率约为第二名 EC2 的两倍）。
- ~60% 架构使用 Serverless 计算，~19% 仅依赖 Serverless。
- ML 服务几乎完全通过 S3 交换数据（输入输出均存于 S3）。
- Analytics 服务（42% 架构使用）以 S3 为主要数据源，常导致数据在 S3 与其他存储间重复。

### DynamoDB 的特殊用途
- 除通用数据存储外，DynamoDB 被广泛用于存储 metadata（16 例）和系统状态/编排信息（12 例），远超其他存储服务在此用途上的占比。

---

## 六、批判性分析

1. **数据集的代表性偏差被低估**：Cloudscape 的数据源是 AWS 邀请客户录制的展示视频，存在显著的选择偏差——这些是 AWS 希望展示的"成功案例"，可能系统性地偏向使用更多 AWS 服务的架构。论文承认了这一点但仍声称"broadly representative"，缺乏充分论证。

2. **仅覆盖 AWS 单一云厂商**：论文声称方法论可推广到其他云厂商，但 AWS 的服务生态（如 Lambda 与 S3 的深度集成）是高度特有的。在 GCP 或 Azure 上，Cloud Functions/Cloud Run 与 GCS/Blob Storage 的交互模式可能有显著差异。这一局限性使得部分结论（如"S3 是新的默认存储"）的普适性存疑。

3. **定量分析停留在计数层面**：大多数分析仅报告了"多少比例的架构使用了某服务"，未深入探讨因果关系。例如，S3 的高使用率可能部分因为 AWS 许多服务默认将数据写入 S3，而非开发者的主动选择。

4. **时间跨度问题**：数据覆盖 2019-2023，但云服务生态变化极快。2023 年后 GenAI 爆发带来的架构变化（如向量数据库、RAG pipeline）完全未被捕捉。论文未讨论数据时效性对结论的影响。

5. **缺乏工作负载信息**：Cloudscape 仅编码了服务间的拓扑关系，不包含流量大小、请求频率、延迟等性能指标。这使得许多"implications"（如建议优化 S3 吞吐/延迟）缺乏数据支撑。

6. **分布式文件系统使用率低的结论可能误导**：论文强调分布式文件系统仅在 4% 架构中使用，但 EBS 因"开发者很少显式提及"而被严重低估（间接使用率达 60%）。类似地，EFS 可能也存在低估，因为它常作为 EKS/ECS 的后端存储而不被单独提及。

---

## 七、AI Infra / MLSys 视角

1. **S3 作为 ML pipeline 的数据总线**：论文发现 ML 服务（SageMaker、Transcribe、Rekognition 等）几乎完全通过 S3 交换数据。这对 AI Infra 的启示是：优化 S3 的读写性能（特别是大文件顺序读和小文件批量读）对 ML workload 至关重要。S3 Express One Zone 等低延迟变体值得在 ML pipeline 中深入评估。

2. **训练数据格式与存储协同设计**：论文指出应研究 CSV、JSON、Parquet、TFRecord 等格式是否充分利用了 S3 的特性。这是一个值得跟进的方向——例如，针对 S3 的 Range Get API 设计列式存储格式，或在 object store 层面支持 predicate pushdown，减少训练时的数据传输量。

3. **Serverless + Storage 的交互优化**：Lambda 是存储服务最大的消费者，但与缓存服务的交互极少。对于 AI 推理场景（如 model serving on Lambda），设计与 Serverless 原生集成的缓存机制（如模型权重缓存、KV cache）是值得探索的方向。

4. **跨服务数据一致性**：35% 的架构有单一 workflow 涉及多种存储服务，这在 ML pipeline 中很常见（如模型版本存 S3、元数据存 DynamoDB、特征存 Redis）。跨服务一致性是 ML 系统可靠性的关键挑战。

5. **可操作的研究方向**：
   - 构建 S3 兼容 object store 上的 ML-aware 数据预取和缓存策略。
   - 设计面向 ML workload 的轻量级跨存储一致性协议。
   - 研究如何将 ML 推理的中间结果在 S3 和专用存储间高效流转，减少数据复制。

---

## 八、总结

Cloudscape 是首个大规模研究云架构中存储服务使用模式的工作，通过对 396 个 AWS 真实部署架构的系统化标注和分析，揭示了 S3 的主导地位（68%）、存储异构性的普遍性（约半数架构使用 ≥2 种存储服务）、分布式文件系统的边缘化、以及 Lambda 与存储的密切交互。其主要价值在于为存储系统研究提供了实证数据支撑，帮助社区聚焦更具影响力的研究方向（如 object store 工作负载表征、跨服务一致性、ML-存储协同设计）。局限在于仅覆盖 AWS 单一云厂商、数据来源存在选择偏差、且缺乏工作负载级别的性能数据。
