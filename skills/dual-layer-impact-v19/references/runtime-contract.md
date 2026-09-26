# v19封装契约

来源：用户交付 `双层影响力工具_v19_交付包_20260923_0735/系统运行版`。runtime按文件复制实际模块和模块必需JSON路由表，源文件SHA256记在 `assets/source-manifest.json`；不含原始项目快照、历史结果、网页、凭据或虚拟环境。原始交付包未改。

## 输入

顶层schema_version应为indicator-workspace.v6，主要字段为project_profile、evaluation_framework.outcome_cards、step3_frozen_outcomes、outcome_card_confirmation、evidence_adapter、available_search、contribution_attribution。以实际build_indicator_input_contract结果为准。

正式运行要求已确认的冻结成果卡和专业事实，七维分别检查内部检索、AI归因和外部检索。全局输入允许开始不代表所有维度证据齐全。原P02快照有5项主要成果；原P01、P06没有冻结成果，应该被阻止。原P02主要卡片以课题边界组织，不能宣称已被封装程序改为单个数据库/分子级样本。

路由与指标含已有项目专用配置。新项目必须提供经过审查的显式映射；保留unmatched，不用已有P02映射或关键词兜底冒充通用处理。自动建卡、成果确认或新项目接入属于上游步骤。

## 凭据与执行

先在独立Python环境安装 `scripts/requirements.txt`。离线inspect/validate仅需标准库；模型运行需要openai和python-dotenv。

run要求显式配置V19_API_KEY、V19_BASE_URL、V19_MODEL，不从命令行传密钥。包装器给原Settings显式传入这三个值，且禁止dotenv自动加载；不采用源码中的默认中转地址。V19是使用OpenAI兼容消息格式的原模型流水线：Codex可调用它，但评判由所配置的模型服务执行，不自动变成Codex自身推理。

模型执行在独立子进程中，设置全局超时并保留诊断。输出目录必须为新目录，不能指向本技能或输入目录；避免覆盖旧报告或改写包内内容。manifest仅记录服务地址（无查询参数、用户信息）、模型、输入哈希、引擎版本、Skill源代码清单哈希，不记录密钥。

上述三个V19环境变量针对独立provider运行入口。impact-platform的codex模式是另一个明确的模型传输入口：由本机Codex认证执行原引擎提示词，维度/成果/范围结果按原字段结构返回，科学规则仍以原版源码为准。恢复运行时只可复用输入、规则、模型和推理配置一致且原始响应与解析结果匹配的调用；每个复用调用标记来源和new_model_call=false，不能计作新的模型执行。

## 校验

运行校验检查当前版本、正式状态、逻辑调用完成数、D1–D7齐全、维度grade和成果impact_level、项目scope_impact_level字段。完成结果必须包含所有L/G等级，证据限制另列。这只是结构/执行完整性检查，不证明证据、因果归因或等级科学性，最终需人工审核。

代码运行失败或校验不通过时进程返回非零，保留底稿，不生成规则打分作为假模型结果。inspect报告会单独列出输入中的本地来源引用无法在当前机器访问的数量及示例；网址不在离线检查中验证。
