---
name: impact-evaluation-pipeline
description: 编排吴老师成果定位、实际公开Search或明确标识的历史回放、原版AI贡献归因、吴老师成果评价和v19双层评估，按阶段保存底稿、确认范围和断点续跑。用于已部署impact-platform的完整评价工作流，两套等级与结果独立保存。
---

# 完整影响力评价Pipeline

该技能使用已部署的impact-platform工作流，不把独立技能按名称调用就视为已经完成数据交接。先读取 [阶段和输入约定](references/workflow.md)。需要本地impact-platform项目及四个模块技能：outcome-impact-evaluation、project-search-verification、data-purification-ai-attribution、dual-layer-impact-v19。独立ZIP不包含整个平台运行环境。

## 编排顺序

1. 吴老师前段：定位成果、自动建卡、提取有原文依据的贡献因素/声明/比较。歧义时停止，保存候选，等待管理员确认。
2. Search：live模式按单良规范执行五模块公开检索，程序保存真实请求、原文及失败记录，Codex核验事实并按评审截止日过滤。replay模式只读取历史交付，始终保留原日期和回放标识，不能冒充新检索。
3. 贡献归因：将材料和Search转换为原版DCA输入，执行确定性代码，保存计算结果与未解决事项。数据提纯为可独立调用的工具，不强制放在每个成果前面。
4. 吴老师后段：根据冻结成果、材料、带实际来源状态的Search和归因结果做成果级评价，保存wu-v2-six-levels底稿及报告。不重复检索或复算归因，不用未核验来源抬高等级。
5. v19：检查已审查的成果ID映射，把原始证据、带模式标识的Search和归因分析送入原版七维/双层引擎。排除吴老师等级和结论，保留v19独立口径。
6. 导出：wu-evaluation.json、v19-evaluation.json及manifest分别保存，不平均、不按数字合并两套L级，不自动发布。

## 使用入口

优先在平台管理端“完整工作流”创建、查看、补充并续跑。也可在平台根目录：

```text
python scripts/run-pipeline.py create --directory <新的运行目录> --input <输入JSON>
python scripts/run-pipeline.py run --directory <运行目录>
python scripts/run-pipeline.py status --directory <运行目录>
python scripts/run-pipeline.py amend --directory <运行目录> --input <补充JSON> --restart-stage search_replay
```

使用平台虚拟环境的Python。后台执行器由服务端配置，输入JSON不能提供任意命令、代码或凭据。对不明原始证据、缺模型配置、缺评审日期/检索能力、缺v19映射，保留waiting状态并说明所缺内容，不用样例补洞。参考评价和流程说明可入库，但不能选作项目原始材料。

修改项目材料或成果范围从wu_intake重跑；改Search从search_replay重跑；改v19交付从v19_evaluation重跑。管理端自动选择最早受影响阶段。已完成阶段仅在输入依赖未变化且输出哈希一致时复用；旧尝试底稿保留。

管理员可在待补充界面补录检索方式与日期，选择冻结子成果，并逐维度勾选实际可用证据。上游材料、范围或Search改变后，旧路由确认失效，不能沿用同名证据编号冒充重新审查。模型结果更新后重新导入草稿会保留版本；来源已变化的旧草稿不能直接发布。

本技能不自动对外发消息，也不把历史回放、测试响应或格式校验当作真实外部核验/专家结论。继续工作需遵守用户对材料范围、模型调用及发布的授权。

## 当前完成标准

两套评价均使用用户09251930文档的L1–L6与D1–D7定义，分别判断、保留各自依据。报告必须给出明确L/G等级；证据局限写入适用范围。检索的HTTP执行、正文获取、结论支持强度分别记录；失败链接不能伪装为成功核验。
