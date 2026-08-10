"""
文档解析工具
将PDF、Word等格式转换为统一的结构化格式
"""

import argparse
from pathlib import Path
import json
from typing import Dict, List
import fitz  # PyMuPDF

def parse_pdf(pdf_path: Path) -> Dict:
    """
    解析PDF文档

    Args:
        pdf_path: PDF文件路径

    Returns:
        包含文档内容和元数据的字典
    """
    doc = fitz.open(pdf_path)

    result = {
        "filename": pdf_path.name,
        "total_pages": len(doc),
        "metadata": doc.metadata,
        "pages": []
    }

    for page_num, page in enumerate(doc, start=1):
        page_data = {
            "page_number": page_num,
            "text": page.get_text("text"),
            "blocks": []
        }

        # 提取文本块
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # 文本块
                page_data["blocks"].append({
                    "type": "text",
                    "bbox": block["bbox"],
                    "text": " ".join([
                        span["text"] for line in block["lines"]
                        for span in line["spans"]
                    ])
                })

        result["pages"].append(page_data)

    doc.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="解析数控技术文档")
    parser.add_argument("input", type=str, help="输入PDF文件路径")
    parser.add_argument("-o", "--output", type=str, help="输出JSON文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}")
        return

    print(f"正在解析: {input_path}")
    result = parse_pdf(input_path)

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path("data/parsed") / f"{input_path.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 保存结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"解析完成，共 {result['total_pages']} 页")
    print(f"输出保存至: {output_path}")


if __name__ == "__main__":
    main()
