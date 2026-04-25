---
type: paper
name: TapeOBS
full_title: "Cost-efficient Archive Cloud Storage with Tape: Design and Deployment"
authors: [Qing Wang, Fan Yang, Qiang Liu, Geng Xiao, Yongpeng Chen, et al.]
venue: FAST
year: 2026
tags: [archive-storage, tape, object-storage, erasure-coding, huawei-cloud]
source_pdf: "[[fast2026-wang.pdf]]"
source_md: "[[fast2026-wang]]"
---

# Cost-efficient Archive Cloud Storage with Tape: Design and Deployment (FAST 2026)

> **一句话总结**：华为云 TapeOBS 用 4% 容量的 HDD pool 做异步缓冲 + batched erasure coding（12+2，冗余 1.17）+ dedicated drives + tape-tailored local engine 把磁带系统的「drive 数量稀缺、mount 80s、随机读慢」三大约束转成可调度的 bulk 任务；相比 HDD-based archive TCO 降 4.95×（CapEx 2.68×、OpEx 16.11×）；2022 年开始上线，已存储数百 PB 用户数据。

## 问题

云归档存储数据量爆炸（医疗影像、备份、视频、日志），HDD 成本仍高。磁带 TCO 优势明显（每 GB 价格低 50%、寿命 10 年 vs HDD 5 年、能耗低、CO2e 排放小），但物理特性对分布式系统极不友好：

- 一个 tape library 1000 盒磁带却只 4 个 drive（drive 远比磁带贵）；drive bandwidth 只有 360 MB/s。
- mount 一盘磁带要 ~80s（rewind 旧带 + 机械手搬运 + 新带定位）；drive 频繁切磁带（drive thrashing）会让有效带宽跌一半。
- 磁带是 append-only（shingled tracks），且随机读需要 wind/rewind 巨大寻道。

直接拿 HDD 系统替换 medium 不行，必须 holistic 重设计。

## 核心方法

**架构**：service layer + index layer + persistence layer（tape pool + HDD pool + MDC）+ DataBrain 调度器；用 PLog 抽象屏蔽底层。

**三大设计原则 → 对应技术**：

1. **Minimize drive thrashing**：
   - **Dedicated drives**（4 个 drive 静态分 2 写 + 1 读 + 1 internal）——写 drive 永远 append 同一带到满；read 不可避免要切带；internal（GC、EC repair、consistency check）通常长时间盯一带。混用所有 drive 必然全部 thrashing。
   - **Batched Erasure Coding（b-EC）**：service layer 先在内存攒多个 object 形成一个大 PLog（如 1.5 GB）再做一次 EC 切片；这样单个对象大概率只落在一条带上，restore 时不用同时启动 m 个 drive。代价是 degraded read 的修复数据量从 S 升到 m·S，可接受。

2. **Avoid random reads within a tape**：tape-tailored 本地存储引擎用两块 NVMe SSD 维护 PLog→物理地址的 KV 索引，避免读 metadata 时寻道磁带；tape 满后把元数据 dump 到磁带末尾的 metadata partition（双 SSD 故障时降级使用）；每 4 KB 数据加 DIF 字段实现自恢复。

3. **Async tape pool**：HDD pool（容量 4% of tape pool）做持久写缓冲 + restore 临时区。利用 restore 的小时级 SLA（3-5h 加急 / 5-12h 标准）把读写都做成异步 + bulk scheduling：
   - **Restore 调度**：按 ddl 收集任务，按 pt-id 分组，组内按 (plog-id, offset) 排序 → 物理顺序流，减少 thrashing 与 seek。
   - **Write 调度**：DataBrain 按对象的预估 expiration time（3 月粒度）分组写到同一带，让一带数据同时过期，大幅降 GC 开销。

EC 选 12+2（冗余 1.17），用 Huawei LDEC（XOR + Galois 域）。一致性检查后台轮询每 4 KB checksum 与 EC parity，应对硬件错误和 CPU SDC。

## 关键结果

- 10 年 TCO：CapEx 2.68×、OpEx 16.11× 优于 HDD-based archive；TCO 总降 4.95×。
- 2022 末灰度，2024 正式商用；至撰写时已存数百 PB 原始用户数据。
- 数据中心地板面积省 44%；CO2e 排放显著降低。
- 论文还披露生产环境 workload 特征与 tape library 实际故障模式。

## 相关

- **相关概念**：Erasure Coding、Object Storage、Log-Structured Write、Garbage Collection、SMR HDD、Cold Storage、TCO
- **同类系统**：AWS Glacier、GCP Archive、Alibaba Cloud Archive、Pelican (MSR)、IBM 3592、LTFS
- **同会议**：[[FAST-2026]]
