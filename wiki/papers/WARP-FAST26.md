---
type: paper
name: WARP
full_title: "Characterizing and Emulating FDP SSDs with WARP"
authors: [Inho Song, Shoaib Asif Qazi, Javier González, Matias Bjørling, Sam H. Noh, et al.]
venue: FAST
year: 2026
tags: [ssd, fdp, write-amplification, emulator, nvme]
source_pdf: "[[fast2026-song.pdf]]"
source_md: "[[fast2026-song]]"
---

# Characterizing and Emulating FDP SSDs with WARP (FAST 2026)

> **一句话总结**：首个对商用 [[NVMe]] Flexible Data Placement（FDP）SSD 的跨设备/跨 workload 系统评测 + 首个开源 FDP emulator（基于 FEMU），揭示 FDP 在 cache 类 workload 可逼近 WAF=1.0 但在 misclassification、RUH 干扰和 adversarial invalidation 下崩塌；发现两种未报道现象 Noisy RUH 与 Save Sequential，并给出 firmware 设计建议（PI vs II 在 OP 阈值上的 trade-off）。

## 问题

NVMe Flexible Data Placement（FDP, TP4146）是 hyperscaler 推动的新 SSD 接口：host 用 Reclaim Unit Handle（RUH）给 write 打 placement hint，相同生命周期数据进同一 RU，理想 WAF→1.0；不像 OpenChannel/[[ZNS]] 需要应用大改，FDP 保持 block 接口兼容性。但 FDP 是 best-effort 而非保证：GC 仍由 device 管理，vendor 在 RU size、OP 比例、RUH 数量、initially-isolated（II）vs persistently-isolated（PI）等上各自硬编码，且对 host 不透明。

社区缺乏对 FDP 的系统理解：什么时候 FDP 起效？什么时候失败？vendor 之间为什么差距巨大？现有研究只在单个 stack（如 CacheLib）报喜，且无法解释黑盒 firmware 行为。

## 核心方法

**Characterization**：在两块 PCIe Gen5 商用 FDP SSD（不同 vendor，均 8-RUH）上跑三类 workload：
- 合成 FIO（多 stream + 不同访问模式）
- Production trace（CacheLib 的 kvcache、cdn、twitter）
- 文件系统（F2FS 的 Fileserver、OLTP）

**WARP emulator**：基于 FEMU 扩展，把商用 firmware 中藏起来的旋钮全部暴露成可调参数：II vs PI、RU size、OP ratio、GC victim 选择策略、per-RUH amplification dynamics。已上游到 https://github.com/MoatLab/FEMU。

**关键发现**：
- **Noisy RUH**：一个 RUH 内的 invalidation 会在其他 RUH 引发额外写放大（资源共享）。
- **Save Sequential**：device 过早回收长 sequential stream。
- **PI vs II**：PI 仅在 OP 高于设备相关阈值时才优于 II；OP 较低时 II 反而更鲁棒。
- F2FS 标 99% 用户数据为 WARM（→ 同一 RUH），FDP 对 F2FS 几乎无效。
- CacheLib kvcache 上 FDP 把 SOC 40% 的 WAF 从 1.85 降到 ~1.0，且不损失 hit ratio。

## 关键结果

- CacheLib kvcache 多租户场景 WAF 从 ~3.0（NoFDP）降到 ≤2.6（FDP）。
- 极端 worst-case（uniform random invalidation）下 FDP 优势接近消失（SSDA 稳到 ~2.6×，SSDB 飙到 4.5×）。
- WARP 重现真实硬件 WAF 趋势，并暴露 per-RUH 内部动态（real device 不可见）。
- 提出超越当前硬件的 firmware GC 策略，进一步降低 WAF。

## 相关

- **相关概念**：[[NVMe]]、Flexible Data Placement、Reclaim Unit Handle、Write Amplification Factor、Garbage Collection、[[ZNS]]
- **同类工作**：CacheLib + FDP integration、F2FS data hint、FEMU、ZNS、Multi-stream SSD、OpenChannel SSD
- **同会议**：[[FAST-2026]]
