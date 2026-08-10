# 评测数据集

本目录存放用于评价检索和生成质量的标注测试集。

## 数据集结构

### 1. 问题集 (`questions.jsonl`)

每行一个JSON对象：

```json
{
  "id": "Q001",
  "question": "G01指令中的F参数是什么意思？",
  "question_type": "事实查询",
  "knowledge_category": "编程知识",
  "cnc_system": "通用",
  "model": null,
  "difficulty": "简单",
  "requires_multi_hop": false,
  "metadata": {
    "contains_code": true,
    "contains_terminology": true
  }
}
```

### 2. 标准答案与证据 (`answers.jsonl`)

```json
{
  "question_id": "Q001",
  "answer": "F参数表示进给速度，单位为mm/min或mm/rev",
  "evidence": [
    {
      "document": "FANUC_0i-MF_编程手册_2023.pdf",
      "page": 156,
      "chapter": "第4章 G代码详解",
      "section": "4.2 G01直线插补",
      "text": "F功能用于指定进给速度...",
      "relevance": "直接回答"
    }
  ],
  "answer_type": "definitive",
  "safety_level": "safe",
  "requires_confirmation": false
}
```

### 3. 问题分类

#### 按知识类型
- 操作知识：机床操作、开关机、对刀等
- 编程知识：G/M代码、程序结构、坐标系等
- 参数知识：参数含义、设置方法、影响等
- 报警知识：报警含义、原因、排查、措施
- 维护知识：保养周期、润滑、检查等
- 安全知识：安全规范、互锁、应急处理

#### 按问题复杂度
- 事实查询：单一知识点查询
- 步骤查询：需要返回操作步骤
- 条件查询：带有型号、版本或条件限定
- 跨段查询：答案分散在多个文档片段
- 多跳查询：需要推理或关联多个知识点
- 歧义查询：问题表达不清晰或有多种理解
- 无答案查询：知识库中不存在的问题

#### 按语音特点
- 含字母数字混合：G01、M03、SV0401
- 含专业术语：刀补、机零点、伺服
- 含中英文混合：FANUC系统、主轴
- 易混淆表达：零/灵、四/是

### 4. 评价指标数据

#### 检索评价 (`retrieval_eval.jsonl`)

记录每个问题的相关文档片段：

```json
{
  "question_id": "Q001",
  "relevant_chunks": [
    {"chunk_id": "chunk_156_2", "relevance": 2},
    {"chunk_id": "chunk_157_1", "relevance": 1}
  ]
}
```

相关性分级：
- 0: 不相关
- 1: 部分相关
- 2: 高度相关

#### 生成评价标准

- **正确性**：答案是否符合事实
- **忠实性**：答案是否基于检索到的证据
- **完整性**：是否涵盖问题的所有方面
- **引用准确率**：引用的文档、章节、页码是否正确
- **适合语音播报**：是否简洁、分步骤、易理解
- **安全性**：是否包含必要的安全提示

## 数据集规模建议

- 第一阶段（验证可行性）：50-100题
- 第二阶段（完整实验）：200-300题
- 最终版本：300-500题

## 标注流程

1. 从真实场景收集问题
2. 从手册中查找标准答案
3. 标注证据位置（文档、页码、章节）
4. 标注问题类型和难度
5. 双人标注后交叉校验
6. 专家审核（可选）

## 使用示例

```python
import json

# 加载问题集
questions = []
with open('data/evaluation/questions.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        questions.append(json.loads(line))

# 统计问题类型分布
from collections import Counter
types = Counter(q['question_type'] for q in questions)
print(types)
```

## 版本记录

- v0.1 (2026-08-10): 初始结构定义
- v0.2 (待定): 完成首批50题标注
- v1.0 (待定): 完成200题标注，进入论文实验
