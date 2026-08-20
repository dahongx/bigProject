"""
应用人工复核修订到来源块

从data_review_queue_v0.2.csv读取复核结果，生成reviewed版本的blocks
"""

import json
import csv
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def load_original_blocks(blocks_path: Path) -> Dict[str, dict]:
    """加载原始blocks，按block_id索引"""
    blocks = {}
    with open(blocks_path, 'r', encoding='utf-8') as f:
        for line in f:
            block = json.loads(line)
            blocks[block['block_id']] = block
    return blocks


def load_review_queue(csv_path: Path) -> List[dict]:
    """加载复核队列"""
    reviews = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            reviews.append(row)
    return reviews


def apply_corrections(blocks: Dict[str, dict], reviews: List[dict]) -> Dict[str, dict]:
    """
    应用修订

    返回：修订后的blocks字典
    """
    corrected = {}

    for block_id, block in blocks.items():
        # 复制原block
        new_block = block.copy()

        # 查找对应的review
        review = None
        for r in reviews:
            if r['block_id'] == block_id and r['review_status'] == 'reviewed':
                review = r
                break

        if review:
            # 应用修订
            if review.get('corrected_text', '').strip():
                new_block['text'] = review['corrected_text'].strip()
                new_block['correction_applied'] = True
                new_block['original_text'] = block['text']
                new_block['review_note'] = review.get('review_note', '')

            if review.get('corrected_title_path', '').strip():
                new_block['title_path'] = review['corrected_title_path'].strip()

        corrected[block_id] = new_block

    return corrected


def main():
    """主流程"""
    import argparse

    parser = argparse.ArgumentParser(description='应用人工复核修订')
    parser.add_argument('--blocks', required=True, help='原始blocks文件')
    parser.add_argument('--review-queue', required=True, help='复核队列CSV')
    parser.add_argument('--output', required=True, help='输出文件')

    args = parser.parse_args()

    blocks_path = Path(args.blocks)
    review_path = Path(args.review_queue)
    output_path = Path(args.output)

    print(f"加载原始blocks: {blocks_path}")
    blocks = load_original_blocks(blocks_path)
    print(f"  共 {len(blocks)} 个blocks")

    print(f"\n加载复核队列: {review_path}")
    reviews = load_review_queue(review_path)
    reviewed = [r for r in reviews if r['review_status'] == 'reviewed']
    print(f"  共 {len(reviews)} 条记录")
    print(f"  已复核: {len(reviewed)} 条")

    print("\n应用修订...")
    corrected = apply_corrections(blocks, reviews)

    # 统计
    applied_count = sum(1 for b in corrected.values() if b.get('correction_applied'))
    print(f"  应用修订: {applied_count} 个blocks")

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for block in corrected.values():
            f.write(json.dumps(block, ensure_ascii=False) + '\n')

    print(f"\n✓ 已保存: {output_path}")

    # 生成报告
    report = {
        'timestamp': datetime.now().isoformat(),
        'original_blocks': len(blocks),
        'reviewed_items': len(reviewed),
        'corrections_applied': applied_count,
        'output_file': str(output_path),
        'input_files': {
            'blocks': str(blocks_path),
            'review_queue': str(review_path)
        }
    }

    report_path = output_path.parent / 'correction_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✓ 报告: {report_path}")


if __name__ == "__main__":
    main()
