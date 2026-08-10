# 架构与裁剪说明

## 上游调用链

上游语音链路的关键调用关系为：

1. `app.py` 启动HTTP与WebSocket服务。
2. `core/websocket_server.py` 初始化VAD、ASR和LLM，并为每个设备创建连接。
3. `core/connection.py` 接收Opus数据、解码为PCM、维护对话状态并调度ASR/LLM/TTS。
4. `core/handle/receiveAudioHandle.py` 调用VAD，检测语音结束后进入ASR。
5. `core/providers/asr/base.py` 完成音频缓存、识别和文本上送。
6. 识别文本进入 `ConnectionHandler.chat()`，再调用LLM。
7. LLM流式文本进入TTS队列，编码为Opus后回传ESP32。

## 论文平台建议保留

- `app.py`
- `config/`
- `core/websocket_server.py`
- `core/connection.py`
- `core/handle/`
- `core/providers/vad/silero.py`
- `core/providers/asr/base.py`及最终选定的一个ASR实现
- `core/providers/tts/base.py`及最终选定的一个TTS实现
- `core/providers/llm/openai/`，用于把CNC-RAG包装成OpenAI兼容服务
- 音频编解码和必要工具类

## 建议关闭或删除

在端到端基线跑通以后，再关闭或删除：

- VLLM视觉模块
- 声纹识别
- 长期记忆
- 音乐播放
- Home Assistant
- MCP与通用IoT控制
- 数字人
- 管理后台、移动端
- 未使用的ASR/TTS/LLM供应商适配器

## RAG接入方式

不建议直接依赖上游的RAGFlow插件作为论文算法主体。该插件本质上只是调用RAGFlow检索API并取前5个片段，难以进行可控的基线、消融和指标统计。

推荐把论文RAG实现为独立的OpenAI兼容服务：

```text
xiaozhi voice gateway -> /v1/chat/completions -> cnc-rag service
```

这样可在不修改ESP32通信和音频链路的情况下，自由替换：

- BM25；
- 向量检索；
- 混合检索；
- Cross-Encoder重排；
- 型号/版本元数据过滤；
- 引用与拒答策略。

## 第一阶段推荐配置

- 交互模式：按键说话，先不做持续唤醒。
- VAD：Silero VAD。
- ASR：先选一个稳定实现；本地部署可从FunASR开始。
- LLM：指向独立CNC-RAG服务。
- TTS：开发阶段可用Edge TTS；正式实验可换为稳定的本地或流式服务。
- Memory：关闭。
- Intent：关闭或只保留“下一步、重复、停止”。
- RAGFlow：不作为核心算法依赖。

## 安全边界

平台提供数控技术知识查询、操作指引和辅助排查，不直接向机床下发复位、参数修改、解除互锁或运动控制命令。高风险步骤必须显示并播报安全提示，必要时要求二次确认。
