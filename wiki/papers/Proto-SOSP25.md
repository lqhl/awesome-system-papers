---
type: paper
name: Proto
full_title: "Proto: A Guided Journey through Modern OS Construction"
authors: [Wonkyo Choe, Rongxiang Wang, Afsara Benazir, Felix Xiaozhu Lin]
venue: SOSP
year: 2025
tags: [operating-systems, education, instructional-os, arm]
source_pdf: "[[3731569.3764811.pdf]]"
source_md: "[[3731569.3764811]]"
---

# Proto: A Guided Journey through Modern OS Construction (SOSP 2025)

> **一句话总结**：Proto 是跑在 Raspberry Pi 3B 上的 <10K SLoC 教学 OS，把完整系统拆成 5 个渐进原型，支持 DOOM ~60 FPS、视频播放 ~26 FPS，用"appealing apps"重新点燃学生对 OS 课程的兴趣。

## 问题

OS 课在北美顶校已从必修降为选修（top-30 里 20 所不再必修），学生对系统软件兴趣下滑。传统教学 OS（xv6、Pintos、Nachos、GeekOS、Embedded Xinu、EGOS-2000）偏 headless，只能跑终端程序，缺乏真正能"展示、把玩、带出教室"的完整体验；而用 Linux 做 OS 课则让学生只能改一小块 CPU 调度，失去"从零构建整个系统"的成就感。作者认为今天的 OS 教学缺了 UNIX 因 Space Travel、WWW、TeX 最初服务个人创作的那份激情。

## 核心方法

Proto 不是新研究内核，而是一套围绕四条教学原则的**增量原型（incremental prototyping）**课程框架：(P1) appealing apps —— 以 3D 动画、视频游戏、音乐/视频播放、DOOM、LiteNES Mario 仿真、区块链矿工为驱动，framebuffer/USB/audio 作一等公民；(P2) demonstrability —— 目标硬件 Raspberry Pi 3B（ARM Cortex-A53 四核 + 1GB + Game HAT 640p 屏幕/电池/按键），可带走做演示；(P3) incremental prototyping —— 把 OS 拆成 5 个 self-contained 原型，每个都能跑、每个对应一组 app；(P4) minimum viable implementations —— 新功能只有直接服务目标 app 才纳入。

系统架构类似 xv6，单体内核；用户态 EL0、内核态 EL1；每个 user app 独立地址空间（4KB 页），内核用 1MB block 映射；28 个 syscall（任务管理、文件系统、线程同步）；支持 USB HID 键盘、GPIO、PWM 音频、SD 卡 ext2-like ramdisk + FAT32 分区；window manager 支持多窗口 + 焦点输入分发。Proto 先完整实现，再分解成 5 个 prototype，让课堂按 app 驱动逐步构建。

## 关键结果

- 内核 <10K SLoC，与 xv6 量级相当
- DOOM ~60 FPS、MPEG-1 视频 ~26 FPS，与同硬件 Linux/FreeBSD 相当
- kernel microbenchmark 与 xv6 相当，功耗 <4 W、单次充电可用几小时
- 用户研究：大多数学生认为 P1-P4 原则直接改善了学习体验、激发了对 systems software 的热情
- 开源：https://github.com/fxlin/uva-os-main

## 相关

- **相关概念**：[[Incremental-Prototyping]]、[[Instructional-OS]]、[[Unix-Kernel]]
- **同类系统**：xv6、Pintos、Nachos、GeekOS、EGOS-2000、Embedded Xinu、NJU project-N
- **同会议**：[[SOSP-2025]]
