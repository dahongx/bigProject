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

当前仅建立目录和接口边界，待数据源、模型及向量库确定后实现。
