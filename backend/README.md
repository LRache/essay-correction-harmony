# 智能作文批改系统后端

本目录包含基于 FastAPI、SQLite、NLTK 和 Hugging Face Transformers 构建的中文作文批改后端，为 HarmonyOS ArkTS 客户端提供接口。

## 安装与运行

安装后端、本地模型和开发依赖：

```bash
uv sync --extra ai --extra dev
```

启动服务：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

默认演示账号：

- 学生：`student@example.com` / `student123`
- 教师：`teacher@example.com` / `teacher123`

## 批改方式

系统提供以下两种分析方式：

- `local-nlp`：NLTK 语法检查 + Hugging Face 中文 BERT 语义分析与作文评分。
- `openai-compatible`：调用 Moonshot 等兼容 OpenAI Chat Completions 协议的外部 API。

## 配置外接 API

复制 `.env.example` 为 `.env`，填写外部模型配置：

```dotenv
AI_PROVIDER=openai-compatible
AI_BASE_URL=https://api.example.com/v1
AI_API_KEY=你的密钥
AI_MODEL=模型名称

# 如果本地 VPN 或代理影响目标 API 的 TLS 连接，可设置绕过地址
NO_PROXY=api.example.com
```

系统环境变量的优先级高于 `.env` 文件。

外部模型返回内容会经过 Pydantic 数据结构校验。请求失败或返回格式不正确时，系统会回退到本地分析链路，并在报告的 `provider.errors` 中记录原因。外接 API 功能不会因本地模型的加入而被移除。

## 配置 NLTK 与中文 BERT

本地模型依赖通过以下命令安装：

```bash
uv sync --extra ai --extra dev
```

默认使用轻量中文模型 `uer/chinese_roberta_L-2_H-128`。可在 `.env` 中修改：

```dotenv
LOCAL_BERT_MODEL=uer/chinese_roberta_L-2_H-128
LOCAL_MODEL_FILES_ONLY=true
LOCAL_MODEL_WARMUP=true
LOCAL_SCORING_MODEL=./models/aes-scorer
LOCAL_GRAMMAR_MODEL=./models/grammar-detector
```

配置说明：

- `LOCAL_BERT_MODEL`：Hugging Face 模型名称或本地模型目录。
- `LOCAL_MODEL_FILES_ONLY`：设为 `true` 时仅加载本地文件，不访问 Hugging Face。
- `LOCAL_MODEL_WARMUP`：启动后端时预先加载模型，避免首次批改承担模型加载时间。
- `LOCAL_SCORING_MODEL`：经过人工评分数据微调后的作文评分模型目录。
- `LOCAL_GRAMMAR_MODEL`：经过中文纠错语料微调后的字符位置检测模型目录。

创建分析任务时提交以下参数即可使用本地模型：

```json
{
  "provider": "local-nlp"
}
```

模型会缓存在后端进程中。报告会明确展示实际使用的模型、处理耗时、是否发生降级以及错误原因。

## 准备公开作文数据集

项目不会直接重新分发第三方学生作文。请在确认数据集许可证和使用权限后，使用转换脚本生成统一格式。

转换普通 CSV、JSON 或 JSONL 数据：

```bash
uv run python scripts/prepare_dataset.py \
  --input path/to/public-corpus.jsonl \
  --output data/evaluation.csv
```

转换 AES-Dataset：

```bash
git clone https://github.com/declan-haojin/AES-Dataset.git .cache/datasets/AES-Dataset
uv run python scripts/prepare_dataset.py \
  --aes-root .cache/datasets/AES-Dataset \
  --output data/aes-evaluation.csv
```

统一数据字段为：

- `title`：作文标题。
- `prompt`：作文要求。
- `content`：学生作文正文。
- `corrected_content`：人工修改后的正文。
- `human_score`：人工评分。
- `grammar_spans`：语法错误位置标注。

脚本兼容 YACLC/YACSC 风格的 `source` 和 `target` 字段。如果数据只有原文和修改后文本，脚本会自动推导发生变化的字符区间。

`grammar_spans` 使用 JSON 格式，例如：

```json
[[12, 14], {"start": 30, "end": 34}]
```

## 训练作文评分模型

使用包含人工分数的统一数据集微调 BERT 回归评分器：

```bash
uv run python scripts/train_scorer.py \
  data/aes-evaluation.csv \
  --output models/aes-scorer
```

训练脚本会划分训练集和验证集，并在 `models/aes-scorer/evaluation.json` 中保存训练数量、验证数量和验证集 Pearson 相关系数。

评分器会同时编码作文要求和正文。长作文按重叠窗口分段，模型分别评分后聚合为整篇分数，不会直接丢弃512 token之后的内容。

## 训练语病位置检测模型

下载 YACLC、YACSC 和 FlaCGEC 后，生成互不泄漏的训练、验证和独立测试集：

```bash
uv run python scripts/prepare_grammar_dataset.py \
  --yaclc .cache/datasets/YACLC \
  --yacsc .cache/datasets/yacsc \
  --flacgec .cache/datasets/FlaCGEC \
  --output .cache/datasets/grammar
```

训练字符位置级 BERT 检测器：

```bash
uv run python scripts/train_grammar_detector.py \
  .cache/datasets/grammar \
  --output models/grammar-detector
```

模型只使用 YACLC 与 FlaCGEC 训练，YACSC 始终作为独立测试集。评测同时输出准确率、精确率、召回率和错误类F1，避免仅凭大量正常字符制造虚高准确率。

## 验收指标评测

运行以下命令计算语法检测准确率、模型评分相关系数和批改耗时：

```bash
uv run python scripts/evaluate.py \
  data/evaluation.csv \
  --provider local-nlp
```

评测结果包括：

- 语法错误字符区间检测准确率。
- 模型评分与人工评分的 Pearson、Spearman 相关系数。
- 单篇作文批改耗时的 p50、p95。
- 语法准确率是否达到 90%。
- Pearson 相关系数是否达到 0.7。
- p95 批改耗时是否低于 2000 毫秒。

若希望任一指标不达标时使命令返回失败，可添加：

```bash
--fail-below-target
```

所有指标均根据输入的真实标注数据计算，不会使用写死的结果。

## 运行自动化测试

```bash
uv run pytest -q
```
