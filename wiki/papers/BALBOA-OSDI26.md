---
type: paper
name: BALBOA
full_title: "RoCE BALBOA: Service-Enhanced RDMA Offload Engine for Data Center SmartNICs"
authors: [Maximilian Jakob Heer, Benjamin Ramhorst, Yu Zhu, Luhao Liu, Zhiyi Hu, Jonas Dann, Gustavo Alonso]
venue: OSDI
year: 2026
tags: [rdma, smartnic, fpga, roce, in-network-computing]
source_pdf: "[[osdi26-heer.pdf]]"
source_md: "[[osdi26-heer]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向数据中心 SmartNIC 的服务增强 RDMA 卸载引擎（OSDI 2026）

> **原题**：RoCE BALBOA: Service-Enhanced RDMA Offload Engine for Data Center SmartNICs

> **一句话总结**：BALBOA 是一个开源 FPGA RoCEv2 transport engine，用 512-bit 流水线、分离的 data/control/completion stream、片上 QP state 和 HBM retransmission buffer，在 Cisco 交换机上与 ConnectX-5/7 跑到约 11.2–11.6 GB/s 的 100GbE payload ceiling，并能插入 AES、DPI 与 RDMA-to-GPU preprocessing；但它实现的是 RC 模式的一侧 RDMA READ/WRITE 子集，500-QP 只是构建容量、性能只测到 32 QP，当前也没有 DCQCN/TIMELY 一类拥塞控制，所以“严格合规、可扩到 200G、可用于生产安全服务”都应看作有边界的论断。

## 问题与动机

[[RDMA]] 把 transport 和 DMA 放进 NIC，使应用绕过 host OS 获得低时延、高吞吐。代价是 ConnectX、BlueField 等商用 RNIC 的 packet-processing pipeline、重传、拥塞控制与状态机大多是固定硬件。研究者想加入新的 encryption、telemetry、access policy、retransmission 或 application preprocessing 时，只能把逻辑放回 host CPU、放到较慢的 DPU core，或接受厂商开放的有限 offload slot；这样很难修改 transport 本身，也常失去 line rate（§1–§2）。

FPGA SmartNIC 理论上可修改，但已有 research stack 往往只实现简化协议，缺少 ICRC、可靠重传、RDMA READ、host/GPU DMA 或与商用 NIC/交换机互通。另一类 FPGA NIC 只有 Ethernet/IP shell，RDMA transport 仍由 host software 处理。这些平台适合证明某个 operator 能工作，却不足以在真实 switched RoCE network 中研究“修改 transport 后会怎样”（§3、表 1）。

BALBOA 想同时满足四个要求：100G throughput（R1）、与现有 RoCEv2 NIC/switch 互通（R2）、为用户逻辑保留足够 FPGA resource（R3），以及用公开、模块化接口修改 datapath 和 protocol（R4）。这里的“protocol adherence”不是实现整个 verbs/transport matrix。论文 §4.1 明确把范围限制为 Reliable Connection（RC）和一侧 RDMA WRITE/READ；UC 只是作者认为容易追加的未来扩展，SEND/RECEIVE、atomic 等也没有列为已实现功能（表 2）。

## 关键观察 / 隐含假设

- **观察 1：开放性和 100G 不一定冲突，前提是把复杂 transport 拆成能深流水的固定接口模块。** BALBOA 把 IP、UDP、InfiniBand header、ICRC、flow control、retransmission 和 arbitration 拆开，用 AXI4-Stream 传 data、command 和 completion（§4.2–§4.3、图 1–3）。
  - **依赖假设**：每个扩展都能保持 initiation interval 1，或在 parallel path 中及时给出 metadata decision，不阻塞 512-bit stream。
  - **可能失效场景**：variable-latency lookup、data expansion、随机外部内存访问或会 stall 的 RX operator 会向网络施加 backpressure，最终导致 packet drop。
- **观察 2：双向 line rate 的关键不是单纯把总线加宽，而是避免 RX/TX 在状态和数据上互相等待。** Connection、PSN、MSN 等表放入 dual-port BRAM，RX/TX 独立；RDMA WRITE data 与 RDMA READ response data 走不同输入 stream，再在 HBM-backed retransmission 模块仲裁（§4.3–§4.4）。
  - **依赖假设**：常用 QP state 能放在片上 BRAM，两个端口和 shared timer 足以处理并发更新。
  - **可能失效场景**：QP 数、QP churn、timeout event 或双向小包率大幅增加时，state table 和 control path 可能先于 512-bit data bus 饱和。
- **观察 3：protocol-aware service 能直接看到 QPN、PSN、header 和 payload，因此比 transport 外的通用 accelerator 更容易保持语义同步。** AES 可用 QPN 与 per-packet counter 构造 CTR counter；parallel DPI 又可把判定 flag 送进 BTH processing，而不用 host side-channel（§5.2）。
  - **依赖假设**：counter 在 QP 重建、重传、重启和 key rotation 后仍全局唯一，service metadata 与 packet ordering 始终对齐。
  - **可能失效场景**：QPN 重用或 counter rollback 会复用 CTR keystream；parallel decision 晚到、丢失或错配会让 packet policy 不一致。
- **观察 4：外部 HBM 容量可以换取可靠传输所需的 bandwidth–delay buffer，而不占片上 SRAM。** 每个 flow 最多 16 个未确认 4 KiB packet，对应 64 KiB；32 GB HBM 从容量上可容纳约 500K 份这种 buffer（§4.4）。
  - **依赖假设**：HBM latency 和 arbitration 不会阻塞 retransmission，且其他应用不会争用同一 HBM bandwidth。
  - **可能失效场景**：这只是 buffer 容量上限；默认 on-chip QP state 仍只有 500 项，不能据此声称已经支持 500K active QP。
- **假设 1：250 MHz × 512 bit 的 128 Gb/s raw bandwidth 留出的余量足以在协议开销后维持 100GbE。**
  - **证据强度**：100G hardware 结果支持；完整 design 在 400 MHz 能过 synthesis timing，只能说明 200G 有候选路径，不能替代 200G PHY、[[PCIe|PCIe]]、HBM 和 end-to-end 验证。
- **假设 2：三种 demo 足以代表 extension interface 的普遍可用性。**
  - **证据强度**：中。AES、ternary-NN DPI、三个 stateless preprocessing operator 覆盖了 serial、parallel 与 application slot，但都属于可深流水、固定成本的友好 workload。

## 核心方法

BALBOA 运行在 AMD Alveo U55C 上，论文评测使用 Coyote v2 shell、XDMAcore 做 host DMA、100G CMAC 接网络。核心总线是 512-bit AXI4-Stream、250 MHz，理论 raw rate 为 128 Gb/s。IP、UDP 与 InfiniBand/BTH/RETH 的 RX/TX stage 用 Vitis HLS 实现；RX 剥离 header 并在旁路 control bus 上生成 state command，TX 则分别接收 command 和 payload，再逐层生成/合并 header。独立 completion stream 把 ACK/NAK 和 flow-control event 从 data path 中分离（§4.2–§4.3、图 1–2）。

### QP 状态、重传与流控

Connection、read request、PSN/MSN 和 transport timer 等状态放在 dual-port BRAM，默认 build 支持 500 QP。RX 与 TX 可同时访问，避免一边更新状态时阻塞另一边。这个数字可通过综合配置扩大，但论文没有给扩大后的 timing/resource/performance（表 2、§4.3）。

发出的 WRITE payload 和 READ RESPONSE payload 都先保存在一条直接暴露的 HBM channel，直到远端 ACK。timeout 或 PSN error 触发 RC 的 Go-Back-N retransmission；命令决定从 host 新数据还是 HBM 旧数据取 payload。作者报告取回一个 4 KiB MTU payload 需 1.732 μs，从首次重传指示到完整 packet 开始送往 Ethernet block 为 1.86 μs（§4.4、图 3）。

当前 flow-control block 是每 QP 固定大小、ACK-clocked 的 sliding window，默认最多 16 个 outstanding packet；收到 ACK 才补回预算。底层 CMAC 支持 PFC。这个机制限制 in-flight data 并支持 Go-Back-N，却不是根据 ECN、RTT 或 queue condition 调速的 datacenter congestion control。论文说 DCQCN、TIMELY 可以替换此模块，运行时 partial reconfiguration 也“未来可能”做到；两者都未实现或评测（§4.5）。

### 协议处理与扩展接口

RoCEv2 的 ICRC 对不同 header field 有规范化规则，而且 512-bit beat 的最后一拍可能不满。BALBOA 分别为常见的 512-bit、320-bit beat 做并行 pipeline，再用多级 32-bit path 覆盖其他 4-byte-aligned 长度；计算后的 CRC 插回 packet（§4.6）。系统还在 CMAC 旁放了双向 100G traffic sniffer，可按 header filter、只抓 header 或输出 PCAP 给 Wireshark，但论文没有单独量化它的 buffer、丢包率或 resource overhead（§4.7）。

扩展有三种位置（§5、图 1）：

- on-datapath protocol service 位于 transport 前后，直接变换 payload，例如 AES-CTR；TX 可利用 command/data 分离吸收部分仲裁，RX operator 则必须不 stall。
- parallel-path service 读取 packet copy，在 transport pipeline 仍执行时计算 metadata，再把结果送回 header logic，例如 DPI。它可以隐藏 inference latency，却要求 decision 与原 packet 严格对齐。
- application slot 只服务选定 QP，可访问 local/remote data、command、interrupt 与 CPU/GPU DMA，例如把收到的 DLRM feature 在进入 GPU 前转换。

作者给 RTL、HLS、hls4ml/P4 三种开发路线：RTL 控制最强但通常按“周”计，HLS 可按“天”计，hls4ml 可把训练好的 model 直接变成 pipeline。论文还提供 logic simulation framework，用同一设计通过一个 compile flag 在模拟与部署之间切换；不过“在很多产学合作和 production system 中证明易用”的说法没有 developer study、集成工时或 bug 数据支持（§5.1、§5.3）。

### 三个示例服务

AES demo 是开源 AES-CTR RTL block，插在 payload stream 上，11 cycles、44 ns，维持 line rate。它用 QPN 加 per-packet counter 构造 IV/counter，论文还讨论把 block 移到 header 内做“stealth communication”，但实测只覆盖所示 AES data path。CTR 只提供 confidentiality，不提供 authentication、replay protection、key exchange、rotation 或 tenant policy；这些生产安全要素不属于实现（§5.2.1）。

DPI demo 是通过 hls4ml 部署的 fully connected ternary neural network。它把每个 512-bit beat 的 payload 与 QPN 送入模型，44 ns 给出 decision，再由 aggregator 通知 BTH stage；系统可标 flag/interrupt，或直接 drop packet。模型训练目标是区分 CSV、PNG、TXT 与 compiled executable，不是判断 executable 是否真的恶意。97.83% full-payload、89.35% partial-embedded detection 来自该模型与引用 [44] 的口径，不代表通用 malware detection（§5.2.2、§6.3.2）。

应用 demo 从 Meta DLRM preprocessing 中选 Neg2Zero、Logarithm、Modulus 三个 stateless operator，每个都做成 initiation interval 1 的深流水。远端数据经 RDMA READ 到本机后，可以先写 host memory 再由 CPU 处理并复制到 GPU，也可以在 FPGA 处理后再经 host copy，或在 FPGA 处理后直接 P2P DMA 到 AMD MI210（§8、图 8）。论文没有运行完整 recommender training/serving job，也没有测模型 accuracy；评测对象是这三步数据转换和搬运。

## 设计取舍

- **片上确定性换 QP 规模**：默认 500-QP state table 很省 BRAM、时延稳定；HBM 可放 500K retransmission buffer 不等于 control/state path 能服务 500K connection。
- **HLS 模块化换实现效率不确定**：packet processing 更容易理解和修改，但 BALBOA 相比 Limago 使用更多 FF/BRAM；跨 Vitis version 的 timing 和生成结果也可能变化。
- **固定 window 换简单可靠性**：ACK window 与 Go-Back-N 容易实现、能和 RNIC 互通；没有已实现的 ECN/RTT-aware congestion control，复杂 incast/PFC 场景不在证据范围。
- **line-rate 接口换 operator 表达力**：固定延时、streaming、stateless operator 很合适；会扩大数据、访问随机 state、产生 variable output 或低于 line rate 的模块需要端到端限速和 buffering。
- **开放 datapath 换 correctness/security 责任**：研究者能改 header、payload 和 command，也可能破坏 PSN、length、ICRC 或 retransmission invariant；论文没有 extension verifier 或 tenant isolation。
- **FPGA 灵活性换部署成本**：相对 ASIC 可以重综合，代价是 FPGA board、toolchain、bitstream rollout 和回滚；这些运维成本没有与商用 SmartNIC 比较。
- **协议子集换实现可控**：RC READ/WRITE 是重要且复杂的一侧路径，但不支持的 SEND/RECEIVE、UC、atomic 和完整 verbs surface 限制了 drop-in compatibility。

## 实验与结果

- 测试集群用 Alveo U55C 上的 BALBOA、Mellanox ConnectX-5、BlueField-3 内的 ConnectX-7，以及 Cisco Nexus 9000 switch，MTU 4 KiB。Figure 4 每个点 100 次，latency 用单 buffer + completion polling，throughput 用 batched transfer；作者还说在两层 fat-tree、U250、U280 上验证过相同结果，但没有分别给图。WRITE 和 READ 在 32 KiB 及以上都接近 11.2–11.6 GB/s，即 100GbE 的 payload ceiling；64-byte WRITE 时 BALBOA 约 5.5 μs，ASIC 约 2–3 μs，64-byte READ 时 BALBOA 约 7.8 μs，ASIC 约 4–6 μs。中等大小 READ 也更慢，论文归因于 FPGA 250 MHz generic PCIe hardblock 发出/跟踪 non-posted read tag 的能力低于约 1 GHz ASIC controller（§6.1、图 4）。
- 32 KiB RDMA READ 的 multi-QP 实验从 1、2、4、8、16 到 32 QP。BALBOA aggregate 保持约 11.2–11.5 GB/s；2 QP 各约 5.7 GB/s，4 QP 各约 2.8 GB/s，8 QP 各约 1.42 GB/s，表明 arbiter 分配较均匀，ConnectX 走势类似（§6.2、图 5）。这支持 32 个并发 QP 的公平共享，不直接验证默认 500 QP 的 packet rate、tail latency 或 churn。
- 重传 datapath 报告 4 KiB HBM fetch 1.732 μs、首次 indication 到完整 retransmit packet 1.86 μs；16-packet window 使每 QP 最多缓存 64 KiB（§4.4）。论文没有注入不同 loss/reorder rate，也没有展示 Go-Back-N recovery throughput、timeout precision、重复/乱序 correctness 或与 ConnectX NAK corner case 的 conformance test，所以“可靠交换网络运行”主要由正常互通和设计说明支撑。
- AES datapath 增加 44 ns pipeline latency，并在图 6 中维持约 11 GB/s；host baseline 用 EPYC 7302P 16 cores、OpenSSL AES hardware support，由远端 RDMA doorbell 触发并 polling，16 KiB 时图上只有约 0.22 GB/s。这个数量级差包含 CPU scheduling/doorbell/polling 和 data movement，不是纯 AES primitive 对比；作者尝试 BlueField-3 IPsec hardware baseline 但因 patched strongSwan 的文档/依赖问题未跑通。DPI 的 44 ns parallel inference 被 transport latency 隐藏，图 7 看不出 throughput/latency 下降；模型报告 97.83% full executable、89.35% partial executable detection，但安全 accuracy 的详细数据在引用 [44] 而非本文（§6.3、图 6–7）。
- U55C post-route estimate 中，基础 BALBOA 占 43,732 LUT（3.4%）、101 BRAM（5.1%）、102,988 FF（4.0%），估算 1.745 W。AES 另占 65,662 LUT（5.0%）、估算 0.356 W；DPI 含 extractor/model 共 54,404 LUT（3.75%）、估算 3.231 W。三者 LUT 相加为 12.15%，功耗若按表内模块相加约 5.33 W；论文突出写出的 1.745 W 只是 base stack，不是含两项 service 的整卡实测。相同 500-flow/U55C 条件下，BALBOA 比 Limago 少 18% LUT，却用更多 FF（102,988 对 72,974）和 BRAM（101 对约 78）。完整设计在 400 MHz 能通过 synthesis timing，但没有 200G hardware result（§7、表 3）。
- DLRM micro-pipeline 平台是 U55C、AMD MI210、EPYC 7V13；FPGA–GPU 间 PCIe switch 把上限限制在 70 Gb/s，即 8,500 MB/s。setup 3（FPGA preprocessing + direct GPU P2P）在大 buffer 达 8,500 MB/s；setup 1（host memory + CPU preprocessing + GPU copy）即使用 8 cores 最高也约 1,190 MB/s，吞吐约差 7.1 倍（图 9）。图 10 比较的是 setup 3 与 setup 2（FPGA preprocessing 后仍经 host memory copy），direct GPU 在 192 B–3 MiB buffer 上节省约 19–135 μs；它不包含 CPU preprocessing latency。因此结果证明三个 stateless operator 与一次 copy 的 offload 收益，不等于完整 DLRM training/serving 加速（§8、图 8–10）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 开源 FPGA transport 可在交换网络中与商用 RNIC 跑到 100G-class payload ceiling | 图 4：U55C 与 ConnectX-5/7 的 READ/WRITE 接近 11.2–11.6 GB/s；小消息 latency 仍落后 ASIC | RC、一侧 READ/WRITE、4 KiB MTU、单层图；两层结果未单列 | 强 |
| arbiter 可在多 QP 间均匀共享 line rate | 图 5：1–32 QP aggregate 稳定、2/4/8 QP 分配接近均分 | 仅 32 KiB READ，最多 32 QP；未测500 QP与小包 | 强 |
| protocol pipeline 能加入固定延时服务而不降 line rate | 图 6–7：AES、DPI 保持 throughput；44 ns pipeline/inference | 两个适合 streaming 的模块，不代表任意 extension | 强 |
| 基础 transport 为应用 offload 留出大量 FPGA logic | 表 3：base LUT 3.4%、BRAM 5.1%，加 AES+DPI 的 LUT 12.15% | U55C post-route estimate；功耗不是整卡实测 | 中到强 |
| RDMA-to-GPU preprocessing 能消除该 pipeline 的 CPU bottleneck | 图 9–10：8.5 对 1.19 GB/s，direct path 省 19–135 μs | 三个 stateless operator、MI210、70G PCIe ceiling；无完整 model job | 强 |

## 批判性分析

### 论证链条

论文最重要的贡献不是某个 AES 或 DLRM operator，而是一个能放进现有 switched RoCE cluster 的开放 transport substrate。相关工作表指出此前 FPGA stack 常在“100G、开源、商用 NIC 互通、switch、GPU DMA、可改 transport”中缺几项；BALBOA 再用 U55C–ConnectX-5/7 的真实互通、32-QP 分享和三个 extension 证明这些能力可以同时出现。这比只做 FPGA-to-FPGA loopback 的 testbed 更有说服力。

不过论文多次使用“strict protocol compliance”“matches commercial ASICs”等宽泛表述，自己的细节给出了更窄结论。实现只覆盖 RC READ/WRITE；Figure 4 说明大消息 throughput 接近，但小消息 latency 和中等 READ throughput 明显落后 ASIC；默认 connection state 是 500 QP，性能图只到 32。更准确的论断是“重要的一侧 RC 子集达到 100G 并与两代 ConnectX 互通”。

### 假设压力测试

固定 16-packet ACK window 在单流、正常交换网络中简单有效，但它没有根据 congestion signal 调速。incast、长 RTT、PFC pause、ECMP reorder 或多租户 noisy neighbor 可能让 Go-Back-N、HBM fetch 和 command queue 相互放大。论文把 DCQCN/TIMELY 和 partial reconfiguration 描述成容易替换的方向，却没有实现后的 timing closure、state migration 或协议行为；模块接口开放不代表算法可以无成本替换。

extension 的“任意逻辑”也受 line-rate contract 限制。AES、ternary NN 和三个 stateless feature transform 都有固定、短 latency，并能每周期接收新 beat。压缩、variable-length parsing、hash-table lookup、stateful aggregation 或 output expansion 会遇到 backpressure、buffer sizing 和 metadata rejoin。§5.3 实际承认 RX path 不得 stall，低于 line rate 的 offload 必须让远端主动降速；这已经把一部分复杂性推回 end-to-end application。

### 实验可信度

硬件平台、commercial NIC、真实 switch、多个 message size、READ/WRITE、multi-QP、resource 与 application path 都有覆盖，是很扎实的 prototype evaluation。图 4 还展示了不利结果：小包 latency 与 medium READ 的差距没有被隐藏。resource 表给到子模块 LUT/BRAM/FF/power，也能看出 DPI 的 3.231 W 估算远高于 base stack中其他子模块。

缺失项恰好集中在 production transport 最难的角落：没有 injected loss/reorder、incast/ECN/PFC、长时 soak、QP churn、500-QP performance、双向同时饱和、memory-registration isolation、malformed packet 或 conformance suite。两层 fat-tree、U250/U280 的“相同结果”没有数据。功耗是 post-route estimate，不是板卡 wall power；与 Limago 的 18% LUT 对比也只比较 resource，不代表相同功能、频率和 shell 下的端到端性能。

AES CPU baseline 是一个实际 service path 对比，但它把 doorbell、host polling、CPU processing 与数据搬运一起算入；因此可以说 BALBOA offload path 大幅更快，不能把差值全部归因于 AES engine。BlueField hardware baseline 没跑通，又让“优于 commercial programmable/offload NIC”的判断缺少最关键对照。DLRM 只测三种 stateless transform，不测 GPU kernel preprocessing、完整 training throughput、accuracy 或 CPU implementation tuning。

### 系统性缺陷

安全 demo 需要特别克制。AES-CTR 没有 authentication，攻击者可翻转 ciphertext bit；QPN+packet counter 的 uniqueness 还依赖 QP reuse、restart、retransmission 和 key lifecycle 没有复用。DPI 识别的是“可执行文件形态”，不是 malware intent，也没有对加密、压缩、分片、adversarial payload 或 concept drift 做本文内评测。把两者称为关闭 RoCE access-control/security gap 会超过证据。

开放 transport 还扩大了 fault domain。用户 module 若错误修改 length、command、PSN 或 ICRC，可能破坏可靠性，甚至让一个 QP 影响其他 QP。论文没有 hardware sandbox、resource quota、extension verifier、bitstream signing、live update rollback 或 multi-tenant isolation。traffic sniffer、simulation framework 和模块边界有助调试，却不是 production safety mechanism。

最后，作者用 32 GB HBM 除以 64 KiB 得到约 500K QP buffer capacity，这是容量计算，不是已实现 scalability。真正扩到这个数量还要解决 BRAM state、timer、completion rate、cache、PCIe control plane 和 recovery storm。类似地，400 MHz timing closure 只覆盖 logic synthesis；200G 还需要 PHY、MAC、host/GPU I/O 和全系统时序。两者都应保留为未来方向。

## 局限与后续工作

- **局限 1**：实现只覆盖 RC 模式的一侧 RDMA WRITE/READ，不是完整 RoCEv2 verbs/transport feature set。
- **局限 2**：默认 state table 是 500 QP，性能只测到 32 QP；HBM 的约500K-QP容量是理论 buffer 上限。
- **局限 3**：当前只有固定 ACK sliding window 与底层 PFC，没有实现或评测 DCQCN、TIMELY、ECN/RTT-aware congestion control。
- **局限 4**：没有 loss/reorder/incast/PFC/soak/conformance 实验，重传和 corner-case interoperability 主要靠设计说明。
- **局限 5**：AES-CTR 缺少认证、replay protection 和 key lifecycle；DPI 只识别有限 payload class，不能等同通用恶意流量检测。
- **局限 6**：资源和功耗来自 post-route estimate，不是整卡实测；缺少与 BlueField/ConnectX programmable path 的成功对照。
- **局限 7**：DLRM case 只有三个 stateless operator，没有完整训练/serving、模型质量、GPU preprocessing 或 optimized CPU/GPU baseline。
- **局限 8**：200G 只有 400 MHz synthesis timing，未验证端到端硬件与 I/O bottleneck。
- **后续工作 1**：建立 packet-level conformance/fault-injection suite，覆盖 timeout、NAK、duplicate、reorder、MTU 边界和 ConnectX corner case。
- **后续工作 2**：从 32 扩到 500 乃至更多 QP，扫描 small-message packet rate、tail latency、QP churn、BRAM/HBM 和 timer pressure。
- **后续工作 3**：真正实现 DCQCN/TIMELY 或新 congestion control，在 incast、ECN、PFC pause 和两层 fat-tree 下与 ConnectX 比较 fairness 与 recovery。
- **后续工作 4**：给 extension slot 增加接口检查、resource quota、per-QP isolation 和可回滚 bitstream lifecycle，并故意注入错误 module 测 fault containment。
- **后续工作 5**：把 AES 升级为带认证的加密，定义 QP restart/rekey/replay semantics；对 DPI 加入 encrypted/adversarial payload 与 drift evaluation。
- **后续工作 6**：在 200G-capable FPGA 上测 MAC、PCIe、HBM、GPU P2P 的完整路径，并报告板卡 wall power、cost 和长时稳定性。

## 相关

- **相关概念**：[[RDMA]]、RoCEv2、FPGA SmartNIC、in-network computing、GPU Direct、可靠重传
- **相关系统**：ConnectX、BlueField、StRoM、Limago、Coyote v2
- **同会议**：[[OSDI-2026]]
