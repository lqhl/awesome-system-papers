# 论文下载脚本

这个文件夹包含用于下载会议论文的脚本。

## 脚本列表

### `download_usenix_papers.py`

通用的 USENIX 会议论文下载脚本，支持 OSDI, ATC, NSDI 等会议。

#### 使用方法

```bash
python3 download_usenix_papers.py <conference> <year> [output_dir]
```

#### 示例

```bash
# 下载 OSDI 2025 论文
python3 download_usenix_papers.py osdi 2025 osdi-2025

# 下载 ATC 2025 论文
python3 download_usenix_papers.py atc 2025 atc-2025

# 下载 NSDI 2025 论文
python3 download_usenix_papers.py nsdi 2025 nsdi-2025
```

#### 特性

- 自动从会议 technical sessions 页面提取所有论文
- 验证下载的文件是否为有效的 PDF
- 支持断点续传（已下载的论文会跳过）
- 自动过滤掉无效的下载（如 404 页面）
- 礼貌地添加延迟，避免对服务器造成压力

#### 输出

- 论文保存为 `{conference}{year}-{paper-id}.pdf`
- 下载完成后会显示统计信息

## 注意事项

1. 请遵守 USENIX 的使用条款
2. 论文版权归作者所有
3. 下载的论文仅供个人学习研究使用
