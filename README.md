# 知衡impact

科研成果影响力评价平台。用户凭项目安全码加入项目，提交成果名称，管理员受理后系统使用该项目材料运行完整评价工作流，自动返回报告，再由提交人验收。

## 使用方式

- 用户端只有 **需求提交**、**成果报告** 两个入口。提交页显示本人每张工单的处理进度；报告页可以查看已加入项目中其他用户成功生成的报告。只有工单提交人可以验收对应报告。
- 管理端只有 **项目材料库**、**工单与工作流**。材料按项目组织，可上传文件、文件夹或 ZIP，并选择参与新工单的原始材料。
- 每张工单依次呈现 **成果卡 → 外部 Search → 贡献归因 → 双层影响力评价**。提交后先进入“待受理”；管理员点击“受理并启动”后执行。全部阶段成功且报告通过结构与引用校验后自动发布，提交人点击“验收通过”结束流程。没有单项评价或独立报告审核入口。
- 管理员可删除项目、材料、工作流。项目删除包含其材料、工单、报告与成员授权；工作流删除包含其工单、过程文件与报告。运行中的工作流禁止删除，被工作流引用的材料须先删除相关工作流。删除会二次确认，项目还要求输入完整项目名称。
- 工作流失败或需要补证时停在当前工单，管理员在同一页面处理后继续；未完成的结果不发布给用户。
- 管理员创建项目时设置项目编号、名称与评价日期范围，获取安全码。重置安全码会撤销原有成员权限，成员需重新输入新码。

## Docker 启动

```sh
docker compose --env-file .env.docker up --build -d --wait --wait-timeout 240
docker compose --env-file .env.docker ps
```

Windows 可双击 `启动Docker.cmd`，访问 http://localhost:18080 。停止使用 `停止Docker.cmd`，数据库和材料卷保留。实际服务由 Nginx、FastAPI、MySQL 和一个完整工作流 worker 组成。Codex CLI 已封装在镜像中，服务器无需另装 CLI。

部署和迁移步骤见 [Docker部署说明.md](Docker部署说明.md)。`.env.docker`、`.deploy-secrets/`、`.deploy-state/`、账号文件和材料均为私有数据，不进入 Git。当前已有数据必须随 Docker 数据卷迁移，仅复制源码不会迁移数据库。

## 评价执行

`pipeline-worker` 通过 Compose secrets 读取本机 `.codex-relay` 导出的配置和认证，使用独立 CLI 工作目录，不读取 `.codex-4`。模型与推理强度在 `.env.docker` 配置。管理员受理工单后才会排队调用模型；部署检查不会调用模型。

本项目 worker 按用户授权使用 CLI 完全访问模式（仅 Docker 容器内），以逐份 UTF-8 文件读取材料；执行环境故障独立报告，成果名只有真实歧义才要求确认。

新工作流读取项目选中的原始材料，生成成果卡、联网检索、贡献归因和双层评价所需的本次成果证据工作区，不复用历史评分作为新成果结论。规则或证据不满足要求时保留异常供管理员处理。

Wu 与 v19 已融合为 [统一成果影响力评价技能](skills/unified-impact-evaluation/SKILL.md)：保留成果定位、建卡、管理者报告以及七维/双层综合能力，共同读取一份六级与七维标准。两份报告的等级差异在管理员工作流和用户报告中并列展示，不平均、不自动取高；旧结果显示历史版本，不自动标记成已按新标准重评。

规则版本为 `grading-20260925-1930`，统一评价标识为 `unified-double-layer-impact.v1`。原六阶段ID和已有报告结构保留兼容，统一导出新增 `unified-evaluation.json`。

## 项目材料

支持 TXT、Markdown、PDF、DOCX、XLSX 和 ZIP。项目材料 `project` 可选入工作流；参考资料 `reference`、操作说明 `instruction` 不默认作为原始证据。材料上传和选择均校验所属项目。

默认上传限制：单文件 200 MB、每批 200 个文件、每批总计 2048 MB、压缩包解压总计 5120 MB，可通过环境配置调整。

## 主要 API

写操作使用同源请求及登录后的 HttpOnly 会话 Cookie。用户只能访问安全码授权的项目；管理员负责项目管理。

| 用途 | 方法 | 路径 |
| --- | --- | --- |
| 登录 / 注册 / 退出 | POST | /api/auth/login、/register、/logout |
| 已加入项目 | GET | /api/projects |
| 输入项目安全码 | POST | /api/projects/unlock |
| 提交需求 / 本人工单 | POST / GET | /api/requests |
| 项目报告 / 报告详情 | GET | /api/reports、/api/reports/{id} |
| 项目管理 | GET / POST | /api/admin/projects |
| 更新项目 | PUT | /api/admin/projects/{id} |
| 重置项目安全码 | POST | /api/admin/projects/{id}/access-code |
| 项目材料列表 / 上传 | GET / POST | /api/admin/projects/{id}/materials |
| 选择材料参与评价 | PATCH | /api/admin/projects/{id}/materials/{material_id} |
| 工单列表 / 详情 | GET | /api/admin/requests、/api/admin/requests/{id} |
| 受理并启动 | POST | /api/admin/requests/{id}/receive |
| 用户验收报告 | POST | /api/requests/{id}/accept-report |
| 处理异常并继续 | POST | /api/admin/requests/{id}/continue |
| 删除项目 / 材料 / 工作流 | DELETE | /api/admin/projects/{id}、/api/admin/projects/{id}/materials/{material_id}、/api/admin/requests/{id} |

旧的单项评价、自由创建 Pipeline、手动审核发布和全局用户报告查询接口已退出注册，不能绕过项目授权。

## 历史数据

2026-09-25 已按新一轮试跑要求清空全部历史工单、工作流、报告、版本、查询、操作记录及材料卷中的历史过程目录，撤销旧项目成员授权。当前保留一个化学项目、6 份原始材料与流程说明、原有账号，并新增独立试跑用户。数据库迁移到 `0013_request_acceptance`。

本轮清理前完整备份：`.local-runtime/backups/before-fresh-trial-20260925-075951/`，包含数据库 SQL 与整个材料卷归档。重置回执在材料卷 `/data/materials/fresh-trial-reset.json`。旧包重导入保护和初始化标记保留，原交付 ZIP、外部原始材料与早期备份均未修改。

新账号与密码保存在已忽略的 `.local-access.md`。首次登录需输入化学项目安全码，新账号没有预先加入项目或提交工单。建议普通窗口登录管理员，无痕窗口登录新用户，避免同一浏览器会话覆盖登录身份。

## 验证范围

项目权限、安全码重置、提交幂等、完整工单自动交付、异常不发布、项目材料隔离和新成果证据工作区通过隔离检查；模型调用在检查中使用替身。前端 TypeScript 与生产构建通过。此次没有发出真实模型请求，运行数据库内没有预置工单或报告。管理员受理后将通过 relay 的 CLI 发起真实评价。旧接口的历史检查不适用于新的产品流程。
