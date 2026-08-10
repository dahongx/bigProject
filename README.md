# 数控加工现场语音交互式检索增强知识服务研究

> 硕士学位论文实验与验证平台
> 
> 更新日期：2026年8月10日

## 项目概述

本项目研究面向数控加工现场的语音交互式RAG知识服务方法，通过ESP32语音终端验证其在工业现场的可用性。

**研究内容**：

1. CNC专业术语、G/M代码、参数和报警代码的语音查询规范化
2. 融合BM25、向量检索、元数据约束和重排序的混合检索方法
3. 带引用、拒答和安全约束的回答生成
4. ESP32语音终端硬件验证平台

**不做的内容**：

- 不构建大规模知识图谱
- 不训练通用大语言模型
- 不自研完整ASR/TTS模型（作为算法创新）
- 不直接控制机床

## 项目结构

```
big/
├── cnc-voice-rag-platform/     # 论文验证平台（核心代码）
│   ├── vendor/xiaozhi-server/  # 抽取的语音网关底座
│   ├── services/cnc-rag/       # 数控领域RAG服务（论文核心）
│   └── docs/                   # 课题方案、技术路线、论文大纲
├── xiaozhi-esp32-server/       # 上游完整源码（参考用，不提交）
├── data/                       # 数据集和实验数据
│   ├── raw/                    # 原始文档（PDF等）
│   ├── parsed/                 # 解析后的结构化文档
│   ├── chunks/                 # 分块结果
│   ├── terminology/            # 术语、代码、同义词表
│   └── evaluation/             # 测试问题、标准答案、证据标注
├── experiments/                # 实验脚本和结果
│   ├── baselines/              # 基线方法
│   ├── ablation/               # 消融实验
│   └── results/                # 实验结果和分析
└── models/                     # 模型配置和权重（可选）
```

## 快速开始

### 环境准备

```bash
# 创建虚拟环境
python -m venv venv

# Windows激活
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 数据准备

1. 将数控手册PDF放入 `data/raw/`
2. 运行文档解析：`python scripts/parse_documents.py`
3. 构建术语表：参考 `data/terminology/README.md`
4. 准备测试集：参考 `data/evaluation/README.md`

### 运行实验

```bash
# 文本RAG基线实验
python experiments/baselines/bm25_baseline.py
python experiments/baselines/vector_baseline.py
python experiments/baselines/hybrid_baseline.py

# 语音查询规范化实验
python experiments/query_normalization/asr_correction.py

# 完整系统实验
python experiments/end_to_end/system_evaluation.py
```

## 重要文档

### 给导师审阅

- [课题方案（导师审阅稿）](cnc-voice-rag-platform/docs/导师审阅稿_课题方案.md)
- [完整技术路线（审阅稿）](cnc-voice-rag-platform/docs/完整技术路线_审阅稿.md)
- [论文大纲](cnc-voice-rag-platform/docs/thesis-outline.md)

### 开发实施

- [后续实施步骤](cnc-voice-rag-platform/docs/后续实施步骤.md)
- [系统架构与裁剪说明](cnc-voice-rag-platform/docs/architecture-and-pruning.md)
- [文档导航](cnc-voice-rag-platform/docs/README.md)

## 当前状态

- [x] 确定研究方向和题目
- [x] 抽取语音服务器底座
- [x] 编写课题方案和技术路线
- [x] 初始化Git仓库
- [ ] 收集数控技术文档
- [ ] 构建术语词表
- [ ] 实现文本RAG基线
- [ ] 验证语音链路
- [ ] 标注测试数据集
- [ ] 完成核心算法实验
- [ ] 接入ESP32硬件
- [ ] 撰写论文

## 技术栈

- **语音处理**：FunASR / Whisper（ASR）、CosyVoice / Edge-TTS（TTS）
- **文档解析**：PyMuPDF、Docling、MinerU
- **检索**：Elasticsearch（BM25）、Qdrant / Milvus（向量）
- **重排序**：BGE Reranker
- **大模型**：Qwen系列（本地）、API模型（对比）
- **后端**：FastAPI
- **硬件**：ESP32-S3、麦克风、扬声器
- **实验管理**：Python、pandas、scikit-learn

## 许可声明

- 本项目语音网关部分基于 [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server) (MIT License)
- 论文核心RAG算法代码为原创研究成果
- 详见 [THIRD_PARTY_NOTICES.md](cnc-voice-rag-platform/THIRD_PARTY_NOTICES.md)

## 联系方式

GitHub: https://github.com/dahongx/bigProject

---

**研究题目**：面向数控加工现场的语音交互式检索增强知识服务研究

**研究机构**：[你的学校和学院]

**研究周期**：2026年8月 - 2027年6月
