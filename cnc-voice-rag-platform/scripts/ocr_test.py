"""
OCR测试脚本 - PaddleOCR 3.x版本

用于提取PDF指定页面并进行OCR识别
"""

import sys
import argparse
from pathlib import Path
import json
import time

try:
    import pypdfium2 as pdfium
    from paddleocr import PaddleOCR
    import numpy as np
except ImportError as e:
    print(f"缺少依赖库: {e}")
    print("请先激活虚拟环境并安装依赖:")
    print("  .venv-ocr\\Scripts\\Activate.ps1")
    print("  pip install pypdfium2 paddleocr")
    sys.exit(1)


def render_pdf_page(pdf_path, page_num, scale=2.0):
    """
    渲染PDF页面为图片

    Args:
        pdf_path: PDF文件路径
        page_num: 页码（从1开始）
        scale: 渲染倍数，越高越清晰

    Returns:
        PIL Image对象和NumPy数组
    """
    pdf = pdfium.PdfDocument(pdf_path)

    # pypdfium2索引从0开始
    pdf_index = page_num - 1

    if pdf_index < 0 or pdf_index >= len(pdf):
        raise ValueError(f"页码 {page_num} 超出范围 (1-{len(pdf)})")

    page = pdf[pdf_index]
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()

    # 转换为NumPy数组（PaddleOCR推荐格式）
    np_image = np.array(pil_image)

    return pil_image, np_image


def ocr_page(image, ocr_engine):
    """
    对图片进行OCR识别

    Args:
        image: NumPy数组格式的图片
        ocr_engine: PaddleOCR对象

    Returns:
        OCR识别结果
    """
    # PaddleOCR 3.x接口
    result = ocr_engine.predict(image)
    return result


def save_ocr_result(result, output_path, page_num, pdf_index):
    """
    保存OCR原始结果

    Args:
        result: OCR结果对象
        output_path: 输出JSON文件路径
        page_num: 页码（从1开始）
        pdf_index: PDF索引（从0开始）
    """
    # 转换为可序列化格式
    serializable_result = {
        "pdf_page": page_num,
        "pdf_index": pdf_index,
        "ocr_raw": str(result),  # 先转为字符串，后续再解析
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_result, f, ensure_ascii=False, indent=2)

    print(f"✓ OCR结果已保存到: {output_path}")


def extract_text_from_result(result):
    """
    从OCR结果中提取纯文本

    Args:
        result: OCR结果对象

    Returns:
        提取的文本字符串
    """
    # PaddleOCR 3.x结果结构可能不同，这里需要根据实际返回调整
    try:
        # 尝试提取文本（具体方法需要根据实际结果对象调整）
        text_lines = []
        # TODO: 根据实际PaddleOCR 3.x返回格式提取文本
        return "\n".join(text_lines)
    except Exception as e:
        print(f"警告: 文本提取失败: {e}")
        return str(result)


def main():
    parser = argparse.ArgumentParser(description='OCR测试 - 提取PDF页面并识别')
    parser.add_argument('--input', '-i', required=True, help='输入PDF文件路径')
    parser.add_argument('--pages', '-p', required=True, help='页码，例如: 1,3,5-8')
    parser.add_argument('--output', '-o', default='data/parsed', help='输出目录')
    parser.add_argument('--scale', type=float, default=2.0, help='渲染倍数（默认2.0）')

    args = parser.parse_args()

    # 检查输入文件
    pdf_path = Path(args.input)
    if not pdf_path.exists():
        print(f"错误: 文件不存在 {pdf_path}")
        sys.exit(1)

    # 创建输出目录
    output_dir = Path(args.output)
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # 解析页码范围
    page_numbers = []
    for part in args.pages.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            page_numbers.extend(range(start, end + 1))
        else:
            page_numbers.append(int(part))

    print(f"准备处理 {len(page_numbers)} 页: {page_numbers}")
    print(f"输入文件: {pdf_path}")
    print(f"输出目录: {output_dir}")
    print()

    # 初始化OCR引擎（只初始化一次）
    print("初始化PaddleOCR引擎...")
    ocr = PaddleOCR(
        lang="ch",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        show_log=False
    )
    print("✓ OCR引擎初始化完成")
    print()

    # 处理每一页
    for page_num in page_numbers:
        print(f"处理第 {page_num} 页...")

        try:
            # 渲染PDF页面
            pil_image, np_image = render_pdf_page(str(pdf_path), page_num, args.scale)
            print(f"  ✓ 页面渲染完成 (尺寸: {np_image.shape})")

            # OCR识别
            start_time = time.time()
            result = ocr_page(np_image, ocr)
            elapsed = time.time() - start_time
            print(f"  ✓ OCR识别完成 (耗时: {elapsed:.2f}秒)")

            # 保存结果
            pdf_index = page_num - 1
            output_file = pages_dir / f"page_{page_num:03d}_ocr.json"
            save_ocr_result(result, output_file, page_num, pdf_index)

            # 提取并显示部分文本
            text = extract_text_from_result(result)
            preview = text[:100] if text else "(无法提取文本)"
            print(f"  文本预览: {preview}...")
            print()

        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 60)
    print(f"处理完成！共处理 {len(page_numbers)} 页")
    print(f"结果保存在: {pages_dir}")
    print()
    print("下一步:")
    print("1. 检查 pages/*.json 查看OCR原始结果")
    print("2. 人工评估识别质量")
    print("3. 如果质量合格，扩展到更多页面")


if __name__ == "__main__":
    main()
