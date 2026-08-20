"""Render selected PDF pages and run a reproducible PaddleOCR 3.x smoke test.

All page numbers exposed by this script are one-based physical PDF pages. The
zero-based PDFium index is recorded separately to prevent citation drift.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


if os.name == "nt" and sys.flags.utf8_mode == 0:
    # Paddle returns Unicode, but parts of the Windows result pipeline can use
    # the active legacy code page. Relaunch before importing Paddle so saved
    # JSON/TXT never contains UTF-8 bytes decoded as Latin-1/GBK.
    utf8_env = os.environ.copy()
    utf8_env["PYTHONUTF8"] = "1"
    completed = subprocess.run([sys.executable, *sys.argv], env=utf8_env, check=False)
    raise SystemExit(completed.returncode)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = PROJECT_ROOT / ".cache"
DETECTION_MODEL = "PP-OCRv5_mobile_det"
RECOGNITION_MODEL = "PP-OCRv5_mobile_rec"

# PaddleX defaults to ~/.paddlex. Set its cache before importing PaddleOCR so
# model downloads remain inside the E: workspace.
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(CACHE_ROOT / "paddlex"))
os.environ.setdefault("HF_HOME", str(CACHE_ROOT / "huggingface"))
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("TEMP", str(CACHE_ROOT / "temp"))
os.environ.setdefault("TMP", str(CACHE_ROOT / "temp"))

try:
    import paddle
    import paddleocr
    import pypdfium2 as pdfium
    from paddleocr import PaddleOCR
except ImportError as exc:
    raise SystemExit(
        "OCR依赖不完整。请使用项目环境 .venv-ocr\\Scripts\\python.exe 运行。"
    ) from exc


def parse_pages(spec: str) -> list[int]:
    """Parse one-based pages such as ``1,3,5-8`` while preserving order."""
    pages: list[int] = []
    seen: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"页码范围起点大于终点: {part}")
            candidates: Iterable[int] = range(start, end + 1)
        else:
            candidates = (int(part),)
        for page in candidates:
            if page < 1:
                raise ValueError(f"PDF物理页码必须从1开始: {page}")
            if page not in seen:
                seen.add(page)
                pages.append(page)
    if not pages:
        raise ValueError("没有提供有效页码")
    return pages


def render_page(
    pdf: pdfium.PdfDocument,
    pdf_page: int,
    scale: float,
    image_path: Path,
) -> tuple[int, int]:
    """Render a one-based physical PDF page and return image width/height."""
    pdf_index = pdf_page - 1
    if pdf_index >= len(pdf):
        raise ValueError(f"PDF物理页码{pdf_page}超出范围1-{len(pdf)}")

    page = pdf[pdf_index]
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil().convert("RGB")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(image_path, format="PNG")
    width, height = image.size
    bitmap.close()
    page.close()
    return width, height


def result_payload(result: Any) -> dict[str, Any]:
    """Convert one PaddleOCR 3.x result into JSON-safe fields."""
    data = result.json["res"]
    return {
        "rec_texts": data.get("rec_texts", []),
        "rec_scores": data.get("rec_scores", []),
        "rec_boxes": data.get("rec_boxes", []),
        "rec_polys": data.get("rec_polys", []),
        "textline_orientation_angles": data.get(
            "textline_orientation_angles", []
        ),
        "text_det_params": data.get("text_det_params", {}),
        "model_settings": data.get("model_settings", {}),
    }


def write_page_outputs(
    *,
    output_dir: Path,
    pdf_path: Path,
    pdf_page: int,
    scale: float,
    image_size: tuple[int, int],
    elapsed_seconds: float,
    results: list[Any],
) -> tuple[Path, Path, int]:
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    payloads = [result_payload(result) for result in results]
    rec_texts = [
        text
        for payload in payloads
        for text in payload["rec_texts"]
        if isinstance(text, str) and text.strip()
    ]

    base = f"page_{pdf_page:03d}"
    json_path = pages_dir / f"{base}_ocr.json"
    text_path = pages_dir / f"{base}_ocr.txt"
    output = {
        "document_id": output_dir.name,
        "source_pdf": pdf_path.name,
        "pdf_page": pdf_page,
        "pdf_index": pdf_page - 1,
        "printed_page": None,
        "render": {
            "scale": scale,
            "width": image_size[0],
            "height": image_size[1],
        },
        "engine": {
            "paddlepaddle": paddle.__version__,
            "paddleocr": paddleocr.__version__,
            "device": "cpu",
            "text_detection_model": DETECTION_MODEL,
            "text_recognition_model": RECOGNITION_MODEL,
        },
        "elapsed_seconds": round(elapsed_seconds, 3),
        "line_count": len(rec_texts),
        "results": payloads,
    }
    json_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text_path.write_text("\n".join(rec_texts), encoding="utf-8")
    return json_path, text_path, len(rec_texts)


def build_ocr_engine() -> PaddleOCR:
    return PaddleOCR(
        device="cpu",
        text_detection_model_name=DETECTION_MODEL,
        text_recognition_model_name=RECOGNITION_MODEL,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="PaddleOCR 3.x PDF抽样测试")
    parser.add_argument("--input", "-i", required=True, type=Path)
    parser.add_argument("--pages", "-p", required=True)
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=2.5)
    args = parser.parse_args()

    pdf_path = args.input.resolve()
    output_dir = args.output.resolve()
    if not pdf_path.is_file():
        parser.error(f"输入PDF不存在: {pdf_path}")
    if args.scale <= 0:
        parser.error("scale必须大于0")

    try:
        pages = parse_pages(args.pages)
    except ValueError as exc:
        parser.error(str(exc))

    for path in (
        CACHE_ROOT / "paddlex",
        CACHE_ROOT / "huggingface",
        CACHE_ROOT / "temp",
        output_dir / "pages",
        output_dir / "rendered",
    ):
        path.mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(str(pdf_path))
    invalid = [page for page in pages if page > len(pdf)]
    if invalid:
        parser.error(f"页码超出PDF总页数{len(pdf)}: {invalid}")

    print(f"PDF: {pdf_path}")
    print(f"PDF总页数: {len(pdf)}")
    print(f"待识别物理页: {pages}")
    print(f"PaddleX缓存: {os.environ['PADDLE_PDX_CACHE_HOME']}")
    print("初始化PaddleOCR 3.x（首次运行会下载模型）...")
    engine = build_ocr_engine()

    failures = 0
    for pdf_page in pages:
        image_path = output_dir / "rendered" / f"page_{pdf_page:03d}.png"
        try:
            image_size = render_page(pdf, pdf_page, args.scale, image_path)
            started = time.perf_counter()
            results = list(engine.predict(str(image_path)))
            elapsed = time.perf_counter() - started
            json_path, text_path, line_count = write_page_outputs(
                output_dir=output_dir,
                pdf_path=pdf_path,
                pdf_page=pdf_page,
                scale=args.scale,
                image_size=image_size,
                elapsed_seconds=elapsed,
                results=results,
            )
            print(
                f"页{pdf_page}: {line_count}行, {elapsed:.2f}s, "
                f"{json_path.name}, {text_path.name}"
            )
        except Exception as exc:  # Continue so one bad page does not lose all work.
            failures += 1
            print(f"页{pdf_page}失败: {type(exc).__name__}: {exc}", file=sys.stderr)

    pdf.close()
    if failures:
        print(f"完成，但有{failures}页失败。", file=sys.stderr)
        return 1
    print("全部抽样页识别完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
