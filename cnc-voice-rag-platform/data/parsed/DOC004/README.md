# DOC004处理状态

更新日期：2026年8月18日

## 已完成

- 原始PDF登记、SHA256固定和版权边界记录；
- PDF物理页码与正文印刷页码映射；
- PaddleOCR 3.x CPU环境配置，全部依赖与模型位于E盘项目目录；
- 5页代表性OCR质量抽样；
- 首批27页原始OCR：PDF第111～128页、第145～153页；
- 批次完整性检查：27页全部成功，无缺失页、无空页、无Unicode替换字符。
- 27页原始OCR已转换为带稳定编号和原始行溯源的块草稿；
- 5页代表性数据与27页块完整性自动校验通过；
- 已生成按风险排序的人工复核队列和首批10题开发集骨架。

## 文件说明

- `metadata.json`：文档及处理批次元数据；
- `page_selection.md`：页码映射、抽样页和首批范围；
- `ocr_quality_report.md`：5页抽样质量结论；
- `ocr_batch_001_report.json`：27页批次自动统计；
- `pages/page_NNN_ocr.json`：带坐标、置信度和页码的原始OCR结果；
- `pages/page_NNN_ocr.txt`：便于人工阅读的原始OCR文本；
- `standardization_config.json`：批次范围、页码映射和初始章节路径；
- `人工标准化规则.md`：人工校正边界与复核步骤；
- `blocks.batch_001.draft.jsonl`：617个自动结构块草稿，不是最终语料；
- `manual_review_queue.csv`：按风险排序的人工复核入口；
- `block_build_report.json`：块类型、风险项及逐页统计；
- `block_validation_report.json`：代表页和溯源完整性校验结果；
- `rendered/`：页面渲染图，仅本地核对，不纳入版本控制。

## 当前停止线

`blocks.jsonl`尚未生成。下一步从`manual_review_queue.csv`开始人工校正标题、程序段、表格行、代码、小数点和正负号。不得把带`auto_draft`状态的块作为最终知识块；开发集可以建立问题骨架，但标准答案必须等待证据块复核完成。
