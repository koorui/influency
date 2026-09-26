> 历史集成记录。当前技能已融合为 `skills/unified-impact-evaluation`；执行与打包以该目录 SKILL.md 和当前 README 为准，本文历史安装位置和验证结果不代表当前状态。

# Codex + 吴老师 v2 Skill 接入

本次使用 `9.23/unified-impact-evaluation` 中完整 v2 规则，源目录未改动。平台维护的可执行包位于 `skills/unified-impact-evaluation`，已安装到本机 `C:/Users/29821/.codex/skills/unified-impact-evaluation`；便携包为 `dist/unified-impact-evaluation.zip`。

## 规则选择与差异

- 沿用吴老师 v2：L1成果形成与验证、L2局部作用验证、L3外部应用验证、L4专业方向显著影响、L5领域基础能力、L6重大引领影响。
- v2 已补齐输入定位、评价规则、UI规范。它的 D6 是通用主线集成，与 v19 特定浦江主线定义不同；本实现不混用 v19 的等级、项目映射或历史结论。
- 上游 JSON Schema 对多个嵌套对象仅规定 object。本实现补充严格字段、引用、状态、等级、升级路径和逐字摘录校验；契约标识为 `wu-outcome-v2.1`，rubric 为 `wu-v2-six-levels`。
- 缺上下文或成果范围待确认时不可给正式等级，也不可通过编辑前台JSON绕过原始底稿的发布限制。
- 高置信自动确认需有至少两处项目材料依据；中低置信时在草稿显示候选，管理员在新任务的“已确认成果范围”中填写候选完整名称后重新评价。当前未实现同一任务中的交互式继续会话。
- 未正式定级时level和升级项为null。L5不生成加2级、L6不生成升级项。缺材料的G级为null，不能默认G1。

## 管理端操作

1. 在“新建评价”输入成果名称，选择上传材料。可填写项目名称/编号；留空时由模型从本次材料中识别。
2. 评价规则选择“Codex · 吴老师v2成果评价”。本机已将其设置为默认，仍可显式选择模拟评价做流程演示。
3. 创建任务。后台执行独立 Codex CLI，页面无需一直打开。
4. 在“评价任务”查看状态；成功后点击“完整底稿”下载包含成果卡、七维、AI归因和证据的JSON，失败可查看诊断日志。
5. 在“结果与审核”查看前台报告。范围/上下文不明确时补材料、确认范围并重新创建评价；其它草稿经管理员审核后才发布。

用户查询页仍采用既定的固定表单，只选择已有已发布成果。输入定位和自动建卡发生在管理员材料评价阶段；没有把普通用户的查询自动改成收费模型任务。

## 执行器

本机以 `codex-cli 0.155.1` 的实际帮助和真实调用验证了 `exec`、stdin prompt、`--output-schema`、`--output-last-message`、`--sandbox read-only`、`--ephemeral` 和 `--json`。

执行器显式加载任务副本中的 `skill/SKILL.md`。参数以数组传给原生可执行文件，不通过 shell 拼接；Windows npm shim 会解析到同安装目录的原生 codex.exe。使用当前 Codex 本地认证及配置模型；未复制账号凭据到 Skill。可用 `CODEX_BINARY`、`CODEX_MODEL` 覆盖服务端配置，前端不能提供任意命令或模型路径。

任务目录：`backend/storage/evaluations/<task_id>/attempt-<n>/`。

- `input.json`、`materials/`：本次输入和材料副本，包含文本摘要哈希。
- `skill/`：本次冻结的Skill副本。
- `run.json`、`prompt.txt`：规则内容哈希、执行器哈希、配置模型、执行输入。
- `events.jsonl`、`stderr.log`、`response.json`：原始运行记录与模型输出。
- `artifacts/`：校验后的评价JSON、成果定位、成果卡、证据底稿、离线HTML及项目组/专家任务文案。

模型不持有应用数据库或会话密钥的环境变量，不写数据库、不发布结果、不向项目组/专家发消息。任务文案仅支持查看、编辑和复制。

后台租约默认600秒，Codex进程默认480秒；执行超时会终止整个进程树。单任务提取文本最多20万字符，超过时拒绝并提示拆分，不静默截断。失败不会退回mock生成假结果。正式多用户部署应增加独立低权限执行账户/容器、按任务并发配额和用量记录；当前验证环境为本机受控管理员使用。

## 输出检查的能力边界

程序检查 schema、枚举、证据编号、来源类型、项目quote与输入文本的一致性、定位门控及升级目标。它不能仅靠这些检查证明外部来源独立性、引用真实性、因果归因或科学结论正确；仍需要模型读取实际来源和管理员审核。

完整底稿只经管理员下载接口提供，公共报告仅包含展示用投影。界面显示真实证据标题、原始URL、能/不能证明的范围、升级路径和可编辑复制任务。

## 安装与复用

```powershell
# 从项目根目录打包；仅首次安装时加 --install，避免覆盖已有同名技能
.\.venv\Scripts\python.exe scripts/package-skill.py

# 独立校验结果，可附输入目录核对逐字引用
.\.venv\Scripts\python.exe skills/unified-impact-evaluation/scripts/validate_result.py evaluation-result.json --input input.json

# 生成离线报告和底稿
.\.venv\Scripts\python.exe skills/unified-impact-evaluation/scripts/export_artifacts.py evaluation-result.json --output artifacts
```

独立 Skill 的 Python 工具需要 Pydantic 2.7+；平台 requirements 已覆盖。安装后可在 Codex 会话中使用 `$unified-impact-evaluation` 并指定项目材料。平台执行器始终引用冻结副本的实际路径，不依赖当前桌面会话是否刷新技能列表。

Docker 配置挂载 `/skills`，但标准 Python 容器不包含宿主机 Windows Codex CLI 或认证。全容器部署要另行配置 Linux Codex 执行环境；不能将本机接通等同于 Docker worker 已接通。

## 验证与试跑

- Skill结构校验通过；自动测试覆盖原文伪造、错误证据、非法等级、升级越界、成果确认、执行失败和进程超时、后台入队和发布门控。
- 已通过一次真实 Codex 连通性测试：虚构且缺上下文的测试文件，返回 `insufficient_project_context`，没有输出L级。
- P02试跑使用用户交付的快照中拉曼相关项目材料台账，逐项保留原JSON路径和完整快照SHA256。它明确标为上游汇编，不冒充原PDF。
- `scripts/pilot-p02.py` 创建/查询本次P02草稿任务，不自动发布，也不重复提交已存在任务。实际试跑状态以管理端任务和底稿为准。

P02本次试跑已完成，返回 `needs_scope_confirmation`：识别到“拉曼探针筛选”“拉曼光谱自动化表征与数据采集”“表征谱图数据智能分析系统的拉曼解析功能”三个候选，没有输出G/L等级。项目原件缺失和汇编记录重复均被明确列为边界。管理员可查看草稿与任务文案，确认具体成果及补充原始材料后再次评价。
