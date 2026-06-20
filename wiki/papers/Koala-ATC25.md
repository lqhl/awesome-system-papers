---
type: paper
name: Koala
full_title: "The Koala Benchmarks for the Shell: Characterization and Implications"
authors: [Evangelos Lamprou, Ethan Williams, Georgios Kaoukis, Zhuoxuan Zhang, Michael Greenberg, Konstantinos Kallas, Lukas Lazarek, Nikos Vasilakis]
venue: ATC
year: 2025
tags: [benchmark, shell, posix, characterization, reproducibility]
source_pdf: "[[atc2025-lamprou.pdf]]"
source_md: "[[atc2025-lamprou]]"
---

# The Koala Benchmarks for the Shell: Characterization and Implications (ATC 2025)

> **一句话总结**：观察到 shell 性能研究长期缺乏可复现的统一 benchmark（各系统各自手写 microbenchmark），且真实 shell workload 在 POSIX 语法、外部命令与 CPU/内存/I/O 维度上跨数量级多样；Koala 聚合 14 组 126 个真实程序、三档输入（full 最大 146GB）与自动化校验基础设施，在 Shark/GNU parallel/hS/PaSh 上测得 1.01–13.43× / 平均 2.6× / 1.5–4.97×（伴随机 slowdown）/ 依赖 annotation 的有限加速，并系统刻画各优化技术的适用边界。

## 问题与动机

[[POSIX-Shell]] 在 CI/CD、日志分析、生物信息学、ML glue code、系统运维等场景仍高度普遍，[[PaSh]]、Shark、hS、[[GNU-Parallel]] 等 shell 加速系统近年持续涌现。但作者 claim：**shell 领域没有公认的 performance benchmark suite**——每篇论文要么手写 microbenchmark，要么从开源仓库 ad hoc 抽取脚本，导致复现性差、baseline 不可比、结论难以外推。Shark 原论文甚至坦言「据我们所知不存在 shell benchmark，只能用自写 microbenchmark 做初步结果」。

现有选项的结构性缺陷：

- **Microbenchmark**（ShellBench、zsh-bench、UnixBench）：合成、孤立，无法支撑 whole-system 评估
- **POSIX / Smoosh 正确性测试套**：验证语义等价，不衡量真实 workload 性能
- **开源仓库 scrape**：缺输入、依赖不明、质量参差，作者难以控制选择偏差
- **用户研究语料**：偏开发者交互模式，规模与复杂度不足以代表生产 pipeline

Koala 的目标是成为 shell 性能研究的 **DaCapo / PARSEC 式基础设施**：真实程序 + 真实输入 + 自动化 setup/validation + 公开表征分析，支撑 fair comparison 与 community-wide understanding。

## 关键观察 / 隐含假设

- **观察 1**：真实 shell workload 在静态语法与动态行为上高度异质——覆盖全部 POSIX 主要 construct（pipeline、redirect、loop、subshell、`&`/`wait` 等），且 shell 解释器时间与外部命令时间占比从近似均衡到命令主导（如 bio、inference）跨度极大；CPU 时间 2.1–6544.8s、内存 6.1MB–25.1GB、I/O 85.7MB–336GB（§6，Ryzen 7 9700X + 32GB RAM + NVMe）。
  - **依赖假设**：从 14 组 curated 程序 + PCA（静态/动态特征 + LLM embedding）可代表「wild shell」的多样性；语法分布与 [[Bash-in-the-Wild]] 类研究对齐。
  - **可能失效场景**：企业内大量 [[Bash]] 函数库、容器内极简 Alpine 环境、或 [[Zsh]]/fish 主导场景未被充分覆盖；benchmark 偏 POSIX `sh`/`bash --posix`，对 bashism 密集脚本代表性有限。

- **观察 2**：不同 shell 加速技术抓住不同优化机会，单一 microbenchmark 会系统性高估或低估某类系统。以 weather 为例：Shark 2.3×、GNU parallel 2.7×、hS 1.64×、PaSh 1.08×（§2）；nlp/weather 上 Shark 可达 6.46×/13.43×，而已高度 pipeline 化的 web-search 仅 1.01×。
  - **依赖假设**：benchmark 的「whole-program + 真实输入」组合能暴露 loop 并行、I/O-bound fan-out、pipeline stage 依赖等结构，从而区分 transformation-based vs drop-in shell replacement 系统。
  - **可能失效场景**：若生产脚本以 monolithic `awk`/Python glue 为主、或依赖 cloud API/网络延迟，Koala 的本地文件处理偏向可能高估 pipeline 优化价值。

- **观察 3**：可复现 benchmark 需要输入规模分层与多层存储——full 输入可达 146GB（weather），但 min 模式在 t3.large 上约 20 分钟可跑完全套（bare metal），full 约 24 小时（Docker + 5 次重复）。
  - **依赖假设**：研究者愿意承担 400GB+ 依赖与数据的下载成本；Brown/Stevens/UCLA 副本集群 + Zenodo 归档可长期保证可用性。
  - **可能失效场景**：带宽受限环境、Zenodo 分片重建、或云存储副本全部失效时的恢复路径虽存在但运维成本高。

- **假设 1**：输出哈希校验足以保证优化系统未破坏语义；性能测量以 wall-clock + `/proc` CPU/IO 为主，不强制隔离 OS page cache 或冷启动效应。
  - **证据强度**：**中**——`validate.sh` 对每脚本做 known-good hash，但 CI/CD、pkg 等 benchmark 涉及编译/网络下载，环境漂移可能触发 false negative；论文未系统报告 flaky rate。

- **假设 2**：评估 Shark/GNU parallel 所需的手动脚本改写属于「系统 intended use」，不应算作 benchmark 缺陷；hS/PaSh 作为 drop-in replacement 应零改写运行。
  - **证据强度**：**中**——改写工作量已文档化（koala-shark、koala-parallel 仓库），但人工识别 parallelizable region 引入主观性，不同研究者可能得到不同 speedup。

## 核心方法

Koala 是面向 shell 性能研究的 **benchmark suite + harness**，而非优化系统本身。核心 artifact 包含四块：

**1. Benchmark 程序集（14 sets，126 scripts）**

覆盖数据分析（weather、covid、bio）、日志分析（analytics）、CI/CD 构建（ci-cd）、ML/NLP（ml、nlp、inference）、系统管理（repl、pkg）、经典 Unix 技巧（oneliners、unixfun、web-search）等。程序来源包括 NOAA 气温数据、Project Gutenberg、Wikipedia dump、基因组 BAM、Nginx/ZMap 日志等真实数据源。每个 set 附带 domain 标签（DA/SA/CI/ML/AN/MI 等）与 LoC/construct/command 统计。

**2. 三档输入（min / small / full）**

- `--min`：合成或种子生成，快速验证 setup 与 validator
- `--small`：通常为 full 的 0.1%–30%，语义保持有效（如基因组截断仍合法）
- `--full`：原始或按现代规模放大的真实输入

输入托管于大学副本集群（1Gb/s）+ Zenodo 永久归档（>50GB 分片）。

**3. 五脚本 harness（每 benchmark set 一套）**

`install.sh` → `fetch.sh` → `execute.sh` → `validate.sh` → `clean.sh`，由顶层 `main.sh` 驱动。关键配置：

- `KOALA_SHELL`：指向待测 shell/optimizer（bash、PaSh、hS 等）
- `--bare` vs Docker：隔离 cross-run 污染
- 默认 5 次重复聚合结果

一键入口：`curl -s up.kben.sh | sh && ./koala/main.sh --min --bare`

**4. 表征分析框架**

- **静态**：libdash + Smoosh AST 统计 construct/command 频率；与 wild shell 研究对比
- **动态**：bash `--posix` 下测 shell vs command CPU 时间、high-water memory、I/O、syscall/FD
- **多样性**：PCA 在特征空间与 OpenAI embedding 空间验证 benchmark 非重叠分布

**Application study**：用完整 suite 重评 Shark、GNU parallel、hS、PaSh（AWS c6i.4xlarge，16-core，Ubuntu 24.04），揭示各系统在不同 script 结构上的 trade-off。深度细节见 [[atc2025-lamprou]]。

## 设计取舍

- **取舍 1：真实性与可运行性**——curate 126 个 end-to-end 程序 + 真实输入，集成成本 10–80 人时/benchmark（总计约 520 人时）；牺牲快速 fork 新 benchmark 的轻便性，换取 wild workload 代表性。
- **取舍 2：POSIX 优先 vs Bash 生态**——默认 `bash --posix`，最大化跨 optimizer 可比性；牺牲对 bashism、数组、关联数组等现代脚本特性的覆盖。
- **取舍 3：输出正确性 vs 性能隔离**——哈希 validator 保证功能等价，但不强制每次 run 清空 page cache 或固定 CPU 频率；简化 harness，接受 OS 噪声。
- **取舍 4：Drop-in 评测 vs 手工改写**——Shark/parallel 需人工标注并行区域（合理反映其 UX），hS/PaSh 零改写；不同系统的 adoption friction 被显式暴露而非抹平。
- **边界条件**：在 Linux + Debian 系依赖、本地/云副本可访问、研究者能接受 24h full run 时最优雅；hS 原型对 ci-cd/file-mod/pkg 等整组失败、PaSh 对 bio 失败，说明 benchmark 同时也是 **maturity stress test**。

## 实验与结果

- **规模**：14 benchmark sets、126 shell scripts；full 输入最大 146GB（weather）；依赖含 600+ Debian 包、50 PyPI、110 AUR、1964 npm 及其传递依赖（>400GB 复制层）
- **多样性**：覆盖全部主要 POSIX construct；PCA 显示静态/动态/embedding 空间均广泛分布，无两 benchmark 语法分布完全相同
- **动态跨度**：CPU 2.1–6544.8s（shell+command 分开统计）、内存 6.1MB–25.1GB、I/O 85.7MB–336GB；pkg 归一化后 CPU 强度高于绝对时间暗示的「中等」
- **Shark**（手工 transformation）：suite 内 1.01–13.43×；nlp 6.46×、weather 13.43×；covid/oneliners/bio/unixfun 仅 1.01–1.06×（高度 pipeline 化或强依赖）
- **GNU parallel**（手工改写）：平均约 **2.6×**；file-mod 3.84×、nlp 6.46×；ci-cd/repl 1.16×/0.95×；unixfun 1.02×（stage 依赖）
- **hS**（drop-in 原型）：独立 stage 上 1.5–4.97×（analytics/unixfun 两端）；强依赖 stage 平均 **0.72×**（speculation 回滚开销）；多组 benchmark 完全无法运行或结果错误
- **PaSh**（`--width 4`，无额外 annotation）：oneliners 2.14×、covid 1.82×；pkg/bio/file-mod/repl/ci-cd 几乎无收益；bio 直接执行失败
- **可用性**：min+bare 约 20 分钟（t3.large）；full+Docker+5 runs 约 24 小时；MIT license，https://kben.sh

## Critical Analysis

### 论证链条

Problem（无统一 benchmark → 研究减速、结论不可比）→ Design（真实程序 + 分层输入 + harness + 表征）→ Evidence（静态/动态/PCA 证明多样性）→ Application（四系统 speedup 分布验证 benchmark 能区分优化域）链条闭合良好。关键跳步在于：**「126 个 curated 程序代表 wild shell」**主要依赖来源多样性与 [[Bash-in-the-Wild]] 语法比例对比，而非概率抽样；作者诚实承认选择过程有人工 curate，但未量化 selection bias（例如是否过度偏向 pipeline-heavy 学术范例）。

### 假设压力测试

- **已证明**：Koala 能同时 stress 计算/内存/I/O 极端；能在统一输入上复现并扩展四篇 prior work 的关键结论；infrastructure 支持 Docker 隔离与多环境 validator。
- **可能失效**（推断）：
  - **Serverless / 分布式 shell**（POSH、DiSh 等）：benchmark 假设本地文件系统与单机进程模型，未覆盖跨节点 shuffle、FaaS 冷启动
  - **交互式 shell**：zsh-bench 类 REPL 延迟不在覆盖范围
  - **安全/权限敏感脚本**：pkg 需下载构建外部包，在 locked-down CI 中可能不可运行
  - **硬件外推**：表征在单一 Ryzen 桌面机与 AWS c6i 上完成，ARM、低内存边缘节点行为未测
  - **时间漂移**：依赖 pinning 与 Zenodo 快照；5 年后 npm/AUR 生态变化可能破坏 reproducibility（论文计划数年一版 release，但未给出自动化 drift 检测）

### 实验可信度

- **Benchmark 代表性**：显著优于自写 microbenchmark 与 POSIX 测试套，14 域 + 三档输入是主要卖点；但仍可能 under-represent 纯 orchestration（Ansible/Terraform wrapper）、数据库 CLI glue、GPU cluster job script。
- **Baseline 公平性**：四系统评测条件不一致——Shark/parallel 有人工优化上限，hS/PaSh 用 drop-in 且 hS 为 early prototype；这反映真实 adoption cost，但横向比较「谁更快」需附带 **equal effort** 说明，论文部分做到（Appendix II）但未量化改写人时与 speedup 的 Pareto 曲线。
- **Ablation**：输入规模（min/small/full）对动态特征的影响有 Figure 6 支撑；缺少「去掉某 benchmark set 后 diversity PCA 塌缩多少」的敏感性分析。
- **Metrics**：聚焦 speedup 与资源汇总，**未报告** tail latency、validator flaky rate、多 tenant 并发下载输入时的 harness 行为、优化后输出差异的 subtle semantic drift（仅 hash）。

### 系统性缺陷

- **运行成本**：full suite 24h + 400GB 级依赖，对 routine regression 仍偏重；min 模式虽 20 分钟但不能代表性能特征。
- **可观测性**：harness 报告 execution characteristics，但论文未讨论统一 tracing 接口供 optimizer 插入细粒度 profiler。
- **故障恢复**：网络中断 fetch、容器 OOM、partial benchmark failure 时的 resume 策略论文未详述。
- **社区治理**：benchmark 添加流程有规范（五脚本模板），但 acceptance criteria（何谓「代表 wild」）仍由作者团队主导；论文未讨论独立 steering committee。
- **优化系统兼容性**：hS/PaSh 在 substantial subset 上 fail，既说明 benchmark 严格，也暴露 **drop-in 评测对 immature system 的惩罚性**——可能被误读为 benchmark 过难而非系统未完成。

## 局限与 Future Work

- **局限 1**：curated 集合无法保证对全球 shell 使用的统计代表性；CI/CD、repl 等无外部输入 benchmark 的动态特征与有大数据输入的 set 不易在同一坐标系比较。
- **局限 2**：Shark/parallel 的手动改写引入 evaluator expertise 变量，削弱「一键公平对比」理想。
- **局限 3**：hS/PaSh 的高失败率表明 benchmark 对 POSIX 子集与外部命令语义假设严格，但未提供 graded compatibility tiers（smoke / compat / perf）。
- **Future work 1**：用 Koala 动态特征向量对 wild shell corpus 做 coverage gap 测量——量化「新增某 GitHub 脚本族后 PCA 体积增长多少」，指导版本迭代而非凭直觉加 benchmark。
- **Future work 2**：建立 **equal-effort evaluation protocol**——记录每系统达到当前 speedup 所需自动/人工改写 LOC 与 wall-clock，将 adoption cost 与性能一起报告。
- **Future work 3**：扩展 serverless / 分布式 shell 子集（对象存储输入、跨节点 pipeline），测试 POSH/DiSh 等系统是否需第二代 benchmark 维度。
- **Future work 4**：长期 reproducibility monitor——定期重跑 min tier 检测依赖漂移，与 Zenodo 快照 diff 联动。

## 相关

- **相关概念**：[[Benchmark-Suite]]、[[POSIX-Shell]]、[[Reproducibility]]、[[CI-CD]]
- **被评估系统**：[[PaSh]]、Shark、hS、[[GNU-Parallel]]
- **同类 benchmark**：ShellBench、zsh-bench、UnixBench、DaCapo、PARSEC
- **同会议**：[[ATC-2025]]
- **对比**：Koala 填补的是「shell whole-program performance」空白，与 POSIX 正确性测试套、microbenchmark 互补而非替代