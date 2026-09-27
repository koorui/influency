---
name: impact-evaluation-pipeline
description: 编排统一成果影响力评价、公开Search及AI贡献归因，支持项目工单受理、证据交接、断点续跑和报告交付。用于impact-platform的完整评测流程。
---

# 完整影响力评价流程

使用已部署平台与三个执行技能：unified-impact-evaluation、project-search-verification、data-purification-ai-attribution。阶段契约见 [输入与模块交接](references/workflow.md)。加载技能不表示数据交接或模型执行已经完成。

## 顺序

1. 按统一技能的 [专家执行规则](../unified-impact-evaluation/references/expert-method.md) 凝练对象、版本、原有基础、本期新增及实际作用；冻结ID，建立成果卡和原始证据。上下文不足或范围歧义时等待确认；对象明确但基本验证缺证时保留缺口并继续审阅，允许最终L为空，不编造L1。
2. Search 实际公开检索或明确标识的历史回放，保留请求、原文、失败及时间边界。
3. 基于真实材料运行贡献归因，区分AI参与、净增量及混杂因素，不把工具分析变成原始证据。
4. 统一评价技能生成管理者报告，保留七维证据与六级理由。
5. 同一技能的七维引擎接收冻结证据，形成七维、成果、特定层/全局层及范围综合，不继承管理者报告等级作为事实。
6. 按统一技能的 [协调与表达检查](../unified-impact-evaluation/references/report-quality.md) 核对分歧，修改有依据的问题，检查流畅度、易懂性、有用性和证据忠实度。交付管理者主报告；七维底稿和协调回执保留，最终异议不覆盖主结论。

界面聚合为成果卡、外部Search、贡献归因、成果评价与内部审查四步；底层 wu_intake、search_replay、attribution、wu_evaluation、v19_evaluation、export 六阶段ID保留，以兼容历史任务。

## 平台入口

管理员建立项目、上传并选择默认评测材料。用户用项目安全码加入，选择项目并提交成果需求；工单先待受理，管理员受理后执行。缺失材料或模型环境异常分别显示待补充或失败。完整执行且报告契约通过后，平台交付报告，由用户验收；技能本身不直接修改数据库或发布。

命令行入口：

```text
python scripts/run-pipeline.py create --directory <新目录> --input <输入JSON>
python scripts/run-pipeline.py run --directory <运行目录>
python scripts/run-pipeline.py status --directory <运行目录>
python scripts/run-pipeline.py amend --directory <运行目录> --input <补充JSON> --restart-stage search_replay
```

使用平台虚拟环境。输入不能指定任意命令或凭据。项目材料/范围变化从wu_intake重跑，Search变化从search_replay重跑，工作区变化从v19_evaluation重跑。保留原尝试记录，不直接修改运行状态或删除锁。

修改项目材料或成果范围从wu_intake重跑；改Search从search_replay重跑；改v19交付从v19_evaluation重跑。管理端自动选择最早受影响阶段。输入修订会使受影响阶段失效；旧尝试底稿保留。七维失败重试可复用输入、模型、输出契约与规则文本完全相同且再次通过来源校验的已成功子调用，不进行摘要值或哈希比较。

管理员可在待补充界面补录检索方式与日期，选择冻结子成果，并逐维度勾选实际可用证据。上游材料、范围或Search改变后，旧路由确认失效，不能沿用同名证据编号冒充重新审查。模型结果更新后重新导入草稿会保留版本；来源已变化的旧草稿不能直接发布。

本技能不自动对外发消息，也不把历史回放、测试响应或格式校验当作真实外部核验/专家结论。继续工作需遵守用户对材料范围、模型调用及发布的授权。

## 当前完成标准

两套评价共用L1–L6与D1–D7定义及专家附件补充规则，当前规则版本见统一技能JSON。缺证、不适用或冲突的维度保留空G与明确状态；决定性事实未明可保留空L。最终管理者报告给出主结论，内部审查和残留异议保留依据；证据局限写入适用范围。检索的HTTP执行、正文获取、结论支持强度分别记录；失败链接不能伪装为成功核验。系统建议、结构校验、自动交付及用户验收均不表示已获专家认定；专家只确认有实际记录支持的具体事实和范围。
