# 成果影响力评价平台

一个前后端分离的科研成果影响力评价平台。用户可以按关键词查询已发布成果，也可以提交固定表单和材料；管理员负责材料入库、创建评价任务、运行 Codex Skill、审核 JSON 结果并发布报告。

## 功能

- 用户端：成果关键词联想、精确查询、固定表单提交、附件上传、需求记录。
- 管理端：需求受理、材料库、批量上传文件/文件夹/ZIP、评价任务、Pipeline、草稿审核、发布/撤回和审计日志。
- 评价链路：吴老师成果定位 → Search 核验或历史回放 → AI 贡献归因 → 吴老师评价 → v19 双层评价。
- MySQL 保存元数据和 JSON 结果；原始材料与过程底稿保存在 backend/storage 或 Docker volume。

## 快速启动（Windows）

需要 Python 3.13、Node.js 22 和 Docker Desktop。

    Copy-Item .env.example .env
    # 编辑 .env，至少修改 MYSQL_ROOT_PASSWORD、MYSQL_PASSWORD、SECRET_KEY
    docker compose up -d --build
    docker compose exec api python -m app.cli create-admin
    docker compose exec api python -m app.cli seed

访问 Web：http://localhost:18080；本地开发前端：http://localhost:5173；API 文档：http://127.0.0.1:8000/docs。

本地开发也可以使用 scripts/dev.ps1。首次创建管理员时默认用户名是 admin，密码由命令行提示设置；不要把真实密码提交到 Git。

## 配置 Codex

在运行 worker 的机器上安装并登录 Codex CLI，然后在 .env 中设置：

    EVALUATION_ADAPTER=codex
    CODEX_BINARY=codex
    CODEX_MODEL=gpt-6-astra
    CODEX_REASONING_EFFORT=medium
    CODEX_SEARCH=true

本地演示可使用 EVALUATION_ADAPTER=mock。API 和 worker 必须使用同一份 .env。不要提交 API key、Cookie、.env、.local-access.md 或 backend/storage 中的真实材料。

## 数据上传

管理员可以在“材料库”上传单文件或批量材料。支持 TXT、Markdown、PDF、DOCX、XLSX 和 ZIP；ZIP 会安全解压后逐个解析，前端支持选择文件夹。默认限制如下，可在 .env 调整：

    MAX_UPLOAD_MB=200
    BATCH_MAX_FILES=200
    BATCH_MAX_TOTAL_MB=2048
    ARCHIVE_MAX_EXPANDED_MB=5120

### API 登录和单文件上传

先登录获得 HttpOnly 会话 Cookie：

    curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"你的密码"}'

上传一个项目材料：

    curl -b cookies.txt -X POST http://127.0.0.1:8000/api/admin/materials -F "file=@./材料/项目说明.pdf"

### 批量上传文件、文件夹或 ZIP

批量接口逐项返回 accepted 和 rejected，单个文件失败不会影响其他文件：

    curl -b cookies.txt -X POST http://127.0.0.1:8000/api/admin/materials/batch -F "purpose=project" -F "files=@./材料/项目说明.pdf" -F "files=@./材料/实验数据.xlsx" -F "files=@./材料/整批材料.zip"

普通用户提交材料使用 /api/submission-materials/batch。上传成功后，使用返回的材料 id 创建评价任务或 Pipeline。项目原始材料标记为 project；参考结果和流程说明分别使用 reference、instruction。

## 常用 API

写操作需要同源请求，并使用登录后的会话 Cookie。

| 用途 | 方法 | 路径 |
| --- | --- | --- |
| 健康检查 | GET | /api/health |
| 登录/退出 | POST | /api/auth/login、/api/auth/logout |
| 查询已发布成果 | GET | /api/results |
| 关键词查询 | POST | /api/search |
| 用户提交固定表单 | POST | /api/submissions |
| 管理员概览 | GET | /api/admin/overview |
| 材料列表 | GET | /api/admin/materials |
| 创建评价任务 | POST | /api/admin/tasks |
| 任务列表/重试 | GET/POST | /api/admin/tasks、/api/admin/tasks/{id}/retry |
| 评价结果审核发布 | PUT/POST | /api/admin/results/{id}、/publish、/withdraw |
| Pipeline 列表/创建 | GET/POST | /api/admin/pipelines |
| Pipeline 详情/续跑 | GET/POST | /api/admin/pipelines/{id}、/{id}/resume |
| 评价 JSON Schema | GET | /api/evaluation-schema |

### 查询示例

    curl -X POST http://127.0.0.1:8000/api/search -H "Content-Type: application/json" -d '{"query":"拉曼光谱","limit":20}'

### 创建评价任务

material_ids 填写上传接口返回的材料 ID，adapter 可选 mock 或 codex：

    curl -b cookies.txt -X POST http://127.0.0.1:8000/api/admin/tasks -H "Content-Type: application/json" -d '{"title":"拉曼光谱项目评价","keywords":["拉曼光谱","光谱检测"],"material_ids":["材料ID"],"adapter":"codex"}'

完整字段、响应结构和认证要求以 /docs 中的 OpenAPI 为准。评价结果统一为 JSON，用户端和管理端通过同一份 JSON 渲染报告页面。

## 目录结构

    backend/    FastAPI、SQLAlchemy、Alembic、worker 和测试
    frontend/   Vue 3、TypeScript、Vite、Element Plus
    skills/     评价 Pipeline 所需的 Codex Skill
    scripts/    环境初始化、开发启动和数据库验证脚本
    docs/       Skill 接入、Pipeline 和验收说明
    compose.yaml

## 测试

    cd backend
    ..\.venv\Scripts\python.exe -m pytest -q
    ..\.venv\Scripts\python.exe -m alembic check
    cd ..\frontend
    npm.cmd run build

真实 Codex 评价需要在已登录 Codex CLI 的环境中运行 worker；测试和演示默认不会自动发布结果，管理员必须审核草稿后再发布。
