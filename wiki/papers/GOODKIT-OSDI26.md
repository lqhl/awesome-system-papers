---
type: paper
name: GOODKIT
full_title: "Inside Out: A Paradigm Shift In Live VM Introspection"
authors: [Dufy Teguia, Louis Duval, Teo Pisenti, Kahina Lazri, Daniel Hagimont, Thomas Pasquier, Renaud Lachaize, Alain Tchana]
venue: OSDI
year: 2026
tags: [virtual-machine, introspection, security, isolation]
source_pdf: "[[osdi26-teguia.pdf]]"
source_md: "[[osdi26-teguia]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# GOODKIT：把实时虚拟机内省移到同一个 VMM 内（OSDI 2026）

> **原题**：Inside Out: A Paradigm Shift In Live VM Introspection

> **一句话总结**：GOODKIT 不再让独立 LibVMI process通过 socket反复暂停 target VM，而是在同一个 Firecracker VMM中把observer作为单独VM启动，并把获准的target memory直接映射给它；observer加入target kernel自己的lock protocol保证局部一致性，单observer让14种target workload最多慢1.06倍，但observer仍能因错误写入或持锁而破坏target，RCU与crash-held-lock recovery也尚未实现。

## 问题与动机

实时虚拟机内省（live VM introspection，LVMI）要在VM运行时查看process、credential、runqueue、disk I/O等内部状态，用于rootkit/ransomware detection、liveness monitoring和performance analysis。一个可部署的framework需要同时满足：看得足够多、observer与target/VMM隔离、读到一致状态、target overhead低、每个tenant可独立计费，并且不修改cloud hypervisor（§1、§3.1）。

现有placement很难兼得这些目标。[[LibVMI]]/KVMI把observer放在另一个VMM/process中，隔离和accounting清楚，但常暂停所有target vCPU获得一致snapshot；每次memory operation还经过socket、user/kernel crossing和copy。把observer直接编进VMM速度快，却让不可信monitor code获得VMM权限。in-guest agent有native semantics，却会和被攻陷target一起失守（§2.3–§2.4）。

GOODKIT抓住一个已有事实：target RAM本来就是VMM userspace中的host virtual address（HVA）mapping。VMM可以为另一个observer VM建立独立EPT，同时把target的某些host pages注册为observer的guest-physical memory。observer仍是KVM眼中的普通VM，却能用普通load/store直接读target；VMM再提供VM-exit/I/O probe，补足memory之外的事件（§2.1、§3.4、图 1）。

论文的安全目标需要谨慎解释。VMM和hypervisor在TCB内，假设正确且未被攻陷；target可完全compromised。observer对cloud provider是不可信普通VM，因此不能破坏**其他**VM或VMM；但论文明确承认，observer为获取target lock会得到部分write mapping，恶意或faulty observer可能改lock/target state、让target服务中断，也可以向自己的tenant撒谎（§3.2）。因此“strong isolation”不等于observer对target无伤害。

## 关键观察 / 隐含假设

- **观察 1：同一个VMM可以让两个VM共享选定physical pages，同时保留各自EPT。** observer不需要LibVMI socket逐次复制memory（§3.4、§4.3）。
  - **依赖假设**：cloud deployment允许修改和信任VMM，并接受target与observer由同一VMM process管理；confidential VM的encrypted/private memory会破坏直接共享。
- **观察 2：一致内省不一定要暂停整台VM。** 多数Linux kernel structure已有spinlock、RWLock或mutex；observer作为额外contender取得同一把lock，可只阻塞相关critical section（§4.5）。
  - **可能失效场景**：RCU、lock-free structure、跨多把lock的global invariant，或observer不知道正确lock order时，局部加锁不能给出一致snapshot。
- **观察 3：kernel address translation可按memory region优化。** text/direct-map只做offset arithmetic，vmalloc/vmemmap才page-table walk，所以实测转换为45–85 ns（§4.4、§5.3）。
  - **依赖假设**：observer掌握target kernel symbol、layout、types和allocation semantics；prototype还让target/observer运行同一kernel image。
- **观察 4：多个observer会重复遍历同一structure，并共同争用target lock。** 紧循环扫描process list时，第二个reader observer就可能让target writer starvation（§4.7、§5.7）。
  - **设计回应**：mutualizer只遍历一次、短暂释放lock，再把结果分发给各observer。
- **假设 1：VMM-side policy配置正确且足够收窄共享区域。** YAML规定memory region/permission、API functions、kernel symbols和probes（§4.2）。
  - **证据强度**：弱到中。memory slot与probe限制由VMM执行较强，但GKMODULE ACL在observer内部；论文自己称部分控制只是guideline，而且无policy时默认permissive。
- **假设 2：observer不会在target lock内crash或永久占锁。** 当前系统没有自动恢复（§7.1）。
  - **证据强度**：弱。论文只提出未来让VMM记lock map、重启recovery observer释放锁，没有实现或fault injection。

## 核心方法

### 同 VMM 的多 guest 架构

GKBUILDER在修改后的 [[Firecracker]] 中启动target与一个或多个Linux observer。VMM先分配一段连续HVA，布局为observer private memory加target memory；再为每个VM配置独立KVM memory slots/EPT。observer的guest-physical space同时包含自己的core memory和manifest允许的target pages。x86约3.25 GB MMIO hole会让target mapping需要1–3个slot，具体取决于observer/target尺寸（§3.4、§4.3、附录C）。

observer kernel中的GKMODULE提供低层API：遍历list/red-black tree、TGVA→TGPA→OGVA address translation、lock/unlock、raw memory access、symbol lookup和与VMM通信。userspace LIBGK在其上提供process/module/VMA listing和kernel-hook check等高层操作。prototype给observer target symbol table，并针对Linux七类kernel region选择offset、page-table walk或lookup方法（§4.1、§4.4、表 1）。

GKBUILDER/GKPROBE共向Firecracker加入3,803行Rust（约原codebase的5.1%）；observer侧GKMODULE为4,480行C，LIBGK为1,039行C。prototype只实现Intel x86-64、Linux target/observer，并用相同Linux 5.10.198 image简化types/layout匹配（§4、§5）。

### 远程加入 target 的锁协议

GOODKIT不暂停所有vCPU，而是让observer仿佛target kernel thread一样取得保护目标structure的lock。对queued spinlock，它借用target vCPU0的per-CPU `qnodes`，把observer视为额外nested context加入MCS queue；对RWLock使用同一queued mechanism；对mutex则让target CPU0 idle task充当owner，因为idle task不会参加普通service execution（§4.5、附录D）。read-only/`const` object可直接读。

这能提供被单把lock保护的数据结构一致性，却会真实参与target arbitration。observer持lock越久，target更新越慢；错误顺序可deadlock。Linux常用的[[Read-Copy-Update|RCU]]尚不支持：外部observer不在target CPU的grace-period protocol中，writer不知道它何时结束read-side section（§6–§7.2）。

### VMM probe 与四类 policy

memory不能暴露VirtIO request、VM exit或hypervisor event。GKPROBE因此运行在VMM内：已有KVM能力用`ioctl()`，VirtIO event则hook现有VMM path。observer通过virtqueue、hypercall和interrupt异步交换batched message。ransomware case只转发request type、sector、size、disk ID等metadata，不复制payload（§4.6）。

manifest从四个轴限制observer：GKBUILDER用memory slots强制read/write region；GKPROBE限制可启用probe及可读字段；GKMODULE ACL限制API；symbol whitelist限制lookup。第三方observer可把低层请求交给trusted mutualizer代执行/过滤。不过observer若直接获得lock所在page的write permission，framework不能阻止它写同page的其他data，论文未展示page内更细保护（§3.2、§4.2）。

### mutualizer 共享内省

每个client observer有request/completion ring。mutualizer按data-structure type合并请求，每类开一个worker：取得target lock，按固定batch遍历，处理同类新请求，再释放lock并sleep；论文实验选择约20 µs pause，在response latency与writer机会之间折中（§4.7、图 2）。这个设计既去重，也把第三方observer的policy check集中到一个trusted path，但mutualizer成为shared bottleneck和fault domain。

## 设计取舍

- **同VMM映射换native-speed access**：省掉socket/copy/hypercall；VMM配置错误会直接暴露target pages。
- **独立observer VM换accounting与VMM隔离**：observer CPU/RAM可单独计量，malicious code不能直接进入VMM；启动每个完整Linux guest仍有memory和boot cost。
- **target lock换细粒度一致性**：避免global pause；observer会与业务争lock，并能因crash、starvation或wrong order拖死target。
- **预知kernel layout换低translation cost**：direct-map只做算术；kernel upgrade、custom config、KASLR/type变化和rootkit欺骗都增加维护成本。
- **VMM probe换hypervisor不改动**：部署边界更现实；cloud provider仍要维护约3.8K LoC Firecracker fork和每种event hook。
- **mutualizer换多observer可用性**：避免reader starvation与重复scan；多tenant共享结果需要freshness、fairness、confidentiality和failure isolation。
- **permissive fallback换易试用**：manifest缺失也能运行；生产中一个配置遗漏会让observer拥有过宽能力。

## 实验与结果

- **平台与baseline**：host为16-core Intel Xeon Silver 4215 2.50 GHz、256 GB RAM、Ubuntu 20.04/Linux 5.4.24+；target/observer均为Alpine Linux 5.10.198，VMM是Firecracker 1.5，除特别说明每VM 1 vCPU。baseline是LibVMI+KVMI v7；作者将LibVMI port到Firecracker，并确认其slowdown与QEMU版近似。LibVMI本身需要KVMI hypervisor extension，而GOODKIT只改VMM/guest（§5.1、附录E）。
- **功能覆盖、原型准确率与代码量**：observer services共七类：四个open-source rootkit detector、DefPunk-like ransomware detector、MySQL liveness monitor和CPU runqueue monitor；另有P1–P9 micro policies。四个rootkit均被发现。重训的linear-SVM ransomware model在RanSAP上F1为0.76，对所测benign workload无alarm、每个ransomware sample至少报一次；这验证framework能承载policy，不是新的detector accuracy贡献。Table 3中GOODKIT policy code相对LibVMI短1.6–7.8倍，正文概括为3–6倍。论文所谓“21 use cases”把14个target-side Phoronix applications与七个observer services相加，不是21种独立security detector（§5.1–§5.3、表 2–3）。
- **单次内省与捕获率**：TGVA translation为45–85 ns；无争用spinlock/RWLock/mutex为29/26/36 ns。相比LibVMI，单纯lock/unlock对pause/resume快17倍，完整P1–P9 turnaround最高快110倍。credential cat-and-mouse中，GOODKIT在0–500 modifications/s范围保持约99% capture；LibVMI超过150/s降到约50%，200/s只有0.16%。图外的10 million modifications/s下GOODKIT才降到80%（§5.3–§5.5、图 3–4）。
- **target运行与I/O overhead**：target改为14 vCPU、observer各1 vCPU，在14种Phoronix workload上，单P3 GOODKIT observer最大slowdown 1.06倍；LibVMI为5.15–37.6倍。四个异构GOODKIT observer并行时平均约1.16倍，但LibVMI不支持独立multi-observer，所以没有对应baseline。DefPunk trace GOODKIT与vanilla均约874 IOPS，LibVMI为747 IOPS；FIO-IOPS上LibVMI slowdown达1.87倍（§5.6.2、图 5）。
- **boot与部署成本**：observer和target并行启动时，一个observer令target boot变成1.08–1.11倍，五个为1.57倍；先完整启动observer再target约2倍。target建好后再启动observer只让target boot增加1.02–1.04倍，且不随observer数增长，但monitor真正可用时间会更晚（§5.6.1）。论文未给每个Linux observer的steady-state RAM、VMM RSS、billing accuracy或大规模density。
- **mutualizer消融**：target持续create/join thread、observer紧循环读process list。没有mutualizer时，超过一个observer便让target writer starvation并freeze；有mutualizer后，target稳定约35K thread creations/s，observer各约38K iterations/s，数量增加时近似不变；vanilla target约40K/s，单observer无mutualizer也有相近performance（§5.7）。这证明mutualizer是该压力场景的correctness必需项，也暴露direct lock-sharing本身可造成严重DoS。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 同VMM direct mapping显著降低LVMI成本 | P1–P9 turnaround相对LibVMI最高快110倍（图 3） | 单socket、相同kernel image、idle 1-vCPU target；baseline靠pause | 强（原型内） |
| fine-grained lock比global pause少干扰target | 14种Phoronix上GOODKIT最多1.06倍，LibVMI为5.15–37.6倍（图 5） | 单P3 observer；不覆盖RCU、contended multi-lock snapshot | 强（被测policy） |
| GOODKIT能跟上快速变化state | 500 modifications/s仍约99% capture，10M/s约80%（图 4、§5.5） | 单credential corruption microbenchmark；capture不等于完整attack detection | 中到强 |
| mutualizer让重复monitoring可扩展 | 无mutualizer时两个reader使target freeze；有则target约35K/s（§5.7） | 单process-list RWLock workload；未测数十tenant/fairness | 强（该场景） |
| observer VM提供VMM/其他VM隔离 | 独立EPT和普通KVM guest boundary（§3.2–§3.4） | observer仍可破坏获准target region或永久持lock；无恶意测试 | 中 |

## 批判性分析

### 论证链条

论文先比较out-of-VMM、in-VMM和in-target三种placement，再利用“RAM已在VMM HVA”找到一个有新意的中间点；direct mapping解释speed，target lock解释consistency，mutualizer补上multi-observer contention，逻辑基本闭合。最重要的claim gap在isolation：独立VM确实隔离observer与VMM/其他tenant，但observer为了内省target得到read甚至write mapping。论文threat model直接承认它可破坏target，因此不能把“VM-level isolation”扩写成target fault isolation已经实现。

### 假设压力测试

若target/observer kernel版本、config或data layout不同，symbol+hard-coded region translation会失效；clever rootkit还可故意伪造observer依赖的semantic invariant。若structure由RCU保护，当前GOODKIT无法加入grace period。若一个operation需要按顺序取得多把lock，observer必须完整复刻target discipline，否则可能deadlock。若target memory由SEV-SNP/TDX等confidential-computing机制保护，cloud VMM不能按当前方式把plaintext page映射给observer。若observercrash时持lock，target可能一直stall。

### 实验可信度

实验同时覆盖micro latency、capture race、14种macro workload、I/O probe、boot和mutualizer ablation，LibVMI Firecracker port也与QEMU交叉验证，证据比单benchmark完整。限制是所有VM同一Linux 5.10.198、单x86 host/Firecracker版本；P3对LibVMI的5.15–37.6倍主要来自高频global pause，未比较其他non-pausing LVMI。四observer没有LibVMI baseline。所谓21 cases包含14种target performance benchmark，不能当作21种policy diversity。没有error bar、长期运行、observer memory accounting、malicious observer或crash injection。

### 系统性缺陷

framework把semantic gap和synchronization责任交给policy author，而不是消除它。每次kernel update都可能改变symbols、types、locks、RCU use和per-CPU layout。GKMODULE内ACL在malicious observer自己的kernel里不是可信barrier；安全必须依赖VMM memory slots、GKPROBE和mutualizer，page-granularity又可能给出超出单个lock variable的write scope。mutualizer解决reader starvation，却成为共享服务，论文未处理它crash、慢client、tenant data leakage或公平排队。VMM fork、guest module和observer images的版本管理/attestation也没有设计。最严重的是fault recovery只停留在future-work草案：observer持target lock后crash，当前prototype无法可靠释放。

## 局限与后续工作

- 实现VMM-side held-lock journal和recovery observer，对每种lock在acquire/release任意指令处crash，测target最大stall和恢复正确性。
- 为RCU reader/writer设计跨VM grace-period protocol，并用concurrent reclamation stress验证不存在use-after-free。
- 在不同Linux版本/config/KASLR/BTF组合上自动恢复types、symbols和locks，报告porting时间与false translation rate。
- 把write permission从整page收窄到可验证lock operation，或由trusted proxy执行；fuzz恶意observer对target、VMM和其他VM的隔离边界。
- 扩到数十observer/target，测mutualizer吞吐、p99 freshness、fairness、per-tenant accounting、memory overhead和crash propagation。
- 明确confidential VM下的可行性；若不能共享plaintext memory，量化RPC/attested helper退化路径。
- 将默认配置改为deny-by-default，并验证manifest、symbol whitelist、probe fields和target mapping的policy audit工具。

## 相关

- **相关概念**：[[Virtual-Machine-Introspection]]、[[Trusted-Computing-Base]]、[[Read-Copy-Update]]
- **相关系统**：[[LibVMI]]、[[Firecracker]]、[[KVM]]
- **同会议**：[[OSDI-2026]]
