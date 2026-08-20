"""
向量检索实验执行脚本（简化版，无需实际模型）

生成模拟向量检索结果，用于验证实验流程
"""

import json
import random
from pathlib import Path
from typing import List, Dict
import hashlib


def simulate_vector_retrieval(chunks: List[Dict], question: str, top_k: int = 10) -> List[int]:
    """
    模拟向量检索（用于流程验证）

    实际部署时替换为真实的BGE-M3编码和FAISS检索
    """
    # 简单的文本匹配模拟
    scores = []
    for i, chunk in enumerate(chunks):
        # 计算简单的词重叠
        q_words = set(question)
        # 兼容不同字段名
        chunk_text = chunk.get('text') or chunk.get('content', '')
        c_words = set(chunk_text)
        overlap = len(q_words & c_words)
        scores.append((i, overlap))

    # 按分数排序
    scores.sort(key=lambda x: x[1], reverse=True)

    return [idx for idx, _ in scores[:top_k]]


def load_chunks(profile_path: Path) -> List[Dict]:
    """加载chunks"""
    chunks = []
    with open(profile_path, 'r', encoding='utf-8') as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def load_questions(path: Path) -> List[Dict]:
    """加载问题"""
    questions = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            q = json.loads(line)
            questions.append(q)
    return questions


def load_gold_mapping(base_dir: Path, profile_name: str) -> Dict[str, List[str]]:
    """加载gold mapping"""
    mapping_file = base_dir / f"gold_candidates.{profile_name}.jsonl"

    mapping = {}
    if mapping_file.exists():
        with open(mapping_file, 'r', encoding='utf-8') as f:
            for line in f:
                item = json.loads(line)
                mapping[item['question_id']] = item.get('candidate_chunk_ids', [])

    return mapping


def evaluate(retrieved_indices: List[int], gold_ids: List[str], chunks: List[Dict]) -> Dict:
    """评估检索结果"""
    gold_set = set(gold_ids)

    relevant_ranks = []
    for rank, idx in enumerate(retrieved_indices, start=1):
        if idx < len(chunks) and chunks[idx]['chunk_id'] in gold_set:
            relevant_ranks.append(rank)

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

    parser = argparse.ArgumentParser(description='向量检索实验（流程验证版）')
    parser.add_argument('--chunk-dir', required=True, help='chunk目录')
    parser.add_argument('--questions', required=True, help='问题文件')
    parser.add_argument('--gold-dir', required=True, help='gold mapping目录')
    parser.add_argument('--output-dir', required=True, help='结果输出目录')

    args = parser.parse_args()

    chunk_dir = Path(args.chunk_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载问题
    questions = load_questions(Path(args.questions))
    print(f"[OK] 加载 {len(questions)} 道问题")

    # 对每个切块配置运行
    profiles = [
        'fixed_t256_o51',
        'fixed_t512_o102',
        'fixed_t1024_o205',
        'structural_t512'
    ]

    for profile in profiles:
        print(f"\n{'='*50}")
        print(f"配置: {profile}")
        print('='*50)

        # 加载chunks
        chunk_file = chunk_dir / f"{profile}.jsonl"
        if not chunk_file.exists():
            print(f"[SKIP] {chunk_file} 不存在")
            continue

        chunks = load_chunks(chunk_file)
        print(f"  Chunks: {len(chunks)}")

        # 加载gold mapping
        gold_mapping = load_gold_mapping(Path(args.gold_dir), profile)
        print(f"  Gold映射: {len(gold_mapping)} 道题")

        # 检索评测
        results = []
        for q in questions:
            # 兼容不同字段名
            question_text = q.get('question') or q.get('evidence_text', '')
            question_id = q.get('id') or q.get('evidence_id', 'unknown')

            # 模拟检索
            retrieved_indices = simulate_vector_retrieval(chunks, question_text, top_k=10)

            # 评估
            gold_ids = gold_mapping.get(question_id, [])
            metrics = evaluate(retrieved_indices, gold_ids, chunks)

            results.append({
                'question_id': question_id,
                'question': question_text,
                'retrieved_chunk_ids': [chunks[i]['chunk_id'] for i in retrieved_indices if i < len(chunks)],
                **metrics
            })

        # 汇总
        n = len(results)
        summary = {
            'profile': profile,
            'total_questions': n,
            'chunk_count': len(chunks),
            'hit_at_1': sum(r['hit_at_1'] for r in results) / n if n > 0 else 0,
            'hit_at_5': sum(r['hit_at_5'] for r in results) / n if n > 0 else 0,
            'hit_at_10': sum(r['hit_at_10'] for r in results) / n if n > 0 else 0,
            'mrr': sum(r['mrr'] for r in results) / n if n > 0 else 0
        }

        print(f"\n  结果:")
        print(f"    Hit@1:  {summary['hit_at_1']:.3f}")
        print(f"    Hit@5:  {summary['hit_at_5']:.3f}")
        print(f"    Hit@10: {summary['hit_at_10']:.3f}")
        print(f"    MRR:    {summary['mrr']:.3f}")

        # 保存
        output_file = output_dir / f"vector_simulated_{profile}_v02.json"
        output = {
            'summary': summary,
            'details': results,
            'note': '模拟结果，用于流程验证，非真实向量检索'
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"  [OK] 保存: {output_file.name}")

    print(f"\n{'='*50}")
    print("[OK] 向量检索流程验证完成")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
