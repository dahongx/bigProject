# OCR环境配置指南

更新日期：2026年8月13日

## 环境路径

```
cnc-voice-rag-platform/
├── .venv-ocr/          # 虚拟环境
└── .cache/             # 所有缓存
    ├── pip/
    ├── huggingface/
    └── temp/
```

## 安装步骤

### 1. 激活虚拟环境

```powershell
cd E:\big\cnc-voice-rag-platform
.\.venv-ocr\Scripts\Activate.ps1
```

### 2. 设置缓存路径

```powershell
$env:PIP_CACHE_DIR = "E:\big\cnc-voice-rag-platform\.cache\pip"
$env:HF_HOME = "E:\big\cnc-voice-rag-platform\.cache\huggingface"
$env:TEMP = "E:\big\cnc-voice-rag-platform\.cache\temp"
$env:TMP = "E:\big\cnc-voice-rag-platform\.cache\temp"
```

### 3. 安装PaddlePaddle

**请根据实际情况选择版本**：

```powershell
# CPU版本（推荐先用这个测试）
python -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# 如果有CUDA GPU，参考官方文档选择GPU版本
```

参考文档：https://www.paddlepaddle.org.cn/install/quick

### 4. 安装PaddleOCR 3.x

```powershell
python -m pip install paddleocr>=3.0.0
```

### 5. 安装其他依赖

```powershell
pip install pypdfium2
pip install pillow
pip install pyyaml
pip install tqdm
pip install rank-bm25
pip install jieba
```

### 6. 验证安装

```powershell
python -c "import paddleocr; print('PaddleOCR version:', paddleocr.__version__)"
python -c "import pypdfium2; print('pypdfium2 OK')"
python -c "import paddle; print('PaddlePaddle version:', paddle.__version__)"
```

## 模型缓存

首次运行PaddleOCR会自动下载模型：
- 中文检测模型
- 中文识别模型
- 方向分类模型

**注意**：观察模型实际下载位置，如果下载到C盘，需要手动配置模型路径。

## 常见问题

### Q: PaddlePaddle安装失败
- 检查Python版本（建议3.8-3.11）
- 尝试使用清华镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple`

### Q: 模型下载到C盘
- 设置环境变量后重新运行
- 或手动下载模型到 `.cache/paddleocr/`

### Q: 虚拟环境激活失败
- PowerShell执行策略问题，运行：
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

## 下一步

环境配置完成后，运行：
```powershell
python scripts/ocr_test.py --help
```
