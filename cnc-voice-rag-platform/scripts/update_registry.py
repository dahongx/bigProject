"""
更新文档登记表
"""

import csv
from pathlib import Path
import hashlib


def calculate_file_hash(file_path):
    """计算文件SHA256哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


# 更新DOC004信息
pdf_path = Path("data/raw/FANUC数控编程手册_杜军_化工出版社.pdf")

if pdf_path.exists():
    file_hash = calculate_file_hash(pdf_path)
    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)

    print(f"文件: {pdf_path.name}")
    print(f"大小: {file_size_mb:.2f} MB")
    print(f"SHA256: {file_hash}")
    print()
    print("请手动更新 data/manifests/document_registry.csv")
else:
    print(f"错误: 文件不存在 {pdf_path}")
