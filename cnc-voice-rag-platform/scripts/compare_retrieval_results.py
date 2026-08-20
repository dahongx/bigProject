"""
对比BM25和向量检索结果

生成完整的对比分析报告
"""

import json
from pathlib import Path
from typing import Dict, List
import pandas as pd


def load_result(path: Path) -> Dict:
    """加载检索结果"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compare_methods(bm25_results: Dict, results_dir: Path, profile: str) -> Dict:
    """对比BM25和向量检索"""

    # 查找向量结果（可能是模拟的）
    vector_file = results_dir / f"vector_simulated_{profile}_v02.json"
    if not vector_file.exists():
        return None

    vector_results = load_result(vector_file)

    # 提取指标（兼容不同格式）
    bm25_summary = bm25_results.get('summary') or bm25_results
    vector_summary = vector_results.get('summary') or vector_results

    comparison = {
        'profile': profile,
        'methods': {
            'BM25': {
                'hit_at_1': bm25_summary.get('hit@1', 0),
                'hit_at_5': bm25_summary.get('hit@5', 0),
                'hit_at_10': bm25_summary.get('hit@10', 0),
                'mrr': bm25_summary.get('mrr', 0)
            },
            'Vector': {
                'hit_at_1': vector_summary.get('hit_at_1', 0),
                'hit_at_5': vector_summary.get('hit_at_5', 0),
                'hit_at_10': vector_summary.get('hit_at_10', 0),
                'mrr': vector_summary.get('mrr', 0)
            }
        }
    }

    return comparison


def generate_comparison_table(comparisons: List[Dict]) -> str:
    """生成对比表格（Markdown）"""

    lines = [
        "# BM25 vs 向量检索对比",
        "",
        "## 整体指标",
        "",
        "| 切块配置 | 方法 | Hit@1 | Hit@5 | Hit@10 | MRR |",
        "|---------|------|-------|-------|--------|-----|"
    ]

    for comp in comparisons:
        profile = comp['profile']
        for method, metrics in comp['methods'].items():
            lines.append(
                f"| {profile:15} | {method:6} | "
                f"{metrics['hit_at_1']:.3f} | "
                f"{metrics['hit_at_5']:.3f} | "
                f"{metrics['hit_at_10']:.3f} | "
                f"{metrics['mrr']:.3f} |"
            )

    lines.extend([
        "",
        "## 分析",
        "",
        "### 当前状态",
        "- 向量检索使用字符级别的简单模拟，指标为0.000是预期结果",
        "- 实际向量检索需要BGE-M3模型",
        "",
        "### BM25结果",
        f"- 最优配置：{max(comparisons, key=lambda x: x['methods']['BM25']['mrr'])['profile']}",
        f"- 最高MRR：{max(c['methods']['BM25']['mrr'] for c in comparisons):.3f}",
        "",
        "### 下一步",
        "1. 安装sentence-transformers和faiss-cpu",
        "2. 下载BGE-M3模型",
        "3. 运行真实向量检索",
        "4. 实现混合检索（RRF融合）",
        ""
    ])

    return "\n".join(lines)


def main():
    """主流程"""
    results_dir = Path("experiments/results")

    profiles = [
        'fixed_t256_o51',
        'fixed_t512_o102',
        'fixed_t1024_o205',
        'structural_t512'
    ]

    comparisons = []

    for profile in profiles:
        bm25_file = results_dir / f"bm25_{profile}_v02_draft.json"

        if not bm25_file.exists():
            print(f"[SKIP] {bm25_file.name}")
            continue

        bm25_results = load_result(bm25_file)
        comp = compare_methods(bm25_results, results_dir, profile)

        if comp:
            comparisons.append(comp)
            print(f"[OK] {profile}")

    # 生成报告
    report_md = generate_comparison_table(comparisons)

    output_file = Path("experiments/reports/bm25_vs_vector_comparison.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_md)

    print(f"\n[OK] 对比报告: {output_file}")

    # 保存JSON
    json_file = output_file.with_suffix('.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'comparisons': comparisons,
            'note': '向量检索为模拟结果，需要真实模型'
        }, f, ensure_ascii=False, indent=2)

    print(f"[OK] JSON结果: {json_file}")


if __name__ == "__main__":
    main()
