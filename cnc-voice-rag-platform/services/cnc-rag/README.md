# 数控领域RAG服务

这里用于实现论文自己的检索与生成服务，不直接修改上游语音网关。

建议提供OpenAI兼容接口：

- `POST /v1/chat/completions`
- `GET /health`
- `POST /debug/retrieve`：仅实验环境使用，返回每一路召回、融合分数和重排结果。

内部模块建议拆分为：

- `ingestion`：文档解析和索引构建；
- `query`：ASR文本规范化、实体与元数据抽取；
- `retrieval`：BM25、向量检索和元数据过滤；
- `fusion`：RRF/加权融合和重排序；
- `generation`：提示、引用、冲突检测和拒答；
- `evaluation`：离线检索、回答质量和消融实验。

其中 `evaluation/` 已从旧量子物理FAQ项目抽取并重写第一批通用资产：严格JSONL读写、Recall@k、Hit@k、MRR、nDCG@k以及新的分层实验场景。旧项目服务端和索引代码因包含硬编码凭据、旧依赖和量子物理状态数据，不直接复制。

`generation/citations.py`已经实现第一版运行时引用约束：只允许从本次真实检索结果中选择引用，输出chunk编号、文档、章节、PDF页、印刷页和支持原文；引用未检索到的gold编号会直接报错。当前尚未接入LLM生成接口。
