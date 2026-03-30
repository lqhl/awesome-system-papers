# Compass: Encrypted Semantic Search with High Accuracy

## 论文基本信息

- **标题**: Compass: Encrypted Semantic Search with High Accuracy
- **作者**: Jinhao Zhu (UC Berkeley), Liana Patel (Stanford), Matei Zaharia, Raluca Ada Popa (UC Berkeley)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/zhu-jinhao

## 研究背景与动机

端到端加密正在成为用户数据系统的标准配置（WhatsApp、iCloud、Telegram、Signal 等）。在加密数据上搜索是一个活跃了数十年的研究问题，现有方案面临两个根本挑战：

1. **安全性弱**：许多方案泄漏了搜索访问模式（search access patterns），容易受到访问模式攻击（access pattern leakage attacks）
2. **精度低**：大多数方案仅实现词汇搜索（lexical search），远不如现代语义搜索（semantic search）的精度

```
关键词搜索结果："Social Security Number Randomization. On June 25, 2011..."
（被"social security numbers"这个高频词带偏）

语义搜索结果："Social Security number is the number..."
（正确理解查询意图是"社会保障号的含义"）
```

现有方案的困境：
- **TEE 方案**：受侧信道攻击威胁（MemJam、CacheZoom 等可完全绕过远程认证）
- **两服务器方案**：假设服务器间不串通，但实际部署困难
- **FHE/同态方案**：计算量巨大，无法实用
- **HE-Cluster**：精度低（TripClick 数据集上低于 TF-IDF）

## 要解决的核心问题

如何在**不依赖可信硬件**、**不泄漏访问模式**、**不对服务器做信任假设**的前提下，实现与明文语义搜索**同等精度**的加密数据搜索？

## 主要贡献

1. **HNSW 图遍历的 ORAM 友好改造**：通过三种技术使图搜索在加密环境下高效
2. **Directional Neighbor Filtering**：利用量化的方向提示仅访问最相关的邻居，大幅降低带宽（节省约一半邻居传输）
3. **Speculative Neighbor Prefetch**：预测性预取可能访问的节点，减少网络往返次数
4. **Graph-Traversal Tailored ORAM**：白盒改造 Ring ORAM，整合图遍历的访问模式，进一步降低延迟
5. **在 4 个数据集上达到 SOTA 精度**：匹配明文 HNSW 的精度，比 HE-Cluster 快多个数量级

## 研究方法与设计

### 系统架构

```
Client ──→ ORAM Controller ──→ Encrypted HNSW Index
                                              ↓
                                          ORAM Tree
                                        (Ring ORAM)
```

Client 端运行 HNSW 搜索算法，与服务器交互获取加密数据。

### 问题分析：HNSW + ORAM 的效率瓶颈

HNSW 图搜索是贪婪多跳过程，在明文环境下每跳仅需本地内存访问。但在加密环境下：

1. **每次节点访问 = 一次 ORAM 请求**（网络往返）
2. HNSW 每层搜索需评估数百个候选节点
3. 每节点含数百个邻居

→ 朴素方案：ef × M 次 ORAM 访问，数千次网络往返

### 技术一：Directional Neighbor Filtering

**核心思想**：每步仅获取"方向上相近"的邻居，而非所有邻居。

具体实现：
- 预计算所有节点的 **Quantized Hints**（使用 Product Quantization，压缩到约 128 维）
- 客户端存储所有量化提示（内存开销极小，如 LAION 仅 5.5 MB）
- 在图遍历的每步，客户端先用量化提示筛选出 top-efn 个"方向最接近"的邻居
- 仅从 ORAM 获取这 efn 个邻居的完整数据，而非全部 M 个

### 技术二：Speculative Neighbor Prefetch

**核心思想**：在等待当前 ORAM 响应时，预测性获取候选节点。

- 客户端维护一个 speculating set（大小 efspec × efn）
- 当前批次 ORAM 请求完成后立即启动下一批（隐藏网络延迟）
- 利用 HNSW 的候选列表排序信息预测

### 技术三：Graph-Traversal Tailored ORAM

**核心洞察**：图搜索有独特的访问模式——多跳贪婪搜索。

白盒改造 Ring ORAM：
1. **Multi-hop Lazy Eviction**：将 ORAM eviction 延迟到查询结束后统一处理，减少在线开销
2. **Stash Sorting**：按路径 ID 排序 stash，降低 stash 查找复杂度
3. **Tree-top Caching**：缓存 ORAM 树顶部层级，减少高频访问路径的长度
4. **Batching**：将多个邻居的 ORAM 访问批量化，减少总往返次数

### 安全性证明

论文给出了形式化安全性证明：
- 基于碰撞-resistant 哈希函数和 IND-CCA2 安全加密
- 使用 Merkle 树保护完整性
- Ring ORAM 的访问模式安全性继承

### 与恶意服务器的对抗

服务器可能：篡改密文、重排 bucket、执行 replay 攻击。Compass 通过：
- Merkle 树完整性验证
- Ring ORAM 的路径随机化
- 定期 checkpoint 和 recovery 协议

## 关键实现细节

- 约 **5,000 行 C++ 代码**
- 使用 Faiss 库构建 HNSW 图
- OpenSSL EVP（AES-256-CBC 加密，SHA-256 哈希）
- 客户端缓存上层 HNSW 图（减少服务器往返）

## 实验结果与分析

### 搜索精度 vs 延迟

在所有 4 个数据集上，Compass 匹配明文 HNSW 精度（MRR@10 ≥ 0.9 的设置）。

### 延迟对比

| 数据集 | 网络 | 用户感知延迟 | 全延迟 |
|--------|------|------------|--------|
| LAION | 快 | 0.7s | 13.5s |
| SIFT1M | 快 | 1.1s | 12.2s |
| TripClick | 慢 | 6.0s | 929s |
| MS MARCO | 慢 | 8.9s | 2263s |

### 与基线对比（TripClick 数据集）

- **Compass**：精度 0.92，用户感知延迟 6s
- **Inv-ORAM**：精度 ~0.75（截断列表越小精度越低），延迟更低但精度不达标
- **HE-Cluster**：精度显著低于 TF-IDF（在 TripClick 上），延迟极高

### 带宽消耗

用户感知通信量（不含 eviction）：LAION 0.57 MB，MS MARCO 8.9 MB，均在可接受范围。

## 潜在问题与局限性

1. **扩展性问题**：客户端内存随数据集线性增长。论文坦承对于 Web 规模搜索（0.5 GB 客户端内存）不适用——这是个人搜索场景的系统，不是通用搜索
2. **恶意服务器下的全延迟高**：Eviction 阶段延迟极高（如 MS MARCO 全延迟 2263s），虽然可以后台执行，但完整查询仍需等待
3. **单轮加密方案的精度劣势未解决**：HE-Cluster 在 LAION 上达到与 Compass 相近的精度，但在 TripClick 上显著低于 TF-IDF，说明在某些数据集上语义搜索本身不如词汇搜索
4. **模型依赖**：语义搜索质量依赖 embedding 模型，模型更新需要重建索引
5. **Fault Tolerance 的复杂性**：Client 磁盘失效时依赖服务器提供状态，若服务器恶意则无法检测不一致
6. **操作类型泄漏**：论文坦承 Compass 不保护"操作类型"（查询 vs 插入 vs 删除）的泄漏，在某些场景下这可能是有价值的信息

## 未来工作方向

- 支持更多 embedding 模型和距离度量
- 优化 eviction 延迟
- 跨用户数据共享的加密搜索
- 扩展到更大规模数据集

## 个人评注

1. **三技术组合精巧**：Directional Neighbor Filtering（带宽优化）、Speculative Prefetch（延迟隐藏）、Tailored ORAM（系统协同设计）是层层递进的优化，缺一不可。单独任何一项都不能解决问题。

2. **安全性定义的完整性**：论文明确定义了威胁模型（恶意服务器）和安全游戏，给出了形式化证明，这是密码学系统论文的黄金标准。

3. **潜在夸大**：摘要称"orders of magnitude faster than baselines"，这在特定场景下（如 MS MARCO vs HE-Cluster）是成立的，但与 Inv-ORAM 的对比在低精度设置下并不明显。需要注意这取决于具体的比较对象。

4. **与 TEE 方法的对比缺失**：论文讨论了 TEE 的侧信道脆弱性，但未直接与 TEE 方法在精度和性能上对比。若 TEE 方案能提供足够安全性，其效率可能更优。

5. **Fault Tolerance 的诚实讨论**：论文主动讨论了 client 磁盘失效和恶意服务器场景，说明了系统的局限性，这是加分项。

6. **数据集选择有意义**：选择 LAION、SIFT1M（图像）、MS MARCO（网页）、TripClick（医疗）是广泛认可的 ANN 基准，具有说服力。

7. **量化提示的隐私性**：客户端存储所有量化提示，这是略低于 embedding 精度但远高于关键词的信息泄漏。若攻击者获取了量化提示，隐私是否真正保护？论文未深入讨论。
