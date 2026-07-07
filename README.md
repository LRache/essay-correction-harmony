# essay-correction-harmony

中文作文智能批改鸿蒙 App 首版原型，包含：

- `backend/`: FastAPI + SQLite 后端，提供学生提交、机器批改占位链路、范文、教师人工批改接口。
- `harmony/EssayCorrection/`: HarmonyOS ArkTS 页面壳，包含登录、作文提交、批改报告、范文参考、教师批改管理。

## Backend

```bash
cd backend
UV_CACHE_DIR="$PWD/.cache/uv" uv sync --extra dev
UV_CACHE_DIR="$PWD/.cache/uv" uv run pytest -q
UV_CACHE_DIR="$PWD/.cache/uv" uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

默认账号：

- 学生：`student@example.com` / `student123`
- 教师：`teacher@example.com` / `teacher123`

AI 接入预留环境变量。当前默认使用 LLM mock 报告，也可以显式配置模型名：

```bash
AI_PROVIDER=llm
AI_MODEL=demo-model
```

LLM mock 报告会生成随机评分，范文、评语、语法问题、改写建议、素材建议等字段都会按作文题目生成对应 mock 文案。分析完成后生成的范文会写入范文库，并在 App 的“范文” tab 中显示。需要旧版规则模板时设置 `AI_PROVIDER=mock`。

## Harmony

```bash
cd harmony/EssayCorrection
DEVECO_HOME=/Applications/DevEco-Studio.app/Contents \
DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk \
/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw assembleApp --no-daemon
```

ArkTS 端默认请求 `http://127.0.0.1:8000`。后端不可用时会回退到本地演示数据，方便先看页面闭环。
