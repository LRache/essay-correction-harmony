# 智能作文批改与辅导系统

本项目是一套面向中文作文教学的智能批改系统，包含 HarmonyOS ArkTS 客户端以及 FastAPI 后端。

系统支持三种批改方式：

- `local-nlp`：使用 NLTK 检测语法问题，并通过 Hugging Face 中文 BERT 分析文章连贯性、主题相关性和作文评分。
- `openai-compatible`：调用 Moonshot 等兼容 OpenAI 接口的外部大模型。
- `mock`：使用轻量规则快速生成演示报告。

## 项目结构

- `backend/`：FastAPI + SQLite 后端，包含用户登录、作文提交、智能分析、优秀范文、教师人工批改接口和模型评测工具。
- `harmony/EssayCorrection/`：HarmonyOS ArkTS 客户端，包含学生提交、报告查看、范文参考和教师批改管理。

## 启动后端

```bash
cd backend
uv sync --extra ai --extra dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后可访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

默认账号：

- 学生：`student@example.com` / `student123`
- 教师：`teacher@example.com` / `teacher123`

## 配置外接 API

复制 `backend/.env.example` 为 `backend/.env`，然后填写：

```dotenv
AI_PROVIDER=openai-compatible
AI_BASE_URL=https://api.example.com/v1
AI_API_KEY=你的密钥
AI_MODEL=模型名称
```

外接 API 与本地 NLTK/BERT 功能相互独立，可以在客户端中自由选择。

## 运行测试

```bash
cd backend
uv run pytest -q
```

本地模型、公开语料和量化评测的详细说明见 `backend/README.md`。

## HarmonyOS 客户端

使用 DevEco Studio 打开 `harmony/EssayCorrection`，根据电脑当前局域网地址修改：

`entry/src/main/ets/service/ApiClient.ets` 中的 `ApiClient.baseUrl`。

真机必须与后端电脑处于可互通的网络中。修改地址后重新编译并安装应用。
