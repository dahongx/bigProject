# DOC004 chunk候选集

更新日期：2026年8月19日

## 文件

- `fixed_v0.1.draft.jsonl`：350字符窗口、70字符重叠的固定长度候选chunk；
- `structural_v0.1.draft.jsonl`：按章节路径、标题、段落类型和表格区域组织的结构化候选chunk，目标上限600字符；
- `chunk_build_report.json`：两种策略的数量、长度、页码覆盖和风险统计。
- `v0.2-draft/`：使用 BAAI/bge-m3 tokenizer 生成的正式实验候选矩阵，包含256、512、1024 token固定窗口和512 token结构化切块；该目录有独立manifest和SHA256，不覆盖早期字符切块。

每个chunk包含稳定编号、正文、检索文本、原始块号、OCR行号、PDF页码、印刷页码、章节路径及用户引用元数据。

## 状态边界

当前两个文件都以`.draft.jsonl`结尾，`review_status`为`draft_contains_auto_ocr`。它们覆盖27页，但来源是尚未全量人工校正的块草稿，因此只用于验证切块、gold映射和引用管线，不能作为论文正式实验语料。

正式版本需要先完成来源块校正，再用同一配置重新生成，并冻结为新的版本号和SHA256。禁止直接把draft文件改名成正式文件。

## v0.2 token矩阵

生成命令：

```powershell
E:\big\cnc-voice-rag-platform\.venv-rag\Scripts\python.exe scripts\build_chunk_matrix.py
E:\big\cnc-voice-rag-platform\.venv-rag\Scripts\python.exe scripts\map_gold_chunk_matrix.py
E:\big\cnc-voice-rag-platform\.venv-rag\Scripts\python.exe scripts\validate_chunk_matrix.py
```

固定窗口的重叠比例约为20%。`source_fragments`记录固定窗口实际覆盖每个来源块的字符范围和覆盖率，避免只碰到一个来源块的少量文字就把整个来源块误判为已覆盖。
