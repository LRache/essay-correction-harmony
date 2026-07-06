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

AI 接入预留环境变量：

```bash
AI_PROVIDER=openai-compatible
AI_BASE_URL=https://api.example.com/v1
AI_API_KEY=...
AI_MODEL=...
```

未配置 AI 时默认使用 deterministic mock + 轻量规则分析。

## Harmony

```bash
cd harmony/EssayCorrection
DEVECO_HOME=/Applications/DevEco-Studio.app/Contents \
DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk \
/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw assembleApp --no-daemon
```

ArkTS 端默认请求 `http://127.0.0.1:8000`。后端不可用时会回退到本地演示数据，方便先看页面闭环。
