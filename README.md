# 知衡impact

科研成果影响力评价平台。用户凭项目安全码加入项目，提交成果名称，管理员受理后系统使用该项目材料运行完整评价工作流，自动返回报告，再由提交人验收。

## 使用方式

- 用户端只有 **需求提交**、**成果报告** 两个入口。提交页显示本人每张工单的处理进度；报告页可以查看已加入项目中其他用户成功生成的报告。只有工单提交人可以验收对应报告。
- 管理端只有 **项目材料库**、**工单与工作流**。材料按项目组织，可上传文件、文件夹或 ZIP，并选择参与新工单的原始材料。
- 每张工单依次呈现 **成果卡 → 外部 Search → 贡献归因 → 成果评价与内部审查**。提交后先进入“待受理”；管理员点击“受理并启动”后执行。全部阶段成功且报告通过结构与引用校验后自动发布供审阅，提交人可验收收阅。指定专家在报告内提交事实及整体复核，用户验收不等于专家认定。
- 管理员可删除项目、材料、工作流。项目删除包含其材料、工单、报告与成员授权；工作流删除包含其工单、过程文件与报告。运行中的工作流禁止删除，被工作流引用的材料须先删除相关工作流。删除会二次确认，项目还要求输入完整项目名称。
- 工作流失败或需要补证时停在当前工单，管理员在同一页面处理后继续；未完成的结果不发布给用户。
- 管理员创建项目时设置项目编号、名称与评价日期范围，获取安全码。重置安全码会撤销原有成员权限，成员需重新输入新码。

## Docker 启动

```powershell
.\start-docker.ps1
```

Windows 可双击 `启动Docker.cmd`，访问 http://localhost:18080 。停止使用 `停止Docker.cmd`，数据库和材料卷保留。实际服务由 Nginx、FastAPI、MySQL 和一个完整工作流 worker 组成。Codex CLI 已封装在镜像中，服务器无需另装 CLI。

部署和迁移步骤见 [Docker部署说明.md](Docker部署说明.md)。`.env.docker`、`.deploy-secrets/`、`.deploy-state/`、账号文件和材料均为私有数据，不进入 Git。当前已有数据必须随 Docker 数据卷迁移，仅复制源码不会迁移数据库。

## 评价执行

`pipeline-worker` 通过 Compose secrets 读取本机 `.codex-relay` 导出的配置和认证，使用独立 CLI 工作目录，不读取 `.codex-4`。模型与推理强度在 `.env.docker` 配置。管理员受理工单后才会排队调用模型；部署检查不会调用模型。

本项目 worker 按用户授权使用 CLI 完全访问模式（仅 Docker 容器内），以逐份 UTF-8 文件读取材料；执行环境故障独立报告，成果名只有真实歧义才要求确认。

新工作流读取项目选中的原始材料，生成成果卡、联网检索、贡献归因和双层评价所需的本次成果证据工作区，不复用历史评分作为新成果结论。规则或证据不满足要求时保留异常供管理员处理。

当前规则版本为 `grading-20260927-coordinated-v5`，结果协议为 `outcome-evaluation.v3`。专家附件落实为[事实驱动规则](skills/unified-impact-evaluation/references/teacher-v3-integration.md)：共用事实账本，分开价值、项目新增、AI贡献与实际影响；缺证可留空 G/L。报告提供持久化任务、指定专家复核及保持主对象的重新核验。历史报告不自动改判，旧任务按记录的运行版本处理。

最终交付前执行内部协调和流畅度、易懂性、有用性、证据忠实度检查，以管理者报告为主，保留未消除的审查意见。详见 [v5 实施记录](docs/management-coordination-v5-20260927.md)。

老师试用、服务器选择与迁移事项见 [老师试用与部署](docs/teacher-trial-deployment.md)。

实施范围、真实对照与发布／回退说明见 [融合实施记录](docs/teacher-v4-implementation-20260927.md)。本地启动读取 `.local-runtime/active-release.txt` 选中的完整发布包，并使用已有依赖镜像。

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

## 当前数据

2026-09-27 已按用户要求清空全部历史报告、报告版本、关联工单、工作流、跟进任务和运行底稿。当前保留 1 个项目、6 份原始材料、3 个账号及现有项目访问授权；报告和工单列表为空。

清理前数据库与材料卷备份位于已忽略目录 `.local-runtime/backups/before-history-clear-20260927/`。账号凭据仍位于已忽略的 `.local-access.md`。原始交付文件、早期备份和初始化防重复导入标记保留。

## 验证范围

v5 相关本地检查 57 项通过，Linux 专属的子进程持锁和中断恢复另在容器中验证。前端类型检查、静态构建、桌面与手机展示、已登录的项目权限／报告导出检查通过。

已用拉曼探针冻结证据进行真实模型协调：L1 保持，D7 改为证据不足，D6 保留主报告意见并解释对象边界。结构校验中恢复了模型漏列的原始证据登记条目，未人工调整等级。样例不等于准确率基准，详细过程见实施记录；运行库现已按要求清空，重新提交后才会产生新报告。
