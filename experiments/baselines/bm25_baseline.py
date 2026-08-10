"""
BM25检索基线实验
"""

import json
from pathlib import Path
from typing import List, Dict
import numpy as np
from rank_bm25 import BM25Okapi
import jieba


class BM25Baseline:
    """BM25检索基线"""

    def __init__(self, corpus: List[Dict]):
        """
        初始化BM25索引

        Args:
            corpus: 文档列表，每个文档是包含'id'和'text'的字典
        """
        self.corpus = corpus
        self.doc_ids = [doc['id'] for doc in corpus]

        # 分词
        tokenized_corpus = [list(jieba.cut(doc['text'])) for doc in corpus]

        # 构建BM25索引
        self.bm25 = BM25Okapi(tokenized_corpus)
        print(f"已构建BM25索引，文档数量: {len(corpus)}")

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 返回前k个结果

        Returns:
            相关文档列表，包含id、text和score
        """
        # 查询分词
        tokenized_query = list(jieba.cut(query))

        # BM25评分
        scores = self.bm25.get_scores(tokenized_query)

        # 获取top-k
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回得分大于0的结果
                results.append({
                    'id': self.doc_ids[idx],
                    'text': self.corpus[idx]['text'],
                    'score': float(scores[idx])
                })

        return results


def load_evaluation_data(eval_dir: Path) -> tuple:
    """加载评测数据"""
    questions = []
    with open(eval_dir / "questions.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            questions.append(json.loads(line))

    answers = {}
    with open(eval_dir / "answers.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            ans = json.loads(line)
            answers[ans['question_id']] = ans

    return questions, answers


def calculate_recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """计算Recall@K"""
    retrieved_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)

    if not relevant:
        return 0.0

    return len(retrieved_k & relevant) / len(relevant)


def main():
    # TODO: 实际实现时需要加载真实的文档chunks和评测数据
    print("BM25基线实验")
    print("=" * 50)

    # 示例：构造简单测试数据
    corpus = [
        {"id": "doc1", "text": "G01指令用于直线插补，F参数指定进给速度"},
        {"id": "doc2", "text": "M03指令使主轴正转，M04指令使主轴反转"},
        {"id": "doc3", "text": "机床零点是机床固有的基准点"},
    ]

    baseline = BM25Baseline(corpus)

    # 测试查询
    query = "G01的F参数是什么意思"
    results = baseline.search(query, top_k=3)

    print(f"\n查询: {query}")
    print(f"检索结果 (Top-{len(results)}):")
    for i, result in enumerate(results, 1):
        print(f"{i}. [Score: {result['score']:.4f}] {result['text'][:50]}...")

    print("\n提示: 这是示例代码，实际使用时需要:")
    print("1. 加载 data/chunks/ 中的文档分块")
    print("2. 加载 data/evaluation/ 中的测试问题")
    print("3. 计算完整的评价指标（Recall@K, MRR, nDCG）")
    print("4. 保存实验结果到 experiments/results/")


if __name__ == "__main__":
    # 需要先安装: pip install rank-bm25 jieba
    try:
        from rank_bm25 import BM25Okapi
        main()
    except ImportError:
        print("请先安装依赖: pip install rank-bm25 jieba")
