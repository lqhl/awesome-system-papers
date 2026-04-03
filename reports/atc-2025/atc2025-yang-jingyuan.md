# ShieldReduce: Fine-Grained Shielded Data Reduction

**作者**：Jingyuan Yang, Jun Wu, Ruilin Wu, Jingwei Li (University of Electronic Science and Technology of China); Patrick P. C. Lee (The Chinese University of Hong Kong); Xiong Li, Xiaosong Zhang (University of Electronic Science and Technology of China)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/yang-jingyuan
**源文件**：[[atc2025-yang-jingyuan.pdf]]

---

## 一、背景

外包存储（outsourced storage）是组织管理多客户端备份的经济高效方案。实际的外包存储系统需要同时实现两个目标：（1）存储节省——通过数据缩减降低存储开销；（2）数据机密性——防止未授权访问（包括云运营商）。然而这两个目标天然冲突：传统对称密钥加密使用用户特定密钥，导致不同客户端的重复数据加密后无法压缩。

现有的加密去重方案（如 convergent encryption、message-locked encryption）通过确定性加密让重复数据块映射为相同密文，从而支持跨客户端去重。但这类方案存在两大局限：（1）泄露数据块频率信息，无法达到传统对称加密的安全性；（2）加密后数据高熵，无法进一步通过 delta compression 和 local compression 节省存储。

---

## 二、要解决的问题

1. **加密去重与细粒度压缩不兼容**：现有加密去重方案只能做去重，无法在加密数据上执行 delta compression 和 local compression，损失了约 2× 的额外存储节省空间。

2. **SGX enclave 中管理 base chunk 的 I/O 开销大**：Delta compression 需要加载历史 base chunk 进行差异编码。在 SGX enclave 中，base chunk 存储在持久化存储上，按需加载会带来大量磁盘 I/O 和高昂的 context switch 开销（每次 ECall/OCall 约 8,000 CPU cycles，远高于普通系统调用的 150 cycles）。

3. **物理局部性随备份版本增加而退化**：随着备份版本增多，base chunk 分散在不同版本的容器中，导致 delta compression 需要从越来越多的容器中读取 base chunk，I/O 开销显著增加。

---

## 三、洞察与设计

**关键洞察**：Chunk 相似性是对称的——如果新数据块 M' 与旧 base chunk M 相似，那么 M 也与 M' 相似。这意味着 delta compression 可以双向执行：不仅可以用旧 base chunk 压缩新数据块（forward），也可以用新数据块作为新的 base chunk 来压缩旧的 base chunk（backward）。由于新数据块在逻辑上通常是相邻的，让它们成为 base chunk 可以重建物理局部性，降低后续备份的 I/O 开销。

基于此洞察，ShieldReduce 设计了以下核心机制：

**Bi-directional Delta Compression**：根据 base chunk 的物理分布自适应选择压缩方向。当 base chunk 集中在少数容器中（物理局部性强）时，执行 forward delta compression；当 base chunk 分散（局部性弱）时，执行 backward delta compression，用新数据块替代旧 base chunk，重建局部性。

**Hybrid Inline/Offline Compression**：
- **Locality-based Inline Compression**：在写路径上，对物理局部性好的批次执行 forward delta compression + local compression，保证高吞吐。
- **Tunable Offline Compression**：对局部性差的批次，在写路径外执行 backward delta compression。引入可配置参数 α（offline reduction target，0 ≤ α ≤ 1）来平衡存储节省与性能开销。

**Locality Detection**：对每批 n 个数据块，计算 q/n（q 为包含 base chunk 的容器数），当 q/n ≤ t（locality threshold）时判定物理局部性存在。

---

## 四、实现细节

- 基于 Intel SGX SDK Linux 2.15 实现，代码量约 10.5K 行 C++。
- **Chunking**：使用 FastCDC 做 content-defined chunking，chunk 大小 4KiB/8KiB/16KiB（min/avg/max）。
- **去重**：复用 DEBE 的 frequency-based deduplication，enclave 内维护 256K 高频指纹的小索引，enclave 外维护完整指纹索引。
- **特征提取**：使用 Finesse 从每个非重复 chunk 提取 3 个特征（各 32 bytes）用于相似性匹配。
- **Delta compression**：使用 Edelta 算法；**Local compression**：使用 LZ4。
- **加密**：AES-256-GCM + 随机 16 字节 IV 加密压缩后的 chunk。
- **容器管理**：4 MiB 固定大小容器，按语义分为 base chunk container 和 delta chunk container，提升 I/O 效率。
- **索引结构**：fingerprint index、feature index 存放在 enclave 外的非可信内存中，指纹通过 AES-256-CBC 加密保护；delta index 追踪 delta 关系；backward index 追踪待离线压缩的 chunk 映射（最大 256 MiB，可覆盖约 32 GiB 数据）。
- **Chunk Replacement**：离线压缩后通过 mark-and-sweep 方式回收旧物理副本的存储空间。

---

## 五、实验结果

**平台**：阿里云 ecs.r7t.xlarge（4 核 2.7GHz Intel Xeon，32GiB RAM，SGXv2），Ubuntu 20.04，3GbE 网络，1TiB Aliyun SSD。

**数据集**：

| 数据集 | 描述 | 版本数 | 总逻辑数据 |
|--------|------|--------|------------|
| Linux | Linux 源代码 v2.6.11–v6.4-rc7 | 209 | 185.7 GiB |
| Web | sina.com.cn 新闻网站备份 | 78 | 210.8 GiB |
| Docker | Cassandra Docker 镜像快照 | 95 | 32.2 GiB |
| SimOS | 合成 CentOS 7 操作系统快照 | 30 | 240 GiB |

**存储效率（Data Reduction Ratio）**：

| 数据集 | DEBE | ShieldReduce (α=0) | ShieldReduce (α=0.5) | SecureMeGA | ForwardDelta |
|--------|------|---------------------|----------------------|------------|--------------|
| Linux | 5.8× | 25.8× | 12.2× | 12.1× | 25.1× |
| Web | 13.1× | 58.6× | 27.9× | 16.1× | 60.6× |
| Docker | 8.6× | 14.9× | 14.4× | 14.0× | 15.0× |
| SimOS | 59.3× | 63.6× | 63.6× | 60.2× | 63.3× |

**上传性能**：
- 相比 ForwardDelta，ShieldReduce 上传吞吐提升 1.1–3.5×（通过保持物理局部性减少 I/O）。
- 相比 SecureMeGA，ShieldReduce inline 上传速度相当，但通过 offline compression 额外获得最高 3.6× 的存储节省。
- DEBE 因不做 delta compression，上传速度比 ShieldReduce 快 1.5–2.2×。

**多客户端性能**：
- 10 客户端并发上传时，Redundant 场景聚合上传 578.1 MiB/s，Unique 场景 211.2 MiB/s。
- 下载端 Redundant 聚合速度最高 1024.6 MiB/s。

**Enclave 开销**：ShieldReduce 相比 DEBE 增加最多 2.4× OCalls，但通过保持物理局部性，比 ForwardDelta 减少最多 83.3% 的 OCalls。索引开销占逻辑数据的 0.14%–0.39%。

---

## 六、批判性分析

1. **安全模型存在已承认但被轻描淡写的信息泄露**：论文承认 delta index 和 backward index 会泄露哪些 chunk 相似，以及 collusion 攻击可利用数据缩减量推断其他客户端的数据。论文仅提出"可以使用 selective deduplication 和 padding"作为防御，但未实现也未评估这些防御措施的存储开销和性能影响。这意味着 ShieldReduce 的安全优势相对于加密去重方案可能没有论文声称的那么大。

2. **Web 数据集不公开，可复现性受限**：四个数据集中 Web 是存储节省最显著的（58.6× vs 其他数据集的 14.9–63.6×），也是 ShieldReduce 对比 SecureMeGA 优势最大的场景（3.6×），但该数据集是私有的，其他研究者无法复现这一关键结果。

3. **局部性阈值 t 和离线目标 α 需要手动配置**：论文固定 t=0.03, α=0，但不同工作负载的最优参数不同。论文也承认"自适应配置 t 是未来工作"，但这在实际部署中是一个关键问题，手动调参会增加运维负担。

4. **SGX 的长期可用性存疑**：论文选择 SGX 是因为"长期支持 Xeon 平台"，但 Intel 已在消费级 CPU 上弃用 SGX（从第 11 代 Core 开始）。虽然服务器端 SGXv2 仍在支持，但 Intel TDX 正在成为主流替代方案。论文用一句话否定了 TDX（"more coarse-grained, relies on a sizable trusted computing base"），但没有深入讨论如何将设计迁移到 TDX 或 AMD SEV-SNP 等替代 TEE 上。

5. **离线压缩的延迟影响未充分讨论**：当物理局部性差时，数据先以 local compression 方式存储，等离线压缩完成后才获得 delta compression 的存储节省。在 Web 数据集上离线压缩耗时可达数百秒。这段时间内的存储开销（即 α_current > α 时的过渡状态）未被量化分析。

---

## 七、总结

ShieldReduce 通过在 Intel SGX enclave 中执行完整的数据缩减流程（去重 + delta compression + local compression），实现了加密前数据缩减，既保持了传统对称加密的安全性，又获得了接近明文数据缩减的存储节省。其核心创新是 bi-directional delta compression，通过自适应选择 forward/backward 压缩方向来维持物理局部性、降低 I/O 开销。该方案适用于多客户端外包备份场景，在 Linux 源代码、网站备份、Docker 镜像和 OS 快照等工作负载上表现良好。主要局限在于依赖 Intel SGX 平台、配置参数需手动调优、以及离线压缩引入的延迟。
