# eTran: Extensible Kernel Transport with eBPF

**作者**：Zhongjie Chen (Tsinghua University), Qingkai Meng (Nanjing University), ChonLam Lao (Harvard University), Yifan Liu (Tsinghua University), Fengyuan Ren (Tsinghua University), Minlan Yu (Harvard University), Yang Zhou (UC Berkeley & UC Davis)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/chen-zhongjie
**源文件**：[[nsdi2025-chen-zhongjie.pdf]]

---

## 一、背景

数据中心应用日益多样化——微服务依赖 RPC 通信、存储系统需要大量数据传输和复制、ML 应用使用 AllReduce 等集合通信原语。为了适配这些多样化需求，研究者提出了大量传输协议设计：sender-driven 的 DCTCP/Swift、receiver-driven 的 Homa/NDP、以及专为分布式训练设计的 MLT 等。

然而，极少有新的传输协议成功合入 Linux 内核主线。DCTCP 花了 4 年才进入内核，MPTCP 花了近 10 年，而 Homa (2018) 至今仍是作者自行维护的内核模块。核心原因在于内核传输协议开发和维护成本极高，且性能往往不令人满意。当前的替代方案——kernel-bypass（如 DPDK/用户态传输栈）——虽然性能好，但牺牲了内核提供的安全保护和可管理性，对公有云用户不友好。

与此同时，eBPF 技术日趋成熟：kfunc、dynptr、动态内存分配、rbtree 等功能陆续加入，为在内核中安全、灵活地定制传输协议提供了新的可能。

---

## 二、要解决的问题

1. **内核传输协议缺乏可扩展性**：Linux 内核网络栈高度固化，新传输协议落地需要数年的开发和审查，无法跟上数据中心应用快速演化的需求。
2. **kernel-bypass 缺乏保护**：用户态传输栈（如 eRPC、Demikernel）将传输状态暴露给应用进程，恶意或有 bug 的应用可以干扰传输行为（篡改 ACK、timeout 等），无法满足公有云多租户的安全需求。
3. **性能与安全的矛盾**：要实现强保护就需要把传输状态放在内核内，但内核传输协议的 user-kernel crossing 开销和固化实现导致性能差；要实现高性能就得 bypass 内核，但又丧失了保护。

---

## 三、洞察与设计

**关键洞察**：eBPF 子系统已经足够成熟，可以作为在内核中安全运行复杂传输协议逻辑的基础——通过扩展（而非绕过）eBPF 的 hook 和数据结构，可以在保持内核安全和保护的前提下，实现可定制的高性能传输协议。

基于这一洞察，eTran 将传输协议分为 **control path** 和 **data path** 两部分：

- **Control path**（用户态 daemon）：处理非性能关键的操作——eBPF 程序加载/卸载、AF_XDP socket 和 UMEM 管理、连接建立/拆除、复杂拥塞控制算法（含浮点运算）、timeout 触发的重传。
- **Data path**（内核 eBPF + 用户态库）：处理性能关键操作。内核部分通过 eBPF 程序直接操作传输状态（ACK/credit 生成、流量 pacing、快速重传）；用户态库通过 AF_XDP socket 做高效 packet IO 和 segmentation/reassembly，但**无法直接访问内核传输状态**。

为实现这一架构，eTran 对 eBPF 子系统做了三项关键扩展：

1. **XDP_EGRESS hook**：在 AF_XDP TX 路径上插入 eBPF hook，允许在出站包上执行传输逻辑（填充 TCP/IP header、流控检查、pacing redirect）。
2. **XDP_GEN hook**：在 NAPI poll 结束时插入 eBPF hook，支持在内核中批量生成 ACK/credit 包，避免跨核通信开销。
3. **BPF_MAP_TYPE_PKT_QUEUE**：新 eBPF map 类型，作为 pacing 引擎的骨干数据结构，支持 rate-based pacing（timing wheel，类似 Carousel）和 credit-based pacing（per-RPC bucket）。

此外，eTran 利用 BPF timer 的回调机制实现异步 pacing 触发，支持 per-CPU 和全局调度两种模式。

---

## 四、实现细节

eTran 原型共约 24K 行 C/C++ 代码，基于 Linux kernel v6.6.0，目标 NIC 为 Mellanox mlx5 驱动：

| 组件 | 代码量 |
|------|--------|
| Kernel 修改 | 2,597 LoC |
| Control path daemon | 8,224 LoC |
| eBPF 程序 (TCP/Homa) | 2,173 / 5,349 LoC |
| 用户态传输库 (TCP/Homa) | 3,661 / 2,024 LoC |

关键实现细节：

- **AF_XDP out-of-order completion**：原生 AF_XDP 只支持 in-order buffer completion，pacing 引入的乱序发送需要修改 buffer 管理机制（~20 LoC mlx5 驱动修改）。
- **Virtual AF_XDP socket**：一个虚拟 socket 管理多个绑定到不同 NIC queue 的真实 AF_XDP socket，通过 epoll 实现；使用 DRR 调度避免饥饿。Fill/Comp ring 共享时使用用户态 spinlock 保护。
- **Homa credit scheduling**：利用 `bpf_rbtree` 维护 credit list，新增 `bpf_rbtree_lower_bound` kfunc 实现候选 RPC 选择；用 `bpf_tail_call` 拆分复杂逻辑绕过 eBPF 指令数限制；用 per-CPU `.bss` 变量在 tail-called 程序间传递状态。
- **TCP 快速重传**：XDP hook 检测到三个重复 ACK 后回滚传输状态，将重传信息 piggyback 在 ACK 包的 headroom 中传给用户态库执行重传。Timeout 重传则由 control path 发送 dummy packet 触发。
- **eBPF 验证器**：不修改验证器，仅注册新 hook 和 kfunc；新 hook 仅暴露 XDP helper 的子集（排除 socket 相关和任意 redirect）。
- **POSIX 兼容**：应用可通过 `LD_PRELOAD` 无代码改动切换到 eTran。

---

## 五、实验结果

实验平台：10 台 CloudLab xl170 (Intel E5-2640v4, 64GB, Mellanox ConnectX-4 25Gbps NIC)，通过 Mellanox 2410 交换机连接。

### Homa 对比

| 指标 | eTran (Homa) | Linux (Homa) |
|------|-------------|--------------|
| 32B 中位延迟 | 11.8 µs | 15.6 µs |
| 1MB 吞吐量 | 17.7 Gbps | 14.5 Gbps |
| 客户端 RPC rate | 2.9 Mops | 1.7 Mops |
| 服务端 RPC rate | 3.3 Mops | 1.8 Mops |

集群基准测试（W2-W5 workload）：短消息主导的 W2/W3 工作负载中，eTran (Homa) P99 尾延迟降低 3.9-7.5×，P50 延迟降低 1.4-3.6×。

### TCP 对比

| 指标 | eTran (TCP) vs Linux (TCP) | TAS vs Linux (TCP) |
|------|---------------------------|-------------------|
| 小消息吞吐量 (1KB) | 4.8× | 7.7× |
| KV Store 吞吐量 | 2.4-4.8× | 3.9-7.9× |
| KV P50 延迟 | 17.2 µs vs 64.2 µs (3.7×) | 略低于 eTran |
| KV P99 延迟 | 27.5 µs vs 89.3 µs (3.2×) | 略低于 eTran |

eTran (TCP) 达到 TAS 吞吐量的约 87%（2KB 消息），但 TAS 使用 DPDK busy polling + 专用核心。

### CPU 开销

Per-request CPU cycles：eTran (TCP) 4.37K vs Linux (TCP) 12.51K；eTran (Homa) 5.48K vs Linux (Homa) 17.43K。主要节省来自流线化的 Socket/RPC 处理、轻量 xdp buff 替代 sk_buff、syscall-free IO。

### eBPF Hook 开销

XDP_EGRESS 空 hook 吞吐量损失 6.6%，加上 OOO completion 为 13.9%，加 HASHMAP lookup 为 21.2%。

---

## 六、批判性分析

1. **AF_XDP vs DPDK 的性能差距被低估**：论文将 eTran 与 TAS (DPDK-based) 的性能差距归因于 AF_XDP vs DPDK 的固有差异和 interrupt-driven vs busy polling 的区别，但这本质上意味着 eTran 选择了一个性能天花板更低的基础设施。对于追求极致性能的 ML 训练/推理场景，这个差距可能不可接受。

2. **TSO 不可用是重大限制**：实验中只对 Linux 启用 TSO 而 eTran 无法使用（AF_XDP 不支持），但论文将此作为"公平对比"轻描淡写。对于大消息传输（storage、ML），TSO 是关键性能因素，缺失 TSO 的 eTran 在这些场景中的实际竞争力存疑。

3. **Homa 集群基准的大消息尾延迟问题**：论文承认 eTran (Homa) 在 W4/W5 大消息下偶尔尾延迟高于 Linux (Homa)，归因于"线程调度不够优化"并留作 future work。但 Homa 的核心卖点之一就是低尾延迟，在 Homa 的标准 benchmark 上尾延迟反而劣化，这削弱了 eTran 作为通用传输框架的说服力。

4. **eBPF 编程复杂度被淡化**：Homa eBPF 实现就有 5,349 行，需要各种 workaround（tail_call 绕指令限制、bss 变量传状态、单 rbtree 模拟双层 rbtree 避免多锁）。这远非"agile customization"，实际开发门槛依然很高。

5. **安全模型假设较强**：论文假设"eBPF verifier 和 kernel 子系统是 trusted 的"，但新增了 ~2,600 行内核代码和多个 kfunc，这些新代码本身的正确性验证被推迟到 future work（"we plan to verify it formally in the future"）。

6. **实验规模有限**：所有实验在 10 台 25Gbps 机器上进行。在更大规模（100+ 节点）和更高带宽（100/200Gbps）下，eBPF 的指令预算、per-CPU 数据结构的扩展性、以及 NAPI 的 CPU 效率是否仍然足够，论文未讨论。

---

## 七、AI Infra / MLSys 视角

1. **对 ML 集合通信的启发**：论文提到 ML 应用使用 AllReduce 等原语，但未具体实现。eTran 的 eBPF pacing 引擎和 credit-based 调度机制天然适合实现 in-network aggregation 或 receiver-driven gradient 传输。一个值得探索的方向是：用 eTran 框架实现专为分布式训练优化的传输协议（类似 MLT），在保持内核保护的同时避免 NCCL 的 kernel-bypass 架构限制。

2. **推理服务的多租户传输隔离**：eTran 的多租户支持和流量管理能力对 LLM serving 场景有价值——不同模型实例可以使用不同的传输策略（prefill 用大消息优化的 TCP、decode 用低延迟 RPC 协议），且互不干扰。这在共享 GPU 集群中比纯 RDMA 方案更灵活。

3. **TSO 缺失是 AI Infra 场景的硬伤**：分布式训练和模型并行产生大量 bulk transfer，没有 TSO/GRO 支持的 eTran 在这些场景下性能受限。等 mlx5 驱动支持 AF_XDP multi-buffer 后值得重新评估。

4. **可跟进的研究方向**：
   - 在 eTran 框架上实现 RDMA-like 语义的传输协议，探索 eBPF + AF_XDP 能否在纯以太网上逼近 RDMA 性能
   - 将 eTran 的 pacing 引擎与 GPU-aware scheduling 结合，实现 computation-communication overlap 感知的传输调度
   - 利用 eBPF 的可编程性在传输层实现 flow-level load balancing，替代 ECMP 解决 AI 训练中的 incast 问题

---

## 八、总结

eTran 提出了一种通过扩展 eBPF 子系统来实现可定制内核传输协议的方案，在不牺牲内核安全和传输状态保护的前提下，通过新增 XDP_EGRESS/XDP_GEN hook 和 PKT_QUEUE map 实现了完整的传输协议功能。在 TCP (DCTCP) 和 Homa 两个代表性协议上，eTran 相比原生内核实现分别获得 2.4-4.8× / 1.7-1.8× 的吞吐量提升和 3.2-3.7× / 3.9-7.5× 的延迟降低。主要局限包括：对 AF_XDP 的性能天花板依赖、TSO 不可用、eBPF 编程复杂度高、以及新增内核代码的形式化验证缺失。适用于需要在保持内核保护的前提下快速迭代传输协议的数据中心场景。
