# FlacIO: Flat and Collective I/O for Container Image Service

**作者**：Yubo Liu, Hongbo Li, Mingrui Liu, Rui Jing, Jian Guo, Bo Zhang, Hanjun Guo, Yuxin Ren, Ning Jia（Huawei Technologies Co., Ltd.）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/liu-yubo
**源文件**：[fast2025-liu-yubo.pdf](../../papers/fast-2025/fast2025-liu-yubo.pdf)

---

## 一、背景

容器技术已广泛部署在云场景中（弹性计算、动态服务扩缩容、灾难恢复等）。容器冷启动——从镜像仓库加载镜像到宿主机并启动服务——是影响云产品质量的关键指标。原生全量镜像加载会造成不可接受的延迟，I/O 放大可达数十倍。

当前主流优化分两条路线：**加速路线**（lazy loading，按需加载数据，已被各大云厂商生产部署，代表系统有 CRFS、Nydus、DADI）和**缓解路线**（caching/sharing、fork、P2P loading，减少冷启动频率）。然而两条路线都未能彻底解决冷启动瓶颈：缓解路线占用宿主机资源、多租户安全性差；加速路线虽然减少了数据加载量，但在 Ready 阶段仍存在严重的网络开销。

---

## 二、要解决的问题

现有 lazy loading 方案存在两个核心瓶颈：

1. **高 I/O 放大**（1.6×–3.1×）：访问粒度与按需加载粒度不匹配（文件级/chunk 级加载 vs. 页级访问），导致大量无用数据被传输。
2. **大量随机网络 I/O**：容器启动时对镜像数据的随机访问产生数十万个网络包，网络资源利用率极低。

这两个问题构成一个困境：更细的加载粒度可减少 I/O 放大，但会增加网络负载，反之亦然。现有的 prefetching 优化（expanded prefetch、file prioritization、trace replay）只是改变 I/O 优先级或盲目重放，无法高效聚合 I/O，也无法精确追踪。

论文进一步指出，**根因在于传统镜像抽象**：
- **Storage-Oriented**（记录磁盘状态）：数据压缩存储、难以页级索引、I/O 放大难以消除
- **Global-Oriented**（一个镜像服务多种服务）：所需数据离散分布在不同文件中、I/O 难以聚合、不同服务间局部性差异大

---

## 三、洞察与设计

**关键洞察**：同一容器服务每次冷启动所需的 root filesystem 内存状态是确定性的，只占全量镜像的很小比例（不超过 18%）。如果将镜像抽象从「记录磁盘状态、一个镜像服务所有场景」转变为「记录内存状态、一个镜像对应一个服务」，就可以将冷启动所需数据预先紧凑组织为连续存储，从根本上消除 I/O 放大和随机网络访问。

基于此洞察，FlacIO 提出 **Runtime Image** 抽象——记录容器服务启动时 root filesystem 的内存状态，包含启动所需的最小数据集和索引。系统包含两大核心设计：

### Runtime Image（镜像侧）

- **Probe-based I/O Tracing**：通过 eBPF 在 VFS 层追踪容器启动过程中的文件 read 和 mmap I/O，由用户定义的 probe（外部 HTTP 状态探测或内部 entrypoint 探测）精确控制追踪窗口，收集启动所需的最小 I/O 集合。
- **Runtime Image 组织**：基于同一 base image 的多个服务组成一个 group，共享 Group Data Zone（连续存储空间），组内数据通过 SHA256 去重。每个服务有独立的 Service Metadata（file index + page table + bitmap），支持增量加载。
- 冷启动时只需少量小 I/O 获取元数据 + 一个大 I/O 获取连续数据，网络效率极高。

### Runtime Page Cache（RTPC，宿主机侧）

- 在 OverlayFS 中实现的专用内核页缓存，叠加在传统 VFS page cache 之上。
- 提供两个新 OS 原语：`rt_diff`（比较 bitmap 找出未加载的页）和 `rt_inject`（将 runtime image 数据注入 RTPC）。
- Hook OverlayFS 的 open/read/mmap/page fault 操作：命中 RTPC 则直接返回，未命中则回退到传统 VFS 路径。
- 支持增量加载：同一 group 内已加载的数据不会重复拉取。

---

## 四、实现细节

FlacIO 原型实现基于以下组件：

| 组件 | 位置 | 功能 |
|------|------|------|
| I/O Tracker | 内核 eBPF | 在 read/mmap/page fault 入口添加 eBPF probe，收集 I/O trace（文件路径、offset、size） |
| RTPC | OverlayFS 内核模块 | 实现 `rt_diff` 和 `rt_inject` 原语，通过 sysfs 暴露给用户态；hook 文件操作进行 RTPC 查找 |
| FlacIO Driver | Containerd snapshotter 插件 | 控制面，桥接 runtime image service、I/O tracker 和 RTPC；封装 `rt_create`/`rt_delete` API |
| Runtime Image Service | Registry 节点独立 daemon | 管理 runtime image 的离线生成、加载、删除；通过 RESTful 与 FlacIO driver 交互 |

- 适配 CRFS 和 Nydus 分别只需 188 和 182 行代码
- Service ID = hash(base image name + entrypoint)
- 去重基于 SHA256 fingerprint，组内去重（跨 base image 重复率 <1%）
- 缓存淘汰采用 FIFO 策略，超过阈值时回退到 lazy loading

---

## 五、实验结果

**实验环境**：24 核 x86 CPU @2.30GHz，256GB DRAM，10Gbps 网络，openEuler 22.03 LTS + Linux 6.5，Containerd v1.7.1。

### 冷启动延迟

| 容器 | Full Image | CRFS | Nydus | DADI | DADI+Trace | CRFS+FlacIO | 加速比 |
|------|-----------|------|-------|------|------------|-------------|--------|
| Pytorch | 127.9s | 27.1s | 25.1s | 20.2s | 20.0s | ~5.6s | 最高 23× vs Full，4.5× vs lazy loading |
| Tensorflow | - | - | - | - | - | - | 3.7–3.9× vs CRFS/Nydus |
| Postgres | - | ~6s | ~6s | ~5s | ~5s | ~3.5s | 最高 27% vs DADI+Trace |

### 网络开销（Pytorch）

| 指标 | Full Image | Lazy Loading 最优 | FlacIO |
|------|-----------|------------------|--------|
| 数据量 | ~6.9GB | ~240MB | ~150MB |
| 网络包数 | ~570K | ~90K | ~22K |
| I/O 放大 | 47.5× | 1.6× | 1.1× |

### 存储空间开销

Runtime image 平均只占 base image 的 4.7%–6%（如 Pytorch 仅 146.5MB vs 3.3–4.2GB 原始镜像）。

### RTPC 性能影响

文件访问开销极小：RTPC miss 比无 RTPC 慢约 5%（random read），mmap 场景平均差异 1.7%–4.6%。

### 真实场景

| 场景 | 提升 |
|------|------|
| 对象存储（Memcached 冷启动后插入） | 吞吐量最高 2.25× |
| ML Training（Keras + MNIST on Tensorflow） | 训练时间快 1.7× |
| 集群自动扩缩容（8 节点各 8 个 Postgres） | 扩缩容速度快 55% |

### 内存占用

Nydus+FlacIO 的内存占用仅为其他系统的 1.1%–24%，得益于精确加载（无 I/O 放大）和消除双重缓存问题。

---

## 六、批判性分析

1. **Probe 定义的用户负担被低估**：论文声称 probe 机制简单易用，但实际上框架类服务（Pytorch、Tensorflow）需要用户编写内部 probe（如 `import torch`），这要求用户了解服务启动的内部细节。论文用"fool-like probes"一笔带过，但未讨论复杂服务（多阶段初始化、动态加载插件）场景下 probe 的可靠性。

2. **Runtime image 的时效性问题**：Runtime image 基于历史 I/O trace 离线生成，但论文未充分讨论当底层库版本更新、依赖变化时 runtime image 的失效检测和自动重建机制。仅提到"entrypoint 或 base image 变化时删除"，但同一 entrypoint 下依赖变化（如 pip 安装新包）的情况未覆盖。

3. **实验基线不够公平**：DADI+Trace 使用 blktrace（块级追踪），本身精度不如文件级追踪，论文将其作为"trace replay"类方案的代表进行比较。如果给 DADI+Trace 同样的文件级精确追踪能力，差距可能会显著缩小。FlacIO 的优势有多少来自"runtime image + RTPC"的架构创新，有多少来自"文件级 vs 块级追踪"的精度差异，论文未做控制实验区分。

4. **增量加载实验设计过于简单**：仅用三个 Pytorch 变体（torch / torch+triton / torch+triton+numpy）测试增量加载，这些服务高度相似。未测试真实场景中同一 base image 下差异较大的不同服务的增量加载效果。

5. **集群规模偏小**：自动扩缩容实验仅用 8 节点 × 8 容器 = 64 容器。在大规模集群（数百节点）场景下，registry 节点的 runtime image 服务是否会成为瓶颈（尤其是 `rt_diff` + 大 I/O 并发传输）未做讨论。

6. **仅适用于 root filesystem 的读路径优化**：FlacIO 只优化容器启动时对 root filesystem 的读取，对写操作和运行时数据加载无帮助。对于启动后持续产生大量读 I/O 的长时间运行容器，FlacIO 的收益会快速衰减。

---

## 七、AI Infra / MLSys 视角

1. **AI 容器冷启动是实际痛点**：论文以 Pytorch/Tensorflow 容器作为核心评测场景，这些大型 AI 框架镜像（数 GB）的冷启动在 GPU 集群弹性调度、Serverless ML 推理等场景下确实是瓶颈。FlacIO 将 Pytorch 冷启动从 27s（lazy loading）降至 ~6s，对训练任务调度效率有直接影响。

2. **对 ML 训练框架容器化部署的启示**：Runtime image 的思路可以推广到更广泛的 AI Infra 场景——例如将模型权重加载路径也纳入 runtime image 的追踪范围，预建包含模型权重 + 框架库的"推理就绪"镜像状态，进一步减少推理服务冷启动时间。

3. **与 checkpoint/restore 的结合机会**：FlacIO 的 runtime image 本质上是 root filesystem 层面的 checkpoint。如果与 GPU 状态 checkpoint（如 CUDA context、GPU memory snapshot）结合，可能实现更激进的 AI 服务热迁移/快速恢复方案。

4. **可跟进的研究方向**：
   - **模型加载加速**：将 runtime image 思路扩展到模型权重加载（如 safetensors/gguf 文件），针对推理服务的模型冷加载做类似优化
   - **大规模 GPU 集群下的 runtime image 分发**：结合 P2P 或 RDMA 技术，解决数百节点同时拉取 runtime image 的 registry 瓶颈
   - **动态 runtime image 更新**：当 AI 框架频繁更新（如 nightly build PyTorch）时，如何低成本维护 runtime image

---

## 八、总结

FlacIO 提出了 Runtime Image 这一新的容器镜像抽象，将传统的 Storage-Oriented + Global-Oriented 抽象转变为 Memory-Oriented + Service-Oriented，配合内核侧的 Runtime Page Cache 实现轻量级 I/O 栈。系统将冷启动所需数据紧凑连续存储，通过单次大 I/O 完成加载，从根本上解决了 lazy loading 的 I/O 放大和随机网络访问问题。在典型容器服务上实现了最高 4.5× 的冷启动加速（对比 lazy loading）和 23× 的加速（对比全量加载），存储开销仅增加约 5%。主要局限在于需要用户定义 probe、runtime image 维护成本，以及仅优化启动阶段的读路径。
