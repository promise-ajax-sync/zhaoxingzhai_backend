# 昭星斋后端

独立于 Flutter 客户端的 Python 3.12 / FastAPI 服务。负责安全持有 AI 密钥、构造权威提示词、调用模型并提供本地降级；PostgreSQL 配置已预留，后续用于用户、案例、占卜记录和 AI 生成记录。

## 本地启动

```powershell
cd E:\newProject\fluttersm\zhaoxingzhai_backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

开发时也可以使用固定主机和端口的启动脚本：

```powershell
.\scripts\run_dev.ps1
```

该脚本固定启动在 `http://127.0.0.1:8000`。

打开：

- 健康检查：`http://127.0.0.1:8000/health`
- 开发文档：`http://127.0.0.1:8000/docs`

未配置 `AI_API_KEY` 和 `AI_MODEL` 时，`POST /api/v1/interpret` 会返回 Flutter 已生成的本地结构化回答，便于先完成前后端联调。

## 配置 AI

复制 `.env.example` 为 `.env`，填写：

```dotenv
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=your-server-side-key
AI_MODEL=your-model
```

密钥只放在后端 `.env` 或部署平台的加密环境变量中，不得提交 Git，也不得下发给 Flutter。

## 测试

```powershell
pytest
```

## AI 解读质量回归

离线评测不请求远程模型，也不需要 AI Key：

```powershell
python scripts/evaluate_interpretation_quality.py
```

固定样本位于 `evals/interpretation_cases.json`，当前覆盖梅花易数、塔罗、小六壬、灵签和每日一卦。评估器会检查问题回应、证据落地、编造内容、绝对化断言、空泛建议、生活类收尾及高风险问题的专业边界。

每次修改提示词或结构化回答规则后，应同时运行离线质量评测和完整 `pytest`。

真实模型回答可以手动保存后再评分，不会再次请求模型：

```powershell
Copy-Item evals\saved_outputs.example.json evals\saved_outputs.local.json
# 将真实接口响应中的 reading、modelId 和 promptVersion 填入 local 文件
python scripts\evaluate_saved_interpretations.py evals\saved_outputs.local.json
```

每项必须包含与固定样本对应的 `caseId` 和结构化 `reading`。建议把个人评测文件命名为 `*.local.json`，不要在其中保存 API Key、Authorization、用户邮箱或其他敏感资料。

## PostgreSQL 建表

安装开发依赖并执行正式迁移：

```powershell
python -m pip install -e ".[dev]"
alembic upgrade head
```

如果只需要按当前模型创建缺失的数据表并验证结果：

```powershell
python scripts/create_tables.py
```

成功时输出 `users`、`cases`、`divination_records` 和 `ai_interpretations`。迁移脚本不会读取或打印数据库密码。

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## 当前接口

### `POST /api/v1/interpret`

请求结构与 Flutter 的 `AiInterpretationRequest.toJson()` 一致；响应结构与 `AiInterpretationResponse` 一致。

当前支持 OpenAI Chat Completions 兼容接口。后续增加其他供应商时，仅新增 provider 适配器，不修改 Flutter 协议。

### 历史同步接口

以下接口要求请求头 `X-Device-ID`。后端只保存设备标识的 HMAC 哈希：

```text
POST   /api/v1/records
GET    /api/v1/records
GET    /api/v1/records/{id}
DELETE /api/v1/records/{id}
PUT    /api/v1/records/{id}/ai-interpretation
```

相同设备、相同 `clientRecordId` 再次上传时更新原记录；删除采用软删除。Flutter 仍以本地历史为主，云端同步失败不会阻断起卦或查看结果。

## Flutter 开发地址

- Windows、Web：`http://127.0.0.1:8000`
- Android 模拟器访问电脑：`http://10.0.2.2:8000`
- 真机：使用电脑在局域网中的 IP，并确保防火墙允许访问 8000 端口

Flutter 使用 `--dart-define` 指定地址，例如：

```powershell
flutter run -d windows --dart-define=AI_BACKEND_URL=http://127.0.0.1:8000
```

开发配置允许 Flutter Web 随机端口跨域访问。生产环境必须把 `APP_CORS_ORIGINS` 改成正式 HTTPS 域名，并增加用户鉴权和限流。

## 接口保护

`POST /api/v1/interpret` 当前具备：

- 每个客户端在固定时间窗口内的基础限流，默认每 60 秒 20 次。
- 基于 `Content-Length` 的请求大小预检，默认上限 128 KiB。
- `X-Request-ID` 请求追踪；响应始终返回该标识。
- 脱敏访问日志，只记录请求 ID、方法、路径、状态码和耗时，不记录问题正文、请求体、查询参数、Authorization 或 API Key。

相关环境变量：

```dotenv
APP_MAX_REQUEST_BYTES=131072
APP_RATE_LIMIT_REQUESTS=20
APP_RATE_LIMIT_WINDOW_SECONDS=60
APP_TRUST_PROXY_HEADERS=false
APP_DEVICE_HASH_SECRET=replace-with-a-long-random-secret
```

当前限流器保存在单个服务进程内。生产环境若运行多个实例，应替换为 Redis 等共享限流存储。只有在可信反向代理会清洗并重写 `X-Forwarded-For` 时，才可启用 `APP_TRUST_PROXY_HEADERS`。

`APP_DEVICE_HASH_SECRET` 用于对匿名设备标识进行 HMAC 哈希，数据库不会保存 Flutter 发送的原始设备标识。生产环境必须替换为随机长字符串并妥善保管。
