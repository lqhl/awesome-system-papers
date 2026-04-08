# CoFS: A Filesystem for Fast Container Startup

**作者**：Li Wang, Jinxu Du, Yang Yang, Qingbo Wu, Tao Liu, Haoze Wu（KylinSoft）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/wang-li
**源文件**：[[fast2026-wang-li.pdf]]

---

## 一、背景

容器技术已成为云原生应用部署的主流方式，Kubernetes 等编排工具广泛使用。容器冷启动涉及镜像下载、解压、配置、启动等多个串行步骤，其中镜像拉取占容器启动时间的 76%，但实际只有 6.4% 的数据会被读取。高冷启动延迟严重影响 serverless 场景的响应性 SLA 和突发请求下的自动扩缩容。

为降低启动延迟，业界提出了 on-demand pulling（按需拉取）方案：容器无需等待完整镜像下载即可运行，所需数据按需获取。Overlaybd、Nydus-fuse、Nydus-erofs、eStargz 等系统实现了这一思路，但各有不足：

- **Nydus-fuse / eStargz**：基于 FUSE，用户态文件系统带来频繁上下文切换和数据拷贝开销
- **Nydus-erofs**：基于内核 erofs + fscache，首次访问数据链路过长（erofs → fscache → 用户态 daemon），同步 I/O 性能甚至低于 Nydus-fuse，且 fscache 缓存驱逐不可控导致性能波动

---

## 二、要解决的问题

基于 FUSE 实现 on-demand image pulling 面临两个核心挑战：

1. **元数据查找开销大**：Linux 内核对文件访问前需进行迭代路径遍历（path traversal），每个路径分量都会触发一次 LOOKUP 请求转发到用户态 FUSE daemon，产生多次上下文切换和请求拷贝
2. **已缓存数据访问仍需经过用户态**：即使数据已下载到本地，FUSE 仍需将 read 请求转发到用户态处理，产生不必要的上下文切换和数据拷贝开销

---

## 三、洞察与设计

**关键洞察**：容器镜像从容器视角来看是一次构建、只读固定的文件系统树。文件集合在镜像构建时已完全确定，不会再变化。

基于这一观察，CoFS 的核心设计思路是：既然文件集合是固定的，就可以在镜像构建时预先构造 Minimal Perfect Hash Function（MPHF），将文件元数据组织为以 hash 值索引的密集数组，从而在内核空间完成 O(1) 的元数据查找，彻底避免 FUSE 用户态 lookup 过程。

**MPHF 元数据查找**：以（父 inode 号 + 文件名）为 key 构造 MPHF，每次 lookup 只需计算 hash 值后直接索引到元数据数组的对应位置，大多数情况下仅需不到一次 I/O 操作（若磁盘块已在 page cache 中则零 I/O）。

**全路径并行查找**：构造第二个 MPHF，以文件全路径为 key，映射到相同 hash 值。通过 kprobe 拦截 `do_filp_open`，在工作队列中以自底向上的方式并行构造 inode，与 VFS 自顶向下的路径遍历并发执行，加速深路径的解析。

**内核态数据快速路径**：利用宿主文件系统的 sparse file 作为本地缓存的镜像文件，已下载数据直接在内核空间通过 `vfs_read` 访问，绕过 FUSE 的用户态往返。通过 `vfs_lseek(SEEK_HOLE)` 判断数据是否已缓存。

---

## 四、实现细节

CoFS 由两个组件构成：

**cofs-snapshotter**（用户态）：基于 eStargz snapshotter 实现的 containerd snapshotter 插件。
- 容器创建前：异步拉取元数据文件 `cofs.inode.array`，通过 ioctl 通知内核驱动；为每层镜像创建 mirror 目录和 FUSE 挂载点
- 容器运行时：作为 FUSE daemon 处理未缓存数据的下载请求，下载后异步写入对应 mirror 文件

**cofs-driver**（内核态）：基于 FUSE driver 扩展实现。
- **元数据文件格式**：12 字节 header（magic + m + n + length），后接 T₁、T₂、g 三个数组和元数据数组（每条 120 字节），以及存储长文件名和扩展属性的 extra metadata 区域
- **Lookup 流程**：计算 MPHF 值 → 索引元数据数组 → 比较父 inode 号和文件名 → 构造 in-memory inode。文件名 ≤16 字节直接存储在元数据条目中，>16 字节存储偏移量指向 extra metadata 区
- **Read 流程**（Algorithm 1）：检查 mirror 文件是否存在 → 若存在且数据已缓存（通过 `vfs_lseek(SEEK_HOLE)` 判断），直接内核态读取；否则转发到用户态 cofs-snapshotter

**MPHF 构造**：基于 Czech 等人的线性时间算法，构造随机图检测无环性，通过 DFS 赋值。n > 2m 时快速收敛（n = 3m 时期望迭代约 √3 次）。100 万节点的构造时间约 34 秒，相对镜像构建时间可忽略。空间开销约 9.5 MB/百万文件。

实现基于 Linux kernel 6.9.1，cofs-snapshotter 基于 stargz-snapshotter 0.15.1。

---

## 五、实验结果

**实验环境**：双路 Xeon E5-2640 V4（10 核 2.40GHz），128GB RAM，1Gb 网卡，4TB HDD。镜像仓库部署在另一台机器，千兆网络连接。

**对比系统**：CoFS（lz4 压缩）、CoFS-gzip、traditional（完整拉取）、Nydus-fuse 2.2.5、Nydus-erofs 2.2.5、eStargz 0.15.1。

**镜像构建开销**：

| 镜像 | eStargz 大小 | CoFS 大小 | eStargz 构建时间 | CoFS 构建时间 |
|------|-------------|----------|----------------|--------------|
| mariadb-10.7.3 | 126.2MB | 128.4MB | 23s | 25.36s |
| redis-6.2.6 | 41.5MB | 41.6MB | 6.75s | 7.64s |
| tomcat-10.1.0 | 330.6MB | 330.9MB | 22.92s | 26.14s |
| elasticsearch-8.1.1 | 535.4MB | 535.5MB | 51.34s | 54.47s |

镜像大小增加 < 0.2%，构建时间增加约 10–13%。

**冷启动时间**：CoFS 在所有容器上均优于其他 on-demand pulling 系统。后台预下载在大多数情况下反而降低性能（因完整镜像远大于启动所需数据，预下载争抢带宽和 I/O 资源）。

**Lookup 性能**：相比 fuse-loopback，CoFS 平均 lookup 时间提升 73%–86%。并行 lookup 在 elasticsearch 容器上带来额外 28% 的提升。

**缓存数据读取性能**：CoFS、traditional 和 Nydus-erofs 性能几乎一致（均在内核空间访问），而 Nydus-fuse 和 eStargz 因 FUSE 用户态开销明显较低。

---

## 六、批判性分析

**实验硬件过于陈旧**：使用 2016 年的 Xeon E5-2640 V4 和 1Gb 网卡 + HDD 配置，与现代容器部署环境（NVMe SSD、10/25Gb 网络）差距巨大。在高速网络和 SSD 环境下，下载和 I/O 延迟大幅降低，FUSE 用户态开销的相对占比可能显著变化，CoFS 的优势幅度是否维持存疑。

**只测试了 4 个容器镜像**：mariadb、redis、tomcat、elasticsearch 都是传统服务型容器。缺乏对 AI/ML 工作负载（大量 Python 包、大模型文件）、微服务（小镜像但高频启动）、多层深度嵌套镜像等场景的评估。

**冷启动时间的绝对值缺失**：论文只展示了图表（Figure 3），没有在正文中给出具体数值和百分比改进，读者难以量化实际收益。

**kprobe 路径加速的侵入性未充分讨论**：使用 kprobe 拦截 `do_filp_open` 属于动态内核插桩，在生产环境中可能带来稳定性风险和安全隐患。论文未讨论 kprobe overhead、与安全模块（SELinux/AppArmor）的兼容性、以及内核版本升级时 `do_filp_open` 接口变化的维护成本。

**并行 lookup 的收益有限且场景受限**：只有 elasticsearch 展示了 28% 的改进，其他容器改进不明显。论文承认只对路径深度超过三层才触发并行 lookup，但未分析实际容器镜像中深路径文件的比例和访问模式。

**缺乏与 Overlaybd 的对比**：Overlaybd 是阿里巴巴广泛使用的生产系统，工作在块设备层面。论文虽在 related work 中提及但未纳入实验对比。

**MPHF 对无效 key 的处理存在隐患**：论文提到对无效 key 仍会计算出 hash 值，通过比较存储的 key 来验证。但如果出现 hash 碰巧命中一个合法条目且文件名长度恰好匹配但内容不同（概率虽低但非零），论文未讨论这种极端情况下的正确性保障。

---

## 七、AI Infra / MLSys 视角

**容器冷启动对 AI 推理服务的影响**：在 serverless AI 推理场景（如 GPU 实例按需启动），容器冷启动延迟是影响首次推理响应时间的关键因素。CoFS 的 on-demand pulling 优化思路可直接应用于加速 AI 推理容器的启动。

**对大模型镜像的启示**：AI 容器镜像通常包含大量 Python 依赖和模型权重文件，镜像体积可达数十 GB。CoFS 的 MPHF 索引方案在文件数量极大时空间效率高（百万文件仅 ~10MB），但论文未验证对超大文件（模型权重通常为单个大文件）的 on-demand pulling 性能。

**可能的延伸方向**：
- 将 MPHF 加速 lookup 的思路应用到模型 checkpoint 加载场景——大规模分布式训练中，数千个 worker 同时从共享存储加载 checkpoint 时的元数据查找是瓶颈之一
- 结合模型推理的 access pattern 预测（哪些层的权重会被先加载），实现更智能的 prefetch 策略，替代论文中批评的简单后台全量下载

---

## 八、总结

CoFS 提出了一种基于扩展 FUSE 的容器文件系统，核心贡献是利用容器镜像只读固定的特性，在镜像构建时构造 MPHF 索引，使内核空间能以 O(1) 复杂度完成文件元数据查找，并通过 sparse file 实现已缓存数据的内核态直接访问。方案在不修改镜像格式兼容性的前提下（基于 eStargz 扩展），以极小的镜像体积和构建时间开销换取了显著的 lookup 性能提升（73%–86%）。主要局限在于实验环境过于陈旧、测试场景有限，且 kprobe 并行 lookup 机制的生产可行性有待验证。
