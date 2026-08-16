---
type: paper
name: qTPU
full_title: "qTPU: Hybrid Tensor Networks for Quantum-Classical Acceleration"
authors: [Nathaniel Tornow, Emmanouil Giortamis, Dennis Sprokholt, Christian B. Mendl, Pramod Bhatotia]
venue: OSDI
year: 2026
tags: [quantum-computing, tensor-network, compiler, heterogeneous-computing]
source_pdf: "[[osdi26-tornow.pdf]]"
source_md: "[[osdi26-tornow]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# qTPU：用混合张量网络统一量子—经典加速（OSDI 2026）

> **原题**：qTPU: Hybrid Tensor Networks for Quantum-Classical Acceleration

> **一句话总结**：qTPU观察到quantum circuit与classical linear algebra都能写成[[Tensor-Network|张量网络]]，于是用hybrid Tensor Network（hTN）把整个quantum-classical workflow表示为一张图，再由compiler在quantum error与classical FLOPs之间选Pareto点、runtime切片到QPU/GPU；VQE-SU2编译最高快53.4倍，IBM Marrakesh的80-qubit QNN fidelity从monolithic baseline约0.003提高到0.12，但多QPU扩展和巨大end-to-end speedup主要使用估算QPU时间，不是真实16-QPU集群测量。

## 问题与动机

QPU适合表示classical memory会指数增长的highly entangled state，却有qubit少、gate noisy、throughput低等限制；GPU/TPU擅长高吞吐linear algebra，却无法有效表示某些量子态。现实算法因此常分两阶段：先运行一族结构相近的quantum circuits得到measurement，再用classical tensor operation组合结果。hybrid ML、circuit knitting和quantum error mitigation（QEM）都符合这个模式（§2.2–§2.3）。

现有host–kernel workflow要求程序员先决定quantum/classical boundary，分别写QPU kernel、GPU kernel和host orchestration。compiler只看到两个black box，不能把quantum circuit的一部分改成classical contraction，也不能在device数量或noise变化时重新partition。circuit cutting与QEM工具还会显式枚举大量circuit variants，导致compile、code generation和postprocessing先于真正QPU执行爆炸（§1、§2.4、Listing 1）。

qTPU的核心主张不是“经典或量子单独更快”，而是找一个共同IR。任意quantum gate可表示为tensor，wire是shared index，执行circuit等价于contract tensor network；classical framework本来就用einsum描述linear algebra。hTN在同一张graph中放quantum tensor（qTensor）和classical tensor（cTensor），先让QPU materialize qTensor结果，再做classical contraction（§3、图 2–3）。

这个统一有明确边界：论文处理可写成circuit family加linear combination/contraction的workflow。training loop、nonlinear update、data-dependent branch和中途measurement feedback仍可能留在hTN之外。hTN还压缩**程序表示**，并不会免费消除最终需要执行的shots、subcircuits或classical reconstruction。

## 关键观察 / 隐含假设

- **观察 1：quantum circuit和classical tensor program共享einsum/TN语义。** gate是rank-`2k` tensor，qubit wire对应contracted index（§3.1、图 2）。
  - **依赖假设**：目标hybrid computation主要是linear-algebraic；难以tensorize的control flow、stateful service或adaptive circuit会削弱统一表示。
- **观察 2：一族相似circuits不必逐个生成代码。** `iswitch`用symbolic index选择input encoding、observable或gate variant，一个parametric qTensor即可表示整族（§5、Listing 2）。
  - **可能失效场景**：variant结构差异很大或需要data-dependent topology时，共享kernel和compact index map的效果会下降。
- **观察 3：cut大circuit会同时减少单次quantum error、增加classical work。** spatial gate virtualization和temporal wire cutting把大qTensor改写为多个小qTensor加cTensor coefficients（§6.2–§6.4、图 6）。
  - **关键边界**：论文明确报告，在**相同classical cost**下qTPU与QAC solution quality相同；1.5–7.2倍error reduction来自qTPU提供并选择了投入更多classical work的Pareto points，不是无成本质量提升（§8.4、图 9）。
- **观察 4：qTensor instances彼此独立，适合map–reduce。** runtime按index切片，QPU并行materialize结果，classical engine再reduce（§7、图 8）。
  - **依赖假设**：有足够多QPU可用，queue/calibration/network不会成为主瓶颈；evaluation的大规模multi-QPU数字来自runtime model/estimated QPU time。
- **假设 1：gate-independent error approximation足够指导partition。** 默认把single-/two-qubit gate error设为`10^-3`/`10^-2`，qTensor error是“至少一gate出错”的近似，总quantum cost取所有qTensor的maximum（§6.2、§8.3）。
  - **证据强度**：中。IBM Marrakesh上一个QNN observable验证趋势，但model未表达correlated noise、crosstalk、routing、readout、shot variance或device drift。
- **假设 2：classical FLOPs能代表hybrid代价。** Pareto model不直接计memory traffic、intermediate tensor size、network、QPU queue、总shots与总subcircuit count。
  - **证据强度**：弱到中。被测workload中QPU time占75%–100%，但这是用estimated QPU schedule得到，其他deployment可能由data movement或queue主导。

## 核心方法

### qTensor、`iswitch` 与 `hEinsum`

qTensor是一族带symbolic indices的quantum kernels。程序员在Qiskit circuit中写`iswitch(index, operations, qubits)`：给定某个index value，runtime选择对应gate/observable/input encoding。多个index的笛卡尔积定义完整circuit family；执行后，每个index assignment的measurement填入一个result cTensor（§5.1、Listing 2）。

`hEinsum`沿用普通einsum字符串，同时接收cTensor和qTensor。语义很简单：先执行每个qTensor得到classical result tensor，再按指定indices做einsum contraction。hybrid ML例子只用两个`iswitch`描述batch input和observables，再用`hEinsum("jk,ik->ij", V, quantum_layer(...))`接classical linear layer，不再手写circuits list、QPU dispatch和result stitching（§3.2、§5.2–§5.3、图 3）。

### 统一 IR 与双目标 compiler

frontend把每个qTensor变成含temporal/spatial edges的circuit graph，再把整个hEinsum变成operation DAG。classical cost是各contraction涉及index sizes乘积所得FLOPs之和；quantum cost用independent gate-error product估计每个qTensor至少一次error的概率，并取最坏qTensor（§6.1–§6.2）。用户还可限制每个qTensor的max qubits、max error和classical FLOPs。

compiler有三类semantic-preserving rewrite。tensorization把只差少量结构的多个hEinsum合成coefficients cTensor加indexed qTensor；若subcircuits作用在disjoint qubit sets，再decompose成多个小qTensor。spatial separation切two-qubit gate，temporal separation切wire/time，把原circuit写成多种小circuit结果的linear combination（§6.3、图 6）。

optimizer从整个qTensor开始，用KaHyPar递归hypergraph partition；优先split estimated quantum cost最高的partition，并根据cut edge选择spatial/temporal rewrite。每次cut通常降低单qTensor error、增加classical contraction。系统对partition count和balance/cut weight做randomized multi-start，保留Pareto frontier，再选距“理论最优点”最近且满足constraints的方案。所谓理论最优距离如何对应用户实际dollar/latency utility并不充分说明（§6.4、图 5、图 7）。

backend把operation graph变成每个node两个operands的contraction order，并为每个unique qTensor生成一个带parameters/if–else的CUDA-Q kernel；classical graph交给cotengra/[[PyTorch|PyTorch]]（§6.5、§8.1）。

### 资源自适应运行时

runtime先沿qTensor相邻index切片，直到独立qTensor instances至少等于QPU数；device placer对QPU做load-balanced assignment，classical slices则round-robin到classical accelerators。JIT codegen调用native toolchain。执行时qTensor engine并行运行circuits并填result cTensor，cTensor engine异步等待输入、在GPU做slice-local contraction，最后reduce partial outputs（§7.1–§7.3、图 8）。

论文还描述failure handling：QPU每日约一小时calibration前完成in-flight circuit，把pending instances转到其他QPU；classical accelerator失败只重跑受影响slice，因为输入保留在host memory（§7.4）。这些是design描述，evaluation没有calibration、device crash或recovery injection。

## 设计取舍

- **统一hTN换表达范围**：cross-boundary compiler能看全图；只有tensorizable、主要线性的workflow最自然。
- **symbolic qTensor换生成规模**：compile一次parametric kernel；实际需要的circuit executions/shots仍需完成，不能把code compression当成quantum-work消失。
- **cut circuit换fidelity**：subcircuits更小、更浅、单次error低；variant数量、shots和classical reconstruction可能急增。
- **Pareto frontier换单一答案**：用户能选error/cost；默认“离理论最优最近”隐含两维normalization和utility，不一定对应SLO或预算。
- **simple error model换compile speed**：VQE-SU2到140q仍约1–3 s；真实calibration、routing和correlated error下选点可能变化。
- **FLOPs换可搜索cost model**：便于比较contraction；忽略memory、network、queue、cloud pricing和total QPU invocation。
- **index slicing换多QPU parallelism**：independent work接近linear scaling；需要很多可同时访问的QPU，且简单placer不感知heterogeneous fidelity/queue。
- **host-resident inputs换局部retry**：classical failure只重跑slice；host memory/control plane成为可用性与容量中心。

## 实验与结果

- **平台、benchmark与口径**：prototype是Python，使用Qiskit、KaHyPar 1.3、cotengra、CUDA-Q和PyTorch。classical host为双AMD EPYC 9654（192 physical/384 logical cores）、1.5 TB RAM、NVIDIA A40 48 GB。benchmarks为MQT Bench的QNN、W-State、VQE-SU2、Dist-VQE；baselines按case分别是QAC circuit cutting、Mitiq QEM、manual Batch和A40上的cuTensorNet。默认error model为single-/two-qubit gate `10^-3`/`10^-2`。除Figure 11真实IBM Marrakesh外，QPU time由Qiskit optimization level 3、1000 shots的scheduled duration估算；作者只用job metadata验证monolithic estimate误差在±2%（§8.1–§8.3）。
- **compiler tradeoff与速度**：100q circuit切成50q subcircuits时，qTPU中等classical投入相对QAC估算error低1.5–3.4倍，最大投入低2.2–7.2倍；但相同classical cost下两者quality相同。VQE-SU2从20q到140q，qTPU compile为0.76→2.51 s，QAC为1.2→134.1 s，140q快53.4倍。规模实验的error improvement因benchmark而异，为2–26倍（§8.4、图 9–10、表 1）。
- **真实QPU validation**：IBM Marrakesh上跑10–80q QNN，qTPU切为10q subcircuits，baseline跑monolithic circuit。20q baseline fidelity约0.53；80q降到约0.003，qTPU在80q仍约0.12，论文报告46倍改善。Pauli noise simulation延伸到150q也保持0.12。80q Pareto sweep中，classical cost从0加到约5.1K FLOPs，error从0.997降到0.522（§8.4、图 11）。比较没有固定总QPU invocation/shot budget，因此更高fidelity也可能使用更多quantum sampling。
- **runtime与扩展**：把40–100q circuit限制到不超过15q qTensor时，100q的estimated QPU execution占总时间75%–100%，compile约2–3 s、classical contraction少于0.01%。把逻辑QPU数从1增到16，W-State最高14.4倍、约90% efficiency；这不是16台真实QPU集群测量。100q Dist-VQE上，qTPU假设4个QPU、每subcircuit 1000 shots，并与A40 cuTensorNet真实wall time比较；cluster超过18q后模型预测qTPU更快，19q为6.7倍（§8.5、图 12）。硬件可获得性、queue与network未计入。
- **hybrid ML与10q circuit knitting**：20–100q、batch 50/100/200的QNN中，qTPU compile相对manual Batch平均快3.7倍、最高6倍；100q batch从10增到200时为4.8→16.9 s，对方3.1→63.5 s。code平均少33倍、最高48倍；100q/batch200为132K对5.1M LoC。另一个QNN cutting中，qTPU到80q仍少于30 s；图 13显示QAC 50q尚完成，60q起触发20 min timeout（正文“beyond 40”与图/caption不一致）。qTPU生成subcircuits少10–42倍，postprocessing约`10^2`–`10^3` FLOPs，对方到`10^6`（§8.6–§8.7、图 13–14）。
- **QEM与组合pipeline的symbolic compression**：对含200个single-qubit gates的QNN，Mitiq显式生成100–10K samples，compile从约335 ms到35 s；qTPU以一个qTensor表示PEC+Pauli twirling+ZNE选择空间，保持约10 ms，10K samples时约快3,550倍，generated code约3.7K LoC对13.5M，少约3,700倍（§8.8、图 15）。在20–60q QNN同时做10q circuit cutting、三档Richardson ZNE和batch20 ML时，50q的qTPU/QAC+Mitiq+Batch baseline end-to-end time约`5.8×10^3`/`1.7×10^7` s，subcircuits为48K/140M，kernel code为23K/16.7B LoC，分别少约3,000/3,000/700,000倍；60q baseline generation超时并用projection（§8.9、图 16）。`4^200`只是可索引configuration space的symbolic容量，时间又主要来自estimated QPU execution，并非实际执行`10^120`个circuits或约197天baseline；最可信的是generation-count差异，不是production wall-clock。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| hTN能压缩并统一三类hybrid workflow | ML、circuit cutting、QEM都降到qTensor+hEinsum；生成code最多少约700K倍（§8.6–§8.9） | 主要是linear/tensorizable workflow；code size不等于execution work | 中到强 |
| compiler能显式交换quantum error与classical cost | 100q四类circuit形成Pareto frontier，最大估算error reduction 2.2–7.2倍（图 9） | default independent-noise model；等classical cost与QAC quality相同 | 中 |
| qTPU compiler比显式枚举更能扩展 | VQE-SU2 140q为2.51 s对134.1 s；QEM 10K samples约10 ms对35 s（表 1、图 15） | QAC/Mitiq各自case；Python prototype和特定parameter range | 强（生成阶段） |
| circuit partition可在真实QPU提高observable fidelity | IBM Marrakesh 80q约0.12对monolithic约0.003（图 11a） | 单device、QNN/observable；未固定总shots/QPU work | 中到强 |
| runtime可近线性利用多QPU | 16 logical QPU下W-State speedup 14.4倍（图 12b） | estimated QPU time，未在真实16-QPU network/queue上部署 | 中偏弱 |

## 批判性分析

### 论证链条

论文从“host–kernel boundary阻止全局优化”出发，用TN等价性建立共同IR，再把programming model、compiler和runtime逐层实现，结构完整。最强证据是symbolic representation避免重复生成：Table 1、Figure 13–16都显示compile/code/subcircuit count不再随组合方式爆炸。较弱的跳步是把representation/estimate优势外推为quantum-classical acceleration：真正QPU wall-clock、queue、dollar cost和total shots大多未测，最大的3,000倍end-to-end结果是derived estimate。

### 假设压力测试

若noise有crosstalk、correlation、readout bias与time-varying calibration，`1-product` gate model和max-per-qTensor objective可能选错cut。若classical contraction中间tensor很大，FLOPs低也可能被memory/network主导。若QPU数量少、异构、排队数小时或每家API不同，round-robin/load balance不能得到Figure 12的scaling。若workflow含mid-circuit measurement、adaptive branch、nonlinear optimizer或stateful feedback，单个hEinsum不能覆盖完整program。若cut带来巨大quasiprobability/shot overhead，只看单subcircuit error会高估end-to-end statistical quality。

### 实验可信度

四种circuit family、三类application、多个专用baseline、真实IBM QPU点和artifact构成了很广的evaluation。作者也明确披露default noise model与QPU estimator，并验证monolithic schedule在job metadata上±2%。但真实hardware只验证QNN一个observable；没有confidence interval、repeated calibration day或fixed total shots。QAC comparison同时改变classical budget，真正equal-cost quality并不更好。multi-QPU、cuTensorNet crossover和end-to-end几乎都混合真实classical wall time与estimated quantum duration，未包含cloud queue/network。巨大baseline因timeout/组合计数而projection，不能当作实测speedup。

### 系统性缺陷

qTPU把整个系统押在“hybrid computation可线性tensorize”上；outside-hTN control仍需host orchestration，programming fragmentation只被缩小。compiler的Pareto选择没有用户SLO、price或sampling-error utility；“距理论最优最近”可能没有deployment意义。device placer不知道每台QPU topology、fidelity、calibration和queue，fault-tolerance也只有独立slice retry描述，没有exactly-once result、partial shot loss或device failure实验。symbolic kernel将code-size explosion变成runtime index/shot schedule，physical execution成本仍可能指数级。Python/Qiskit/CUDA-Q/PyTorch跨栈的versioning、compile cache、numerical reproducibility和vendor portability也未量化。

## 局限与后续工作

- 在多日IBM hardware上固定total shots、QPU invocations和dollar budget，比较Pareto points的mean/error bar、fidelity与time-to-solution。
- 把routing、readout、correlated/crosstalk noise和实时calibration加入cost model，测预测Pareto ranking与真实hardware ranking的一致率。
- 将classical FLOPs扩成memory peak、data movement、network、QPU queue、shots和price的multi-resource model，并用实际cloud账单校准。
- 在真实多QPU、跨vendor环境注入calibration、disconnect、partial result和classical accelerator failure，验证reassignment与slice retry。
- 对mid-circuit measurement、adaptive circuit和nonlinear feedback定义hTN边界，量化仍需host code的比例。
- 分别报告symbolic code generation、circuit instantiation、QPU submission、execution和reconstruction，避免把压缩表示误当作减少全部quantum work。
- 与QAC/Mitiq在equal classical cost、equal shots和equal fidelity三个口径下重做comparison。

## 相关

- **相关概念**：[[Quantum-Computing]]、[[Tensor-Network]]、[[Heterogeneous-Computing]]、[[Quantum-Error-Mitigation]]
- **同会议**：[[OSDI-2026]]
