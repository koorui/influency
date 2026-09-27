# 知衡impact Docker 部署

> 2026-09-27：当前 v5 使用已有依赖镜像与显式源码／静态文件挂载，本机入口为 start-docker.ps1。老师试用与新服务器部署以 [当前部署说明](docs/teacher-trial-deployment.md) 为准。以下保留早期部署及迁移过程，旧构建命令和历史数量不代表当前发布状态。

该部署使用 Nginx 前端、FastAPI 后端、MySQL 8、完整工作流 worker。Codex CLI 0.156.1、Python 依赖和评测 Skill 均封装进后端镜像。API、数据库、迁移和任务进程按就绪状态顺序启动。默认入口为 http://localhost:18080 ，数据库没有映射宿主机端口。

## 本机启动

完成 Docker Desktop / WSL 2 安装并确保引擎运行后，双击 `启动Docker.cmd`。双击 `停止Docker.cmd` 只停止容器，保留数据库和材料卷。原来的 `启动审阅.cmd` 是独立的 Python/Node/SQLite 临时环境，不是这个部署入口。

也可以在项目目录执行：

```sh
docker compose --env-file .env.docker up --build -d --wait --wait-timeout 240
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs --tail 100 api pipeline-worker
```

## 账号、材料和 CLI

首次启动时，`migrate` 执行数据库迁移，`bootstrap` 把 `.deploy-state` 中的 2 个账号和 6 份有机化学材料导入 MySQL 及材料卷，保留账号原密码和材料标识。原 SQLite 数据和源材料保留，不作为 Docker 运行时依赖；仓库演示报告不进入正式部署。重复启动不会重复导入或覆盖数据库。管理员材料库为 `/admin?tab=projects`。

`.deploy-secrets/relay-config.toml` 与 `relay-auth.json` 只来源于本机 `.codex-relay`，通过 Compose secrets 挂载到完整工作流 worker，使用独立的 CLI 工作目录。认证文件不进入镜像和 Git。默认评价适配器和 v19 传输均为 `codex`，未使用 `.codex-4`。部署和就绪检查不会发出模型请求；管理员受理工单后才会执行。Relay 的实际模型、结构化输出和联网工具能力仍需在真实评价前验证。

部署私密文件为 `.env.docker`、`.deploy-secrets/` 和 `.deploy-state/`，已加入 Git 忽略与镜像构建排除规则。初始化导出包含账号认证信息，只供私下迁移，不要公开上传。

## 迁到服务器

服务器安装 Docker Engine 和 Compose，使用同一份 `compose.yaml` 和 Dockerfile。首次部署可将项目源码、`.env.docker`、`.deploy-secrets/` 与 `.deploy-state/` 私下复制过去，在 `.env.docker` 中设置 `DEPLOY_ORIGIN` 为实际访问地址。如需直接通过服务器端口访问，将 `BIND_ADDRESS` 改为 `0.0.0.0`；如使用本机反向代理，可保留 `127.0.0.1`。HTTPS 环境将 `COOKIE_SECURE` 设为 `true`。密钥和数据无需写入源码或镜像。

**已有运行数据保存在 Docker 卷中，仅复制项目文件夹不会带走后续产生的数据。** 迁移已有部署时，先停止所有容器，再备份 `zhiheng-impact_mysql_data` 和 `zhiheng-impact_materials` 两个卷；在目标服务器用同版本 MySQL 恢复后再启动。Codex 工作卷只是运行缓存，凭据由 secrets 重新注入。

Linux 服务器的停机备份示例（在项目目录执行）：

```sh
docker compose --env-file .env.docker stop
mkdir -p backups
docker run --rm -v zhiheng-impact_mysql_data:/source:ro -v "$PWD/backups:/backup" alpine:3.22 tar -czf /backup/mysql-data.tgz -C /source .
docker run --rm -v zhiheng-impact_materials:/source:ro -v "$PWD/backups:/backup" alpine:3.22 tar -czf /backup/materials.tgz -C /source .
docker compose --env-file .env.docker up -d --wait
```

目标服务器恢复到**空卷**，然后启动：

```sh
docker volume create zhiheng-impact_mysql_data
docker volume create zhiheng-impact_materials
docker run --rm -v zhiheng-impact_mysql_data:/target -v "$PWD/backups:/backup:ro" alpine:3.22 tar -xzf /backup/mysql-data.tgz -C /target
docker run --rm -v zhiheng-impact_materials:/target -v "$PWD/backups:/backup:ro" alpine:3.22 tar -xzf /backup/materials.tgz -C /target
docker compose --env-file .env.docker up --build -d --wait
```

不要使用 `docker compose down -v` 停止日常服务，因为它会删除数据卷。保留 `.env.docker` 中原数据库密码，避免恢复后连接密码不一致。

## 项目制升级和历史清理

数据库迁移 `0012_project_workflow` 增加项目、安全码授权、授权版本和错误尝试限制，并把材料、工单、工作流和报告关联到项目。首次初始化化学项目的安全码保存在材料卷 `/data/materials/project-access-codes.json`；后续重置通过管理员项目页面完成，旧码及旧授权同时失效。首次文件不会记录后续重置的新码。

用户入口为 `/`（需求提交及本人进度）、`/reports`（项目成果报告）。管理员入口为 `/admin?tab=projects`（项目材料库）、`/admin?tab=requests`（工单与完整工作流）。安全码通过后才能查看该项目或提交工单；报告仅向有权访问该项目的用户开放。

每次提交生成一条待受理的完整工作流，管理员点击“受理并启动”后执行：成果卡、外部 Search、贡献归因、双层影响力评价。成功后自动发布和回填用户工单，提交人点击“验收通过”。管理员可以在异常或补证时处理当前工单。单项评价 worker 和人工报告审核入口已撤除。

2026-09-25 的清理保留 7 份必要材料、3 条真实完整流程和 3 份完整报告，保留 2 个现有账号。删除 36 份重复或测试材料、7 条测试及废弃流程、8 条单项评价及 9 份无用报告；保留原始交付 ZIP、外部源材料和清理前完整备份。

备份目录：`.local-runtime/backups/before-project-system-20260925-040746/`，包含数据库 SQL 和整个材料卷归档。清理回执位于 `/data/materials/legacy-cleanup-completed.json`。旧 `import_delivery` 在发现回执后拒绝重新导入，避免历史演示数据重新进入正式库。

## 本机环境

Docker Desktop 4.92.0、WSL 2.7.14。后端镜像固定 Python 3.12.14、Node 22.16.0 和 Codex CLI 0.156.1。Docker Desktop 本机拉取代理为 `http://127.0.0.1:7897`，不写入服务器 Compose。

本机 WSL 6.18 内核曾反复出现内存映射锁停滞，导致构建和数据库进程无法推进。目前通过用户 `.wslconfig` 使用官方 WSL 2.6.3 安装包内的 6.6.87.2 内核与 modules.vhd，限制 4 个处理器、8 GB 内存。文件在 `C:\Users\32134\.wsl-kernels\wsl-2.6.3\PFiles64\WSL\tools`。这是本机兼容性处理，不影响 Linux 服务器镜像；未改 BIOS。原配置备份为 `C:\Users\32134\.wslconfig.before-kernel-20260925`。如需回退，停止数据库与 Docker，恢复该配置并执行 `wsl --shutdown`，再启动 Docker。长期稳定性仍需观察。

## 验证边界

部署检查、数据库迁移及权限检查不发出真实模型请求。本次对新工单完整生命周期使用隔离数据库与模型替身验证；3 份历史成功报告通过报告结构及证据契约校验后自动发布。新的真实成果仍须由用户提交后执行完整模型工作流。

当前 CLI 执行路径已移除自定义材料摘要、工作区指纹和以哈希判断复用的逻辑；账号与安全码认证保留现有算法。历史交付底稿作为原始档案保留，不重新计算摘要。旧预览进程保持停止。

2026-09-25 更新验证：MySQL、API、Web 容器健康，完整工作流 worker 正常运行；两个镜像均在 Docker 内完成构建。实际 Docker 页面已核对登录、安全码加入项目、7 份项目材料、3 条完整工单、3 份共享报告、四阶段详情和手机布局。17 项针对性隔离检查通过，最终报告列表调整后项目流程的 6 项检查再次通过。检查没有生成真实模型工单。普通审阅账号已用安全码加入化学项目。

## 新一轮完整试跑（当前状态）

2026-09-25 已新增数据库迁移 `0013_request_acceptance`，记录管理员受理人与受理时间、用户验收时间。运行状态为：待受理 → 排队/处理中 → 待验收 → 已验收。完成报告仍可在同项目授权成员之间共享，验收操作仅限工单提交人。

已创建独立普通用户，凭据保存在 `.local-access.md`，用户尚未加入项目。全部旧工单、工作流、报告、版本、查询、操作记录与 46 个历史存储目录/文件入口已删除；当前为 1 个项目、6 份原始材料与流程说明、0 工单、0 工作流、0 报告。清理不影响原始交付 ZIP 或外部源材料。

完整备份目录：`.local-runtime/backups/before-fresh-trial-20260925-075951/`。备份前已停止 Web、API 与 worker；数据库采用一致性导出，材料归档已逐个读取确认可解压。`backup.json` 保存文件大小与条目数，不计算文件摘要。重置回执位于 `/data/materials/fresh-trial-reset.json`。

管理员项目详情有“删除项目”，材料行有“删除”，工单列表与详情有“删除工作流”。删除项目需要输入项目名称确认；所有删除操作校验管理员身份和项目归属，运行中的工作流或执行锁阻止删除，被引用材料阻止单独删除。删除文件先移入材料卷内暂存区，数据库提交失败会恢复，提交成功再清除；无需访问宿主机源材料目录。

新的受理、自动返回、本人验收与关联删除已在隔离数据库中检查，未调用真实模型；实际 Docker 的新账号入口、空记录状态和 6 份材料已核对。浏览器按钮的状态转换用拦截响应验证，没有在正式库创建检查工单。

## CLI 文件读取修复（2026-09-25）

首次真实试跑发现：数据库材料和工单快照完整，但 Codex CLI 的只读执行器依赖 bubblewrap，当前 Docker 内创建用户命名空间失败。模型因此没有读到 input.json，旧界面把它归类成材料不足。该故障与 relay API 连通性无关。

按用户明确要求，仅 `pipeline-worker` 设置 `CODEX_SANDBOX_MODE=danger-full-access`，各阶段调用使用此权限模式；其他服务默认仍为 read-only。Docker 仍以 app 用户运行，没有添加 privileged、SYS_ADMIN、Docker socket 或宿主机磁盘挂载，也没有更改本机其他 Codex 配置。模型通过 `.codex-relay` 导出的配置调用服务，容器未单独设置 HTTP_PROXY/HTTPS_PROXY。

成果卡阶段将完整材料逐份写为 UTF-8 文本，在提示中直接提供项目名、用户成果名和文件清单，由 CLI 定位原文，避免一次输出整份长报告导致截断。用户自定义名称不要求与原文标题逐字一致，仍须通过原文引用和成果范围校验。运行日志中的沙箱启动故障现在直接作为执行异常报告；只有明确存在候选成果歧义时才显示成果范围确认框。

实际工单第三次尝试已确认使用 danger-full-access，schema 和材料检索命令退出码均为 0，能够检索到“累积五烯”“拉曼探针”的原文。两次旧失败尝试保留供复查。完整报告是否完成以工单当前状态为准。

配置语义参见 [OpenAI 官方配置文档](https://developers.openai.com/codex/config-reference)。
