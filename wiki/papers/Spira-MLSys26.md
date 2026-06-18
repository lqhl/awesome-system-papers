---
type: paper
name: Spira
full_title: "Spira: Exploiting Voxel Data Structural Properties for Efficient Sparse Convolution in Point Cloud Networks"
authors: [Dionysios Adamopoulos, Anastasia Poulopoulou, Georgios Goumas, Christina Giannoula]
venue: MLSys
year: 2026
tags: [sparse-convolution, point-cloud, gpu, voxel, 3d-perception]
source_pdf: "[[a87ff679a2f3e71d9181a67b7542122c.pdf]]"
source_md: "[[a87ff679a2f3e71d9181a67b7542122c]]"
---

# Spira: Exploiting Voxel Data Structural Properties for Efficient Sparse Convolution in Point Cloud Networks (MLSys 2026)

> **一句话总结**：首个 voxel-property-aware 稀疏卷积引擎，利用 voxel 坐标的整数性/有界性/几何连续性三条结构性质，end-to-end 推理平均 1.68×（up to 3.04×）快于 SOTA（TorchSparse++、Minuet）。

## 问题

自动驾驶、AR/VR 的点云网络里 Sparse Convolution (SpC) 是主要算子，两步：voxel indexing（构建 kernel map）+ feature computation（按 kernel map 计算输出）。现有 GPU 引擎（MinkowskiEngine、SpConv2、TorchSparse、TorchSparse++、PCEngine、Minuet）有两个关键缺陷：

1. voxel indexing 的 pre-processing（组织 query 结构）和 post-processing（重排/过滤 kernel map）开销大；
2. 对 output-stationary 和 weight-stationary 两种 dataflow 支持不全（Minuet 只支持 weight-stationary）。

它们都没利用 voxel 坐标的结构特性。

## 核心方法

识别三条 voxel 数据性质：**Integer**（整数值）、**Bounded**（空间范围受限）、**Neighboring**（同表面相邻 voxel L1-norm 小；submanifold layer 中小 L1-norm weight offset 的 kernel map 列密度显著高）。

Spira 四大 idea：

1. **One-Shot Z-Delta Search Mapping**：坐标一次性排序后，跨 layer 自动保持排序 → 完全省掉 pre-processing。把 K^3 weight offset 分成 K^2 组（每组 K 个 offset 共享 x,y，仅 z 连续），每组只做一次 binary search（anchor query），剩余 K-1 个 query 用 localized linear search，计算量从 |V_q|·K^3 降到 |V_q|·K^2 binary search + 低成本 linear。
2. **Packed-Native Voxel Indexing**：利用 Bounded 把 (v_x,v_y,v_z) 三元组 pack 进单个 32-bit 或 64-bit int（如 12/12/8 bits），让 downsampling（bitwise mask 即可 rounding）、sorting（packed 值保序）、mapping 查询全在 packed 格式上做，省 3× 内存、省比较开销。
3. **Adaptive Hybrid-Dataflow Feature Computation**：按 weight offset 的 L1-norm 阈值 t 分 dense/sparse，dense 走 output-stationary、sparse 走 weight-stationary，覆盖 full dataflow spectrum；t 通过 5 点采样 < 3 s 一次性 tune。
4. **Network-Wide Voxel Indexing**：发现所有 layer 的 voxel indexing 无相互依赖，在 network 起始并发跨多个 SM 批量执行，提升 GPU 利用率。

## 关键结果

- End-to-end point cloud inference：平均 1.68×，最高 3.04× vs TorchSparse++/Minuet，横跨 6 种 GPU（高端到 edge）。
- Layer-level：平均 2.11×、最高 3.44×。
- Search time 比 TorchSparse++ 快 7.83×、比 Minuet 快 1.82×；post-processing 比 TorchSparse++ 低 5.42×。
- 开源：github.com/SPIN-Research-Group/Spira

## 相关

- **相关概念**：稀疏卷积、voxel 化
- **同类系统**：TorchSparse/TorchSparse++、SpConv2、Minuet、PCEngine、MinkowskiEngine
- **同会议**：[[MLSys-2026]]