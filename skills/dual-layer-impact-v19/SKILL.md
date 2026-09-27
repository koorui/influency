---
name: dual-layer-impact-v19
description: 兼容旧v19入口；使用本项目统一技能对冻结成果进行七维评价、成果综合和特定层/全局层分析，保留原始证据与运行记录。
---

# 七维与双层评价（兼容入口）

实际引擎与规则位于 [unified-impact-evaluation](../unified-impact-evaluation/SKILL.md)。先读统一入口及 [运行契约](../unified-impact-evaluation/references/runtime-contract.md)，再使用 [当前标准](../unified-impact-evaluation/references/grading-standard-20260925.md) 和 [专家执行规则](../unified-impact-evaluation/references/expert-method.md)。本目录保留的旧资源不构成另一套执行规则。

输入仍是 `indicator-workspace.v6`：只评价冻结的项目与成果，不重新拆并或改名，不把管理者评价结论充当原始证据。先在统一技能目录运行 `python scripts/v19.py inspect`；只有授权运行评价时才使用该目录的 `run`。独立使用需保留相邻统一技能目录，或直接使用完整统一技能。

七维、成果和范围综合都按实际作用及适用证据判断，不平均、不求和，不把学术作用等同商业化，不要求领域基础能力必须跨领域。结果是系统建议，未经真实复核不能声称专家已认定。旧结果保留原版本，不因入口或版本文本更新而视作重评。

模型和凭据由运行环境提供；不读取项目外凭据、不伪造结果、不自动发布或发消息。本入口不启动额外评测，也不修改平台配置。
