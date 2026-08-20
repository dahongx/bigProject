"""
向量检索基线实验

使用BGE-M3模型构建向量索引并检索评测
"""

import sys
import json
from pathlib import Path
from typing import List, Dict
import numpy as np
from tqdm import tqdm

try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请安装: pip install sentence-transformers faiss-cpu")
    sys.exit(1)


class VectorRetriever:
    """向量检索器"""

    def __init__(self, model_name: str = "BAAI/bge-m3", cache_dir: str = None):
        """
        初始化向量检索器

        Args:
            model_name: 模型名称
            cache_dir: 模型缓存目录
        """
        print(f"加载模型: {model_name}")
        self.model = SentenceTransformer(
            model_name,
            cache_folder=cache_dir,
            device='cpu'  # 改为'cuda'如果有GPU
        )
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"模型维度: {self.dimension}")

    def build_index(self, chunks: List[Dict], save_path: str = None):
        """
        构建FAISS索引

        Args:
            chunks: chunk列表
            save_path: 索引保存路径

        Returns:
            FAISS索引对象
        """
        print(f"编码 {len(chunks)} 个chunks...")

        # 提取文本
        texts = [c['content'] for c in chunks]

        # 批量编码
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        # 构建索引
        print("构建FAISS索引...")
        index = faiss.IndexFlatIP(self.dimension)  # 内积（已归一化=余弦）
        index.add(embeddings.astype('float32'))

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(index, save_path)
            print(f"索引已保存: {save_path}")

        return index, embeddings

    def search(self, query: str, index: faiss.Index, top_k: int = 10):
        """
        检索

        Args:
            query: 查询文本
            index: FAISS索引
            top_k: 返回top-k

        Returns:
            scores, indices
        """
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True
        )

        scores, indices = index.search(
            query_embedding.astype('float32'),
            k=top_k
        )

        return scores[0], indices[0]


def load_chunks(profile_path: str) -> List[Dict]:
    """加载chunks"""
    chunks = []
    with open(profile_path, 'r', encoding='utf-8') as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def load_questions(path: str) -> List[Dict]:
    """加载问题"""
    questions = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            questions.append(json.loads(line))
    return questions


def load_gold_mapping(path: str) -> Dict:
    """加载gold mapping"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def evaluate_retrieval(retrieved_indices: List[int],
                       gold_chunk_ids: List[str],
                       chunks: List[Dict]) -> Dict:
    """
    评估检索结果

    Args:
        retrieved_indices: 检索到的chunk索引
        gold_chunk_ids: gold chunk ID列表
        chunks: 完整chunk列表

    Returns:
        评估指标
    """
    gold_set = set(gold_chunk_ids)

    # 检查每个位置
    relevant_ranks = []
    for rank, idx in enumerate(retrieved_indices, start=1):
        if chunks[idx]['chunk_id'] in gold_set:
            relevant_ranks.append(rank)

    # 计算指标
    hit_at_1 = 1 if relevant_ranks and relevant_ranks[0] == 1 else 0
    hit_at_5 = 1 if relevant_ranks and relevant_ranks[0] <= 5 else 0
    hit_at_10 = 1 if relevant_ranks and relevant_ranks[0] <= 10 else 0
    mrr = 1 / relevant_ranks[0] if relevant_ranks else 0

    return {
        'hit_at_1': hit_at_1,
        'hit_at_5': hit_at_5,
        'hit_at_10': hit_at_10,
        'mrr': mrr,
        'first_relevant_rank': relevant_ranks[0] if relevant_ranks else None
    }


def main():
    """主流程"""
    import argparse

    parser = argparse.ArgumentParser(description='向量检索基线实验')
    parser.add_argument('--chunks', required=True, help='chunks文件路径')
    parser.add_argument('--questions', required=True, help='问题文件路径')
    parser.add_argument('--mapping', required=True, help='gold mapping文件路径')
    parser.add_argument('--output', required=True, help='结果输出路径')
    parser.add_argument('--model', default='BAAI/bge-m3', help='模型名称')
    parser.add_argument('--cache-dir', default='models', help='模型缓存目录')

    args = parser.parse_args()

    # 加载数据
    print("加载数据...")
    chunks = load_chunks(args.chunks)
    questions = load_questions(args.questions)
    gold_mapping = load_gold_mapping(args.mapping)

    print(f"Chunks: {len(chunks)}")
    print(f"Questions: {len(questions)}")

    # 初始化检索器
    retriever = VectorRetriever(
        model_name=args.model,
        cache_dir=args.cache_dir
    )

    # 构建索引
    index_path = args.output.replace('.json', '.index')
    index, embeddings = retriever.build_index(chunks, save_path=index_path)

    # 检索评测
    print("\n开始检索评测...")
    results = []

    for q in tqdm(questions, desc="检索"):
        # 检索
        scores, indices = retriever.search(q['question'], index, top_k=10)

        # 评估
        gold_ids = gold_mapping.get(q['id'], [])
        metrics = evaluate_retrieval(indices, gold_ids, chunks)

        results.append({
            'question_id': q['id'],
            'question': q['question'],
            'retrieved_chunk_ids': [chunks[i]['chunk_id'] for i in indices],
            'scores': scores.tolist(),
            **metrics
        })

    # 汇总指标
    n = len(results)
    summary = {
        'total_questions': n,
        'hit_at_1': sum(r['hit_at_1'] for r in results) / n,
        'hit_at_5': sum(r['hit_at_5'] for r in results) / n,
        'hit_at_10': sum(r['hit_at_10'] for r in results) / n,
        'mrr': sum(r['mrr'] for r in results) / n
    }

    print("\n=== 结果 ===")
    print(f"Hit@1:  {summary['hit_at_1']:.3f}")
    print(f"Hit@5:  {summary['hit_at_5']:.3f}")
    print(f"Hit@10: {summary['hit_at_10']:.3f}")
    print(f"MRR:    {summary['mrr']:.3f}")

    # 保存结果
    output = {
        'summary': summary,
        'details': results,
        'config': {
            'model': args.model,
            'chunks_file': args.chunks,
            'dimension': retriever.dimension
        }
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存: {args.output}")


if __name__ == "__main__":
    main()
