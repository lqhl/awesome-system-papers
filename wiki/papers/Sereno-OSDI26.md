---
type: paper
name: Sereno
full_title: "Inference in the Shadows: Taming Memory Bandwidth Contention in Mobile LLM Inference with Sereno"
authors: [Tong Xin, Xinrui Shi, Mingkai Dong, Zeyu Mi]
venue: OSDI
year: 2026
tags: [mobile-systems, llm-inference, memory-bandwidth, qos, speculative-decoding, area/ai-infra]
source_pdf: "[[osdi26-xin.pdf]]"
source_md: "[[osdi26-xin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Sereno：缓解移动端 LLM 对前台应用的内存带宽干扰（OSDI 2026）

> **原题**：Inference in the Shadows: Taming Memory Bandwidth Contention in Mobile LLM Inference with Sereno

> **一句话总结**：手机NPU、CPU和GPU共享DRAM，但NPU沿用相机等实时媒体任务的高优先级；后台Llama-8B因此只损失约1%吞吐，却让25个前台应用的总jank增加153%。Sereno把[[Speculative-Decoding|推测解码]]的draft layer变成亚毫秒让出点，用自身执行时间感知争用，再以draft preemption、verification batch和micro-sleep调节带宽；30-app测试中，平均jank比PowerServe低58.5%，LLM吞吐反而高26.4%。

## 问题与动机

手机上的notification summary、translation和agent subtask往往在后台短时运行，同时用户正在滚动、游戏或看视频。虽然LLM算子在NPU执行，CPU负责应用逻辑、GPU负责rendering，三者仍通过统一内存架构（UMA）共享LPDDR与system interconnect；几毫秒的NPU DMA burst就可能让前台frame错过8.3 ms的120 Hz deadline（§1–§2）。

OnePlus 13上的初始测量让Llama-3.1-8B [[Quantization|W4A16]]分别与25个app共跑，每次只有一个前台app。总jank rate增加153%，各app归一化jank平均3.13倍，Discord接近原生18倍；CPU/GPU benchmark throughput下降37.2%–49.6%。与此同时，后台LLM prefill/decode throughput平均只下降1.01%/1.64%，形成“前台受伤、后台几乎不受影响”的非对称干扰（§3.1、图 2）。

PMU与profiler显示CPU/GPU utilization和cache/TLB miss基本不变，但CPU memory stall cycles、LLC miss latency、GPU memory stall分别升3.8、3.5、3.1倍。作者再检查Snapdragon 8 Elite、Dimensity 9400和Exynos 2400的kernel/device-tree：NPU traffic使用高优先级/urgency路径，却没有CPU侧MPAM、memlat和thermal control。这个policy原本保护4K60 camera pipeline，如今被best-effort LLM继承（§3.2–§3.3、图 3、表 1）。

直接限频或chunk-and-sleep会停止推理进展；商业NPU又把static graph当作不可中断单元。前台composition burst平均约2.25 ms，作者据此要求control interval不超过约1.125 ms，而8B target model即使按layer切分，subgraph仍需5–8 ms。关键问题因此是：能否在不改SoC/driver、也不破坏模型输出的前提下，创造更细的可让出点（§4.1）。

## 关键观察 / 隐含假设

- **观察 1：干扰根因是bandwidth arbitration，不是NPU compute sharing。** foreground compute/cache指标平坦，memory latency指标升3–4倍；NPU自身吞吐几乎不降（§3、图 2–3）。
  - **依赖假设**：前台也是memory-latency sensitive。较弱Snapdragon 8 Gen 3的gaming更常受compute限制，Sereno的jank降幅从Elite的52.03%降到29.70%（§7.5、图 14）。
- **观察 2：推测解码的tentative work可以丢，committed state不能。** draft model由多个亚毫秒layer subgraphs组成，可在边界提前进入verify；target model仍验证所有候选，因此错误draft或n-gram token不会改变最终输出（§4.2、§5.1）。
  - **依赖假设**：模型有高效speculative path，draft layer足够短；纯autoregressive engine、不可rollback的SSM state或acceptance极低时，控制粒度和收益都会变差。
- **观察 3：[[LLM|LLM]]自身可充当近零额外流量的DRAM probe。** 同一draft subgraph在无争用时延迟稳定，争用时DMA stall直接延长执行；125,060 samples中，contention score与stall cycles per LLC miss在测量区间内Pearson `R≈0.86`（§5.2、§7.3、图 11）。
  - **依赖假设**：每个subgraph先离线calibrate，compiler、temperature、DVFS或模型更新后baseline仍有效；论文没有长期漂移实验。
- **观察 4：draft与verify的带宽形态互补。** EAGLE-3 decode有94.7%时间bandwidth-bound；draft batch=1最吃带宽，较大的verify graph让一次target-weight traversal验证更多候选，平均bandwidth demand从B=1的1.00降到B=32的0.74、B=128的0.38（§4.2、§5.1）。
  - **关键边界**：大verify batch是更长的atomic burst，也需要更多低置信候选；较低平均带宽不等于总吞吐必然更高。
- **观察 5：粗暴cap会让speculation变成负优化。** 把verification bandwidth限制50%时，EAGLE-3吞吐下降54%，甚至比non-speculative baseline低8.4%；控制器必须尽量保留有效进展，而不是统一throttle（§4.2）。
- **假设 1：前台QoS优先于单请求后台latency，但后台不能永久饿死。** 默认policy用12 token/s token-bucket guardrail，若持续亏空会放宽阈值，最后暂时退回uncontrolled speculative decoding；这会有意重新引入一些前台干扰（§5.3、§6）。

## 核心方法

### 弹性推测解码（Elastic Speculative Decoding）

Sereno用QNN把Llama-3.2-1B draft model按Transformer layer编译成亚毫秒static subgraphs。controller只能在subgraph之间preempt：停止剩余draft layers，保留已生成候选并立刻进入target verification；已经commit的token与KV不回滚。它没有让一个正在执行的NPU graph真正中断（§5.1、图 4）。

preempt后候选不足，N-gram Filling从本地prompt、已验证输出和被拒draft序列构建多来源cache，用frequency filter自清理，并让较长n-gram match权重更高。填入token仍由target model验证，所以方法声称lossless；它补偿吞吐，不是bandwidth-control primitive（§5.1、§7.4）。

verify阶段预编译B=8/16/32等不同batch的graphs并共享weights。轻争用选较小batch，减少等待draft candidates；重争用选较大batch，降低平均memory-bandwidth demand。商业runtime要求batch size在export时固定，所以支持多少档位取决于预编译graphs，而非运行时任意变形（§5.1）。

### 内生传感器与反馈控制

系统为每个unique draft subgraph离线记录无争用latency。运行时计算 `CS=(T_actual−T_baseline)/T_baseline`，形成亚毫秒contention score。它是reactive sensor：不预测触摸或render path，而是在NPU自身变慢后响应；hysteresis要求连续超阈值才preempt，减少noise触发（§5.2）。

PI controller把score error映射到三档actuation：draft阶段稍有争用就立即preempt；verify阶段按强度选择更大batch；每个5–8 ms verify subgraph之间再插1–2 ms micro-sleep，使平均duty cycle约低10%–25%。不用derivative项，以免放大mobile scheduling noise（§5.3）。

默认Balanced policy设`CS_target=0.15`并启用12 token/s guardrail；UI-First policy设0.07且关闭guardrail。controller参数通过Ziegler–Nichols脚本按SoC自动calibrate。实现基于PowerServe/QNN 2.39，新增约6.4K行C++（§6）。

## 设计取舍

- **可丢draft work换亚毫秒yield**：不损坏committed output；acceptance从throughput-oriented speculation的30.4%降到18.9%，大量候选最终被拒（§7.3）。
- **内生reactive sensor换硬件计数器**：几乎不产生额外memory traffic；只能在contention已影响一个draft subgraph后发现，也需要逐graph calibration。
- **多个static graphs换运行时弹性**：兼容black-box NPU；增加export/storage和模型升级维护，动作只能取预编译batch档位。
- **更大verify batch换较低平均带宽**：每次读target weights服务更多候选；atomic burst更长，且N-gram低置信候选会降低acceptance。
- **micro-sleep换前台headroom**：比长期sleep细；期间仍是零进展，过强policy直接损失LLM throughput。
- **token-bucket连续性换严格QoS**：保证后台不饿死；persistent contention下fail-safe会关闭干预，不能给foreground hard SLO。
- **软件兼容性换平台专用实现**：不改kernel/driver；目前定量实验只覆盖两代Snapdragon和dense Llama，其他SoC只有source分析。

## 实验与结果

- **平台、负载与口径**：主机为OnePlus 13/Snapdragon 8 Elite，泛化机为OnePlus 12/8 Gen 3，均24 GB LPDDR5X；target是Llama-3.1-8B W4A16，draft是Llama-3.2-1B W4A16。30个app含25个常用app和5个heavy games；每次只跑一个foreground app+后台LLM，每个15个GSM8K prompt约45秒，去掉两高两低后取均值（§7.1）。
- **前台QoS与后台吞吐**：相对PowerServe，Sereno jank最高/平均降低92.6%/58.5%，LLM throughput最高/平均提高67.9%/26.4%。跨所有category平均jank为6.21%（Native 4.91%），slow rendering为0.44%（Native 0.35%）；Social场景为8.14% jank、16.00 token/s，对Native 6.18%和PowerServe 22.12%（§7.2、图 5）。
- **与speculation/naive control比较**：throughput-oriented Speculative在Social为19.84 token/s但jank 15.38%；Sereno用16.00 token/s换到8.14%。“jank低72.1%、性能只低6.2%”是Reader这个特定case，不是30-app平均。Freq-Limit约6.74 token/s且jank 18.55%；Sereno整体约为这些naive strategies吞吐2.5倍（§7.2、图 5）。
- **请求latency与sporadic workload**：512-prefill+128-decode的平均turnaround为10.21秒，比PowerServe 11.25秒低9%；但prefill从0.99变2.09秒，最终变快来自speculative decode补偿。50秒period下20%–80% duty cycle，Sereno jank为0.72%–1.16%，约为PowerServe一半，并在60%/80%达到8.48/11.32 effective token/s；effective TPS把idle也算进分母（§7.2、图 7、10）。
- **机制与消融**：PowerServe让CPLM从Native 2.76升到7.15，Sereno降到4.17（比PowerServe低42%）。四app消融中，standard speculation为8.5% jank/19.7 token/s；draft preemption降至4.5%/13.9，batch与sleep继续到3.6%/12.9，N-gram把吞吐恢复到15.6而jank为3.7%。单独N-gram改进把受限setup吞吐从14.42提高18.06（§7.3–§7.4、图 8、12）。
- **能耗、开销与硬件边界**：Sereno为3.52 token/J，略低于Speculative 3.78，但高于CPU 1.81和Chunk-Sleep 2.07；controller与N-gram多用约单核4.7% CPU，内存增加0.86 GB（19%，主要是1B draft weights），额外static graphs少于70 MB。8 Gen 3的Tools/Social仍降jank约58.79%/62.34%，Gaming只降29.70%，说明compute bottleneck下机制有限（§7.5、图 13–14）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 移动LLM会造成严重且非对称的foreground interference | 25 apps总jank +153%，LLM prefill/decode仅−1.01%/−1.64%；memory stall升3–4倍（图 2–3） | OnePlus 13、Llama-8B持续stress；app逐个测试 | 强（该平台） |
| draft latency可作为bandwidth-contention proxy | 125,060 samples中score与CPLM `R≈0.86`（图 11） | `CPLM≤22`的测量范围、per-subgraph离线calibration | 强（相关性） |
| Sereno改善QoS–throughput Pareto frontier | 对PowerServe平均jank−58.5%、throughput +26.4%；平均jank接近Native（图 5） | 30 apps、两代Snapdragon、单target/draft模型 | 强（测试集内） |
| 各actuator作用互补 | preemption主降jank，batch/sleep继续保护，N-gram恢复20.9%吞吐（图 12） | 只选四个代表app；增量顺序固定 | 中到强 |
| 方法在非持续burst中仍有效 | 20%–80% duty cycle均约将PowerServe jank减半，并保持更高effective TPS（图 10） | 5个轻前台app、合成50秒period、5分钟trace | 中 |

## 批判性分析

### 论证链条

论文先用跨层测量确认bandwidth contention，再从SoC policy解释非对称性，最后把speculative draft的可丢性映射到控制点，observation→design链条清楚。图8证明物理stall确实下降，图12又分离actuator与补偿机制。需要降调的是“win-win”：相对non-speculative PowerServe，speculative acceleration可同时提高吞吐和QoS；相对uncontrolled speculation，Sereno明显牺牲吞吐，例如Social从19.84降到16.00。它找到更好Pareto点，不是无代价消除争用。

### 假设压力测试

若foreground主要compute-bound而非bandwidth-bound，释放DRAM也救不了frame，8 Gen 3 gaming已展示这种退化。若draft acceptance很低、draft model过大或target没有成熟speculation，preemption会丢大量工作并多占0.86 GB。若120 Hz rendering burst比一个draft subgraph更短，reactive detection仍可能错过deadline；verify阶段5–8 ms的atomic subgraph更无法即时停。若persistent gaming让token bucket耗尽，fail-safe会回退到uncontrolled speculation，foreground保护不是hard guarantee。

### 实验可信度

30个真实app、两代商用手机、jank/slow rendering、physical PMU、throughput、request latency、energy、sporadic trace和component ablation覆盖较完整；每点15个prompt并trim extrema也比单次测试可靠。局限是只有Snapdragon做实机共跑，Dimensity/Exynos只是公开source推断；操作脚本约1–2 Hz，不是真实用户arrival；没有error bar或jank p99；target/draft只测dense Llama W4A16。所谓lossless正确性来自“target verifies candidates”的算法推理，论文没有输出bitwise/quality regression实验。

### 系统性缺陷

Sereno需为每个model/SoC导出许多layer-level draft与不同batch verify graphs，并维护KV/in-flight状态，prototype已增加6.4K C++和19%内存。per-subgraph baseline、PI gains、policy threshold及token bucket都需校准，DVFS、thermal、OS update或compiler重排可能导致drift。它只管理自己的LLM，多个background models或其他NPU clients如何协调未讨论。没有crash/cancel、battery temperature、foreground priority inversion或恶意app触发throttling测试；也没有与vendor提供真正NPU bandwidth quota的未来hardware control做实测对比。

## 局限与后续工作

- 在Dimensity、Exynos、Apple/Qualcomm tablet与AI PC上实测，而非只用kernel/device-tree佐证，并覆盖多个NPU clients。
- 对不同draft大小、acceptance、[[MoE|MoE]]/SSM/hybrid architecture和quantization扫参，量化可获得的yield granularity与内存成本。
- 报告每帧deadline miss、jank burst length与p95/p99，并使用真实touch/scroll/game traces评估reactive delay。
- 测baseline calibration在thermal、DVFS、系统升级和长时间运行下的drift，加入在线recalibration与错误检测。
- 与硬件MPAM/NPU quota、deadline-awareframe scheduler及cooperative multi-client controller比较QoS、energy和复杂度。
- 对token-bucket fail-safe构造persistent contention，明确background liveness与foreground hard SLO不可同时满足时的policy。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[Memory-Bandwidth]]、[[Quality-of-Service]]、[[Unified-Memory]]
- **同会议**：[[OSDI-2026]]
