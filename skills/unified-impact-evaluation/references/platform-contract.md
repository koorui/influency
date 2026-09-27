# 平台执行契约 v2.1

此文件定义统一技能的管理者报告格式。`scripts/assessment_contract.py` 是结构与引用校验的来源，JSON Schema由它生成。判级规则只读取本技能的当前标准，v2仅表示兼容的字段结构。

- schema_version保留wu-outcome-v2.1；新报告rubric_id为unified-double-layer-impact.v1。读取旧报告仍接受wu-v2-six-levels，但不将其自动标记为新标准重评结果。
- outcome_card为12个具名字段的数组；evidence_index为具备唯一ID的证据数组。所有引用必须命中本次证据。
- 项目证据：kind=project，material_id取input.json材料清单的id，quote逐字复制材料文本，locator标物理页或段落；verification=project_statement。
- 外部证据：kind=external，material_id=null，url为实际来源HTTP(S)地址。source写发布主体，date写能确认的日期或null，quote为已读原文，supports/does_not_prove明确适用边界。
- resolution.source_refs绑定定位证据。high需要至少两处名称、描述、指标可以对齐的项目原文。管理员confirmed_scope非空时，仅对与该字符串完全匹配的canonical_name允许确认继续；仍不可绕过项目或原始证据缺失。
- context缺失或范围待确认时，保留所有结构字段；未知卡片标missing，七维grade=null，不虚构G1、L1或升级路径。
当前协议采用 `outcome-evaluation.v3`：系统初判与专家认定分离；完成七维审阅不要求每维都有G，缺证／不适用／冲突保留空值；L可待定。以 [事实驱动评价协议](teacher-v3-integration.md) 为准。
- claims保存项目自述；dimensions保存七维分析；ai_attribution保存参与、基线、净增量、混杂和缺口；external_search_status如实记录检索是否完成。
- 正向等级理由必须挂证据；边界理由说明缺口。关键判断分开project_evidence_ids和evaluation_evidence_ids。
- next_tasks包含project_material和expert_review，可为null；非空则包含title、summary、body。body是可直接编辑复制的收件对象任务文案，不声称已发送。
- 专家附件的落实见 [专家执行规则](expert-method.md)：summary注明系统评价建议；boundary_gap区分尚未发生、证据未取得和不适用；专业争议与补材料任务分开。formal、自动交付和用户验收均不构成专家认定证明。

截图非必需。本版以文字摘录与页码/位置保留原始依据，不伪造截图；外部URL可在报告点击，正式上线前需人工确认链接与事实对应。

当前协议采用 `outcome-evaluation.v3`：系统初判与专家认定分离；完成七维审阅不要求每维都有G，缺证／不适用／冲突保留空值；L可待定。以 [事实驱动评价协议](teacher-v3-integration.md) 为准。
