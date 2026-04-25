---
type: paper
name: Moirai
full_title: "Moirai: Optimizing Placement of Data and Compute in Hybrid Clouds"
authors: [Ziyue Qiu, Hojin Park, Jing Zhao, Yu-Kai Wang, Arnav Balyan, et al.]
venue: SOSP
year: 2025
tags: [hybrid-cloud, data-placement, mip-optimization, uber, presto-spark]
source_pdf: "[[3731569.3764802.pdf]]"
source_md: "[[3731569.3764802]]"
---

# Moirai: Optimizing Placement of Data and Compute in Hybrid Clouds (SOSP 2025)

> **一句话总结**:基于 MIP 的混合云数据+计算联合摆放框架,在 Uber 四个月 6670 万 query、13.3 EB 访问的 trace 上把混合云部署成本相对 Alibaba Yugong 再砍 97%(egress 降 95–99.5%,副本降 99%,on-prem 网络降 89–98%)。

## 问题

企业长期停留在 on-prem + public cloud 的 hybrid 状态(Uber 预计 5 年)。跨站数据流带来巨大成本:cloud egress 9–11¢/GB(1 PiB ≈ $115K)、800 Gbps 专线 ≈ $1.6M/年、为规避 egress 而做的全量复制同样贵(Twitter 300 PB 副本 ≈ $90M/年)。现有方案各有毛病:No Rep egress 费爆炸;Rep 3Mon 存储费爆炸;Alibaba 的 Yugong 按 "project" 粒度摆放依赖人组织结构,但 Uber 只有 10% 的读发生在 project 内,且用固定副本预算+只优化带宽,与混合云的弹性存储/egress 费不匹配。

## 核心方法

Moirai 把问题建成一个 **Mixed-Integer Programming** 问题,同时决定每张表放 on-prem/cloud/双副本、每个 job 路由到哪里,目标函数含 egress、副本存储、专线容量费。关键 scalability trick:

- **Spinner** 从 access log 构建 job-table bipartite graph,用 query template 指纹(128-bit hash, 参考 Microsoft/Meta/PostgreSQL 做法)把 recurring job 聚类
- **过去一周未访问的表整体剪枝**,把问题规模从不可解压到几小时内跑完
- **按 dependency 做 grouping** 取代项目层次 grouping
- **预选常用副本表**,副本决策弱化为一个独立子问题
- **dependency-aware job routing**:对新 job,用 per-table access-size predictor 预测远程 fetch 量并路由到最小化 egress 的一侧
- **周期重优化 + ingress/egress penalty**:避免来回搬数据

## 关键结果

- 50/50 on-prem/cloud split 下,比 Yugong 降成本 97%
- Egress 降 95–99.5%,副本降最多 99%,on-prem 网络需求降 89–98%
- 周运行时从朴素 MIP 的 10 天压到几小时
- 对混合云容量比例变化(渐进迁移场景)成本下降持续,验证 data-move penalty 的价值
- 已给出 Uber 生产部署路径,simulator 与 trace 承诺公开

## 相关

- **相关概念**:[[Mixed-Integer-Programming]]、[[Data-Placement]]、hybrid cloud cost optimization
- **同类工作**:Yugong (Alibaba)、Cloudward Bound、Spotify/Twitter 迁移实践、Microsoft Cosmos Wing
- **同会议**:[[SOSP-2025]]
