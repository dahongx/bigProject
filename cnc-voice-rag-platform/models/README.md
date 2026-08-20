# 本地模型目录

当前不预置模型。确认需要本地模型后再加入，并记录模型名称、版本、来源、许可证、文件校验值、用途和对应实验配置。

旧FAQ项目中的 `bge-small-en-v1.5` 不复制到这里，因为它面向英文，不能直接代表中文CNC语料上的合适选择。

## 当前分词器

`bge-m3-tokenizer/` 只保存 BAAI/bge-m3 的分词器资产，不包含模型权重。它用于让切块长度与后续候选中文嵌入模型使用同一套 token 口径。模型权重在向量检索实验开始前再决定是否下载。

本地路径：`models/bge-m3-tokenizer/tokenizer.json`。该目录不纳入 Git；重新下载时必须把 Hugging Face 缓存设置到 `E:\big\.cache\huggingface`，不能使用 C 盘默认缓存。
