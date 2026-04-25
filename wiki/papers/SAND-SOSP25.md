---
type: paper
name: SAND
full_title: "SAND: A New Programming Abstraction for Video-based Deep Learning"
authors: [Juncheol Ye, Seungkook Lee, Hwijoon Lim, Jihyuk Lee, Uitaek Hong, Youngjin Kwon, Dongsu Han]
venue: SOSP
year: 2025
tags: [video-deep-learning, data-loading, storage-abstraction, gpu-utilization, preprocessing]
source_pdf: "[[3731569.3764847.pdf]]"
source_md: "[[3731569.3764847]]"
---

# SAND: A New Programming Abstraction for Video-based Deep Learning (SOSP 2025)

> **一句话总结**:给视频深度学习提出 view 抽象(类似数据库 view,暴露为 POSIX 文件路径),自动预物化 + 跨 epoch/跨 job 复用中间对象,SlowFast 的 2200 行 preprocess 代码压成 8 行,GPU 利用率比 CPU/GPU baseline 高 12.3×/2.9×。

## 问题

Video-based deep learning(VDL)从 OpenAI Sora、Gemini 到内容审核都在用,但预处理流水线极端复杂且慢:SlowFast 需要 2.2K 行 preprocess 代码(是模型训练代码的 2 倍+);CPU 预处理比 GPU 训练慢 2.2-6.5×,GPU 利用率掉 65-88%。云 GPU 实例 vCPU/GPU 比例固定(AWS p4、GCP a2 都是 12:1),加 CPU 不可行;NVDEC 等硬件解码器会挤占 GPU 显存(A100 上 1080p batch size 从 24 降到 16)且能耗多 2.6×。同一 video 每 epoch 重新解码,100-200 epoch 下来开销巨大,多 job 共享数据集时更是线性放大。

## 核心方法

**View 抽象**:把预处理管线的每个中间状态(压缩 video、decoded frame、augmented frame、training batch)抽象为 view——虚拟对象,暴露为 Linux VFS 下的 POSIX 文件路径(如 `/{task}/{epoch}/{iter}/view`),用户用 open/read/getxattr 访问,兼容 PyTorch DataLoader。用户只写 config(video handling + 5 种 augmentation branch),不用自己管 decoder、frame selection、augmentation。

**View Materialization Planning**:从 view 类型构造依赖 DAG,系统化识别"何时需要哪些中间对象",为跨任务/跨 epoch 共享找机会。一个典型例子:video1 的 frame 4 resize 后在 single/multi task 下多次复用,cache 一次省多次 decoding。

**Pre-Materialization + Priority Scheduling**:根据 DAG 选"高复用潜力"的中间对象预物化到 SSD,权衡重生成成本与存储约束。多线程并行物化,lagging 线程被动态 boost 优先级,保证实时 data feeding 不被 pre-materialization 拖慢。

## 关键结果

- Preprocess 代码从 2200 行(SlowFast)降到 8 行
- vs CPU baseline:hyperparameter search 训练时间 10.2×、GPU 利用率 12.3×
- vs GPU baseline(NVDEC):训练时间 2.8×、GPU 利用率 2.9×
- 覆盖 single task、hyperparam search、multi task、分布式数据并行(DDP)等场景
- 解决云实例中 83.5 TB Kinetics-400 数据集无法全缓存、EBS 带宽不够(55.8 Gbps 需求 vs 典型 3-8× 更低)的问题

## 相关

- **相关概念**:[[Data-Loading]]、[[GPU-Utilization]]、[[VFS]]、[[POSIX]]、[[Materialized-View]]
- **同类系统**:PyTorch DataLoader、DALI、[[Ray]]
- **同会议**:[[SOSP-2025]]
