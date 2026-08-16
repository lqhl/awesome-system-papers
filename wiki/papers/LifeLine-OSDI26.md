---
type: paper
name: LifeLine
full_title: "LifeLine: An Object-Page Lifetime Alignment GC Enabling Minimal Memory Copying for Mobile Devices"
authors: [Jiacheng Huang, Yunmo Zhang, Qingan Li, Junqiao Qiu, Chun Jason Xue]
venue: OSDI
year: 2026
tags: [garbage-collection, android, memory-management, page-remapping, mobile-systems]
source_pdf: "[[osdi26-huang-jiacheng.pdf]]"
source_md: "[[osdi26-huang-jiacheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# LifeLine：让对象与内存页共同存亡的 Android GC（OSDI 2026）

> **原题**：LifeLine: An Object-Page Lifetime Alignment GC Enabling Minimal Memory Copying for Mobile Devices

> **一句话总结**：Android CMC 已能通过 OS remap 整页，但一页内对象寿命混杂时仍要逐对象复制；LifeLine 用 reference-field mutability 近似共同存亡关系，把 object graph 切成 subgraph 并按 subgraph 重排 mature heap，让每页趋近“几乎全活或几乎全死”，在 Pixel 7 Pro 的商业应用滚动 workload 中把每次 GC copy volume 从 61.9 MB 降到 26.4 MB、GC duration 从 198 ms 降到 153 ms。

## 问题与动机

Android Runtime（ART）的 [[Garbage-Collection|垃圾回收]]需要标记 live object、压紧 heap，再回收空闲空间。现代默认 Concurrent Mark-Compact（CMC）尽量并发执行：应用访问尚未处理的 to-space page 时触发 SIGBUS，fault handler 再移动该 page 上的 live object。传统办法是 `memcpy` 每个对象；新 Linux 可以用 `userfaultfd` 的 `UFFDIO_MOVE` 只改 page-table entry，把整张 physical page 从 from-space remap 到 to-space（§2、图 1）。

整页 remap 只有在 page 几乎全活时划算。一张 4 KB page 若同时有许多 live/dead small object，整页保留会带走垃圾，整页丢弃又会误删 live object，collector 仍只能复制 survivor。Generational GC 只粗分 young/mature；mature generation 内的对象仍可能在完全不同阶段死亡，这就是论文所说的 object–page lifetime mismatch。

这个 mismatch 在小 heap 上尤其贵。Twitter 接近 minimum heap 时，一分钟复制 3,341 MB，是 average live memory 的 80.9×；heap 放大到 140 MB 后仍复制约 10× live memory（§3.1、图 3）。GC 期间，采样到的 object-field read tail latency 约放大 60×；触发 GC work 的 read 平均约 15 µs，其中 87% 时间花在 copy（图 2）。原始 CMC heap 中，接近 100% survival、适合 remap 的 page 只占所测应用 memory 的 16.1% 和 13.5%（图 4）。

LifeLine 不试图准确预测每个 object 的死亡时间，而是问一个更容易的问题：哪些对象很可能一起存活、一起死亡？如果先把这些对象放进同一 page，下一次 GC 就能用 page remap 保留 dense page，或整页回收 dead page，只复制 sparse page 中少量 survivor。

## 关键观察 / 隐含假设

- **观察 1：Android object graph 很稀疏，incoming edge 往往决定 object lifetime。** 多数 object 的 in-degree 为 1；Instagram 中约 69% object 只有一个 incoming reference（§4、图 5）。
  - **设计含义**：可以预测 edge 两端是否共同存亡，而不为每个 object 建复杂 lifetime model。
  - **可能失效场景**：global registry、listener、cache 或 native root 让 graph 多 owner、隐式 owner 很多时，一个 edge 不足以解释 lifetime。
- **观察 2：Reference 是否反复改变，与两端 lifetime gap 强相关。** Amazon Shopping 先 warm 30 s，再观察 38 s；unchanged edge 两端大多接近同时死亡，changed edge 两端常相差接近整个观察窗口（§4、图 6）。
  - **设计含义**：把 mutable edge 当作 subgraph boundary，把 stable edge 连接的 object 放在一起。
  - **证据边界**：精细 lifetime-gap study 主要是一款应用和几十秒窗口；其他应用只补充 degree/mutation prevalence，不能证明所有 phase 都稳定。
- **观察 3：Mutable reference 是少数，可以近似跟踪。** 所测 app 中，reference field 从未改变的 object 明显多于发生改变的 object（图 7）。
  - **设计含义**：用 sampled write barrier 和 layered [[Bloom-Filter|Bloom filter]] 记录少数高频 mutation，不需要 per-object exact counter。
- **观察 4：Prediction 不必精确，只需让 survival ratio 双峰化。** 错误 grouping 最多产生 medium-density page；normal tracing 仍决定 liveness，ZCGC 会走保守 copy path，不会回收 live object（§5.4、§6.3）。
  - **取舍**：Safety 不依赖 predictor accuracy，performance 依赖；phase change 会先损失一次 alignment/copy 成本，之后才重排。
- **观察 5：收益在 intermediate mature ratio 最大。** Amazon Shopping 中 mature object 约 65% 时，copy reduction 约 60%；超过约 80% 后，baseline CMC 本来也能 remap 大量 dense page，LifeLine 差距缩小（§6.2、图 14b）。
- **假设 1：OS 提供低成本 page move。** 评测使用 4 KB page 和 `UFFDIO_MOVE`；Pixel 7 Pro 的默认 kernel 不支持，作者移植 patch 后才启用（§6.1）。
  - **可能失效场景**：不能修改 kernel、page size/architecture 不同，或 page-table/TLB cost 高的设备。
- **假设 2：常见 app phase 内的 reference mutability 足够稳定。** 默认 workload 是每 0.4 s swipe 一次的连续 scrolling/content loading。
  - **证据强度**：中。真实 commercial app 很有价值，但没有覆盖页面切换、短 session、foreground/background、游戏或强 mutation workload。

## 核心方法

### 1. 三个 heap space 与闭环 workflow

LifeLine 在 ART generational heap 中维护 young、lifetime-unaligned mature、lifetime-aligned mature 三个逻辑 space（§5.1、图 8）。新对象先在 young，survivor 起初进入 unaligned；系统采样 reference mutation，运行 Lifetime-based Graph Partition（LGP），再用 Lifetime-Alignment GC（LAGC）把相关 subgraph 逐步搬进 aligned space。之后 Near-Zero-Copy GC（ZCGC）主要管理 aligned space。

Poorly aligned page 中的 survivor 会被 copy 回 unaligned space；新 promoted object 也先积累在那里。当 aligned space 缩小、unaligned space 增大到阈值，系统再次运行 LAGC。它不是一次性 offline profile，而是“采样→分图→对齐→观察漂移→重新对齐”的闭环。

### 2. LGP：用 sampled mutation 切 object graph

LGP 在 interpreter object-field store handler，以及 JIT/AOT compiler 生成的 write path 中插入 lightweight barrier（§5.2、图 9）。每个 thread 有 thread-local counter；默认 sampling period `M_B=100`，只有每 100 次 reference write 才进入完整 barrier，其他 write 只增加 counter（表 1）。

Barrier 用 `(object,address_offset)` hash 标识 field，并插进第一层尚未包含它的 Bloom filter。出现在越深 layer，表示采样到的 mutation 次数越多。默认三层：第 1 层 2 MB，后两层各 0.5 MB；论文测得 false-positive rate 少于 1%。达到第 3 层的 field 被判为 mutable，outgoing reference 被切断；未出现或很少出现的 field 作为 stable ownership edge 保留。

Sampling/Bloom error 不参与 liveness decision。False positive 会多切 edge，生成更小 subgraph；漏掉 mutable edge 可能把不同 lifetime object 放一起，后续 ZCGC 仍按 live marking 选择 copy，不会错误回收。代价只是 alignment opportunity 和额外 GC work。

### 3. LAGC：把 subgraph 放到 page

LAGC 在一次 mostly-concurrent marking 中边 trace、边建 subgraph metadata（§5.3、图 11）。每个 subgraph 保存 root identifier、owner 和 byte size，各 4 bytes，总计 12 bytes；5,000 个 subgraph 约 59 KB。Depth-first tracing 让同一 subgraph object 连续出现，便于计算 size 和 relocation order。

默认以 4 KB 为 large-subgraph threshold：

- large subgraph 独占一张或多张 page，从 page-aligned address 开始，按 DFS order 连续排放；
- small subgraph 沿 ownership relation 向上找 parent，greedy 聚成接近一页的 group，再从最高 owner 开始 guided traversal，把相关 sibling/descendant 连续放进同页。

LAGC 只处理 unaligned generation，可以跨多个 GC cycle 渐进迁移，而不是一次重排整个 mature heap。只 align large subgraph 的 `LifeLine (large)` 和同时 packing small subgraph 的 `LifeLine (large+small)` 都被实验比较；默认是后者（§6.1、图 13）。

### 4. ZCGC：Dense page remap，其余 page copy

Normal mark phase 已统计每页 live bytes，ZCGC 直接除以 page size 得 survival ratio，不需再次扫描 object（§5.4、图 12）。默认 page-survival threshold `T_M=90%`：

- survival 大于 90% 的 dense page 通过 `UFFDIO_MOVE` remap physical page，只改 PTE；
- low/medium page 预先计算 survivor 新地址，application fault 时只复制 live object，随后回收其余空间；这些 object 进入 unaligned generation，等待下一次 LAGC。

Alignment 理想时 medium page 很少，distribution 在约 10%/90% 两端形成跳变（图 18）。阈值来自 remap/copy cost 交点，可按 deployment cost model 调整，并不是所有 device 的固定常数。

### 5. 自适应重对齐与实现规模

ZCGC 记录第一次 alignment 后的 aligned/unaligned size。当前两者相对基线漂移超过 `Δ=30%` 时重跑 LAGC；阈值小会频繁重排，太大则长期退化到 CMC（§5.4、§6.5、表 1）。

Prototype 基于 AOSP `android-15.0.0_r3`：ART 约 2.3K C++ LOC，其中 collector 约 1.5K、LGP 约 300、heap layout 约 200；kernel 另改约 100 C LOC，涉及 userfaultfd/page migration（§6.1）。正确性仍来自 CMC marking 和 fault-based relocation；lifetime metadata 只改变 placement 和 movement choice。

## 设计取舍

- **Edge mutability 换精确 lifetime。** Tracking 很轻且错误只伤性能；stable edge 并不必然表示共同死亡，phase change 后需要重新对齐。
- **一次较贵 LAGC 换多次便宜 ZCGC。** Alignment phase metadata/placement CPU 比 CMC 高 12.5%；收益需要后续 GC 足够多，短 session 可能尚未摊平。
- **4 KB page alignment 换 object-placement freedom。** Large subgraph 独占、small subgraph greedy pack 简单可控，但可能产生 gap，也可能改变 cache locality；论文没有单独测 fragmentation/locality。
- **固定 90% threshold 换简单 planner。** Dense page 少回收一点 garbage 以避免 copy；设备 page-remap/copy cost 变化后需重调。
- **Runtime–kernel co-design 换移植成本。** 能使用真正 zero-copy page move，但 stock Pixel kernel 需要 patch，其他 Android vendor/runtime 不能直接部署。
- **低 predictor overhead 换长期 mutator tax。** 每次 reference write 都增加 thread-local counter；完整 sampling path 平均 CPU time 增加约 3.8%。

## 实验设计

Baseline 覆盖 ART production collector：Android 13 起默认的 OS-assisted CMC、较早的 Baker-barrier Concurrent Copying（CC），以及 startup 使用的 stop-the-world Semi-space（SS）。LifeLine 基于 CMC，分别测试 only-large 与 large+small alignment（§6.1）。所有 collector 在同一 patched kernel 上运行，因此 CMC 也可使用 OS assistance。

设备只有一台 Google Pixel 7 Pro：2×2.85 GHz Cortex-X1、2×2.35 GHz A78、4×1.80 GHz A55、12 GB LPDDR5、120 Hz screen，Android 15 AOSP 与 5.10 GKI。Workload 列出 Amazon Shopping、Facebook、Instagram、Spotify、LinkedIn、TikTok、Twitch、Twitter、Threads、Telegram、Line、YouTube、Google Maps。App login 后等 10 s，再用可重复脚本每 0.4 s swipe；论文承认不覆盖随机 navigation、短 session 和频繁 foreground/background。

Copy/GC duration 实验先 warm 30 s，再固定 scrolling rate，为每个 app 收集 10 次 GC，报告 mean/variance。Frame experiment 只有 Twitter/Instagram，heap cap 80 MB，约为 minimum 的 2–3×。Tail memory-access experiment 只用 Amazon Shopping，每 100 次 object read 采一个样本。真实应用和真手机很有说服力，但每项样本时间、device 和 interaction pattern 都较窄。

## 实验与结果

- **每次 GC copy volume 平均少 57.4%。** 相对 CMC，LifeLine 从 61.9 MB 降到 26.4 MB；heap 越小，差距越大。Amazon mature fraction 约 65% 时降低约 60%，超过约 80% 后 CMC 也能 remap dense page，LifeLine 相对收益下降（§6.2、图 13–14）。
- **平均 GC duration 少 22.7%。** CMC 从平均 198 ms 降到 LifeLine 153 ms；大部分应用都缩短，但 Google Maps 等 small-heap app 原本 GC 很短，absolute gain 较小（§6.2、图 15）。这是 per-GC mean，不是 pause-time P99，也不等于整段 app runtime 加速 22.7%。
- **用户可见 tail 在两个 case study 中改善。** 80 MB heap 的 Twitter/Instagram scrolling 中，CMC 在 GC interval 的 frame-time CDF 明显右移；LifeLine 缩小差距，Instagram GC interval 的 P90 frame latency 相对 CMC 低约 29%（§6.2、图 16）。论文没有报告全 workload dropped-frame rate、P99 或 battery/energy。
- **Mechanism evidence 与主结果相符。** Amazon Shopping 在 GC compaction 期间的 1-ppm memory-read tail latency 相对 CMC 低 85%；Figure 18 中 20%–80% survival page 大幅减少、CDF 在约 10%/90% 处跳变，Figure 19 的 movement 从 0–100-byte object copy 转向 4 KB page remap（§6.3、图 17–19）。
- **Auxiliary memory 少于 4 MB，CPU overhead 只在某些阶段低。** 三层 Bloom filter 共 3 MB，5,000 subgraph metadata 59 KB，总 auxiliary memory 少于 4 MB且 alignment 后释放。LGP sampled write path 平均多 3.8% CPU time，LAGC alignment phase 比 CMC 多 12.5%；稳态 ZCGC 的 GC-thread CPU time反而少 32%。3-minute Instagram run 中，LAGC 带来的平均 CPU overhead 为 2.7%（§6.4）。
- **Sensitivity 说明默认参数不是任意选择。** Bloom layer `N_B=1` 产生过多小 subgraph、LAGC 很贵；`N_B=5` 又混入不同 lifetime 并增加 tracking，默认取 3。Sampling period 默认 100，large threshold 4 KB，page survival threshold 90%，realignment `Δ=30%`；论文逐项说明过大/过小的退化方向，但没有公开每个 parameter sweep 的完整端到端数值（§6.5、表 1）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| Object–page lifetime mismatch 限制 CMC page remap | §3、图 3–4：medium-survival page 多，friendly page 仅 13.5%/16.1% | 少数 app characterization、4 KB page、Android CMC | 强 |
| Reference mutability 可近似共同 lifetime | §4、图 5–7：69% single-owner，changed/unchanged lifetime gap 分离 | 细粒度 gap study 主要是 Amazon 的 38 s window | 中 |
| LifeLine 把 page survival 变成双峰并减少 copy | 图 13、18–19：61.9→26.4 MB，movement 转为 4 KB | 单 Pixel、scripted scrolling、每 app 10 GCs | 强 |
| Copy reduction 能缩短 GC 并改善 frame tail | 图 15–17：198→153 ms，Instagram P90 少 29%，1-ppm read 少 85% | GC mean 跨 app；frame 只两 app，read 只一 app | 强到中 |
| Overhead 适合所测 mobile deployment | §6.4：少于 4 MB；3.8% LGP、12.5% LAGC phase、Instagram average 2.7% | 单 SoC/OS、3-minute case；无 energy/thermal | 中 |

## 批判性分析

### 论证链条

论文先证明 CMC 的限制不是 remap primitive 太慢，而是 page 内 live/dead object 混合；再用 object-graph sparsity 与 reference mutation 支持 subgraph heuristic。LGP 回答“谁可能一起死”，LAGC 回答“如何放到 page”，ZCGC 回答“如何安全利用 page operation”。最后，survival distribution、movement granularity、copy bytes、GC time 和 frame tail 逐层验证，因果链很完整。

最值得肯定的是 predictor 不参与 liveness：normal mark 保证 correctness，prediction error 只会让 page 走 copy fallback。论文因此不需要证明 exact lifetime prediction。不过“self-correcting”是 performance claim：错误 layout 要先产生 unaligned object、达到 `Δ`、再付一次 LAGC；phase change 的恢复时间和期间 tail 没有专门实验。

### 假设压力测试

Mutability–lifetime correlation 的核心 measurement 较窄。Amazon 的 38 s window 和连续 scrolling 可能让 view/content object 呈稳定 ownership；页面跳转、聊天、游戏、camera、WebView、background service 或 JNI/native reference 可能有不同 graph。Stable reference 也可能从 global cache 指向短命对象，mutable container 内的 item 也可能一起死亡。

收益还取决于 mature ratio 与 session length。超过约 80% mature 时 CMC 已能 remap，LifeLine 差距缩小；短 session 若只经历一次 LAGC、来不及用多轮 ZCGC 摊销，12.5% alignment overhead 可能不合算。论文没有按 app phase、session length 或 allocation rate 给出 break-even。

### 实验可信度

商业 app、真实 Pixel、CMC/CC/SS 全 production baseline、copy→GC→frame 三层 metric，以及 large-only/large+small 和 parameter analysis，明显强于 trace simulation。Baseline CMC 也运行在支持 page move 的同一 kernel，比较没有故意拿掉它的 OS assistance。

但只有一台高端 Pixel 7 Pro、一个 Android/kernel 版本和固定 swipe workload。主结果每 app 只有 warmup 后 10 个 GC；报告 mean/variance，未给 P99 pause。Frame 只测 Twitter/Instagram、memory access 只测 Amazon。没有 end-to-end app throughput、allocation rate、peak RSS、energy、thermal、battery 或长期 foreground/background trace，因此“mobile devices”不能直接外推到低端 SoC 和 vendor ROM。

### 系统性缺陷

部署需要同时维护 ART 和 kernel patch。测试 kernel 默认没有 `UFFDIO_MOVE`，作者移植后才运行；vendor kernel、security policy 或旧 device 不一定允许。约 2.3K ART C++ 与 100 kernel LOC 不算巨大，但 GC correctness、signal/userfaultfd path 和 heap layout 都是高风险代码，论文没有 fuzzing、stress/crash test 或长时间 production deployment。

Page-aware packing 还可能改变 cache locality、TLB behavior、fragmentation 和 allocation throughput。Large subgraph 独占 page、small subgraph greedy packing 的 internal gap 没有量化；remap dense page 会保留少量 dead bytes，90% threshold 是 time–space trade-off。Auxiliary memory 少于 4 MB 不等于 total heap footprint 不变，论文没有系统报告 peak/steady RSS。

## 局限与后续工作

- **局限 1**：只有 Pixel 7 Pro、Android 15 patched kernel；stock kernel 和其他 managed runtime 未验证。
- **局限 2**：交互主要是每 0.4 s scrolling，不覆盖 navigation、short session、background transition、game/WebView/JNI workload。
- **局限 3**：每 app 10 个 GC，主要报告 average duration；frame/read tail 只覆盖 2/1 个 app。
- **局限 4**：Mutability predictor 的细粒度证据主要来自 Amazon 的 38 s window；phase-change realignment latency 未测。
- **局限 5**：没有 energy、thermal、battery、total app throughput、peak RSS、fragmentation 或 cache/TLB locality。
- **局限 6**：需要 ART+kernel co-design，缺少 correctness stress、fuzzing、crash 和 production longevity 证据。
- **后续工作 1**：在低/中/高端 SoC、4/16/64 KB page 与 vendor kernel 上复测 copy、GC P50/P99、frame drop、energy 和 thermal throttling。
- **后续工作 2**：重放 navigation/background/game/WebView/JNI phase trace，记录 mutability prediction、medium-page ratio、`Δ` trigger、realignment time 和短 session break-even。
- **后续工作 3**：做 week-long allocation/GC stress，并注入 userfaultfd failure、signal race、process kill 和 memory pressure；用 heap verifier 检查 lost/duplicate reference 与 live-object corruption。
- **后续工作 4**：单独量化 exclusive/greedy packing 的 internal fragmentation、peak RSS、cache miss、TLB shootdown 和 allocation throughput。
- **后续工作 5**：在线估计 remap/copy/LAGC cost，按 device 和 app phase调整 `T_M`、`M_B`、`Δ`，与固定参数比较 JCT、jank 和 energy。

## 相关

- **相关概念**：[[Garbage-Collection]]、[[Page-Remapping]]、object lifetime、generational GC、[[Bloom-Filter]]、userfaultfd
- **相关系统**：Android Runtime、Concurrent Mark-Compact、Concurrent Copying
- **同会议**：[[OSDI-2026]]
