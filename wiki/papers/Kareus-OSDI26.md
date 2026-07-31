---
type: paper
name: Kareus
full_title: "Kareus: Joint Reduction of Dynamic and Static Energy in Large Model Training"
authors: [Ruofan Wu, Jae-Won Chung, Mosharaf Chowdhury]
venue: OSDI
year: 2026
tags: [distributed-training, energy-efficiency, gpu-frequency, kernel-scheduling]
source_pdf: "[[osdi26-wu-ruofan.pdf]]"
source_md: "[[osdi26-wu-ruofan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 联合降低大模型训练的动态与静态能耗（OSDI 2026）

> **原题**：Kareus: Joint Reduction of Dynamic and Static Energy in Large Model Training

> **一句话总结**：Kareus联合搜索communication launch timing、SM allocation与GPU frequency，因为三者共同改变overlap、runtime和dynamic/static energy；同训练时间最多省28.3% energy，或同energy最多快27.5%。

## 问题与动机

单独DVFS只降dynamic power却可能延长static energy时间，单独kernel overlap又忽略frequency改变compute/communication contention；相同工作量的schedule能耗/时间可差3.29×。

## 关键观察 / 隐含假设

- 最佳SM allocation与launch timing随frequency变化，三者不可独立调优。
- steady frequency在相同平均频率下可避免凸dynamic power惩罚。
- iteration kernel pattern重复，offline search可摊销。

## 核心方法

Kareus把全局组合问题拆成partition-local subproblems，以multi-pass multi-objective optimization分别推进total、dynamic、static energy与uncertainty frontier，再组合可行execution schedules；限制communication SM搜索并用nanobatching减少dependency。

## 实验与结果

- **设置**：多种[[LLM|LLM]] training workloads与GPU配置，对比energy/frequency与overlap SOTA，以iteration time和joules为指标（§7、图 13–15）。
- 同time energy最多-28.3%，同energy time最多-27.5%；MBO平均两小时内。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| joint optimization扩展Pareto frontier | 图 13–15 | 所测GPU/models | 强 |
| 搜索成本可摊销 | Appendix C/D | 长训练job | 中 |

## 批判性分析

### 论证链条

3.29× schedule差异先证明耦合，再由frontier实验支持联合优化。

### 假设压力测试

kernel shape、thermal/power cap或cluster contention漂移会使offline frontier过期；短job无法摊销两小时搜索。

### 实验可信度

真实measurement与emulation结合覆盖多点，但电网carbon、cooling和host/network energy未计入。

## 局限与后续工作

- online recalibration与whole-cluster/carbon-aware objective。
- 支持动态shape、multi-tenant power cap。

## 相关

- **相关概念**：[[Energy-Efficiency]]、[[DVFS]]、[[Communication-Computation-Overlap]]
- **同会议**：[[OSDI-2026]]
