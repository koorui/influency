# CLI 主导的原生实时检索

当前运行方式：Docker 内 Codex CLI，codex-relay，原生 `web_search=live`。你负责读原文、决定查询、打开结果、追查引文和仓库、调整词语并判断是否获得有效证据；后台不替你选择检索词或来源。原采集脚本仅是你可调用的归档工具。

## 工作方式

1. 读取本次 `input.json`、`materials/*.txt` 和原始 Search 规范。追踪成果相关的论文、DOI、模型名称、参与团队、日期、样品和实验条件，区分具体成果与底层通用方法。
2. 分别调查 sota、prior_work、usage_media、github、indicator。多用原生 web search 的查询、打开与定位能力，尝试中英文、学术名称、标题、作者及文献链。根据实际结果继续追查，不以一轮检索作为完成条件。
3. 每个模块的搜索批次后立即执行 `python skill/scripts/research_session.py sync-web --module 模块名`。它直接从本次CLI工具事件读取真实查询和网址，不允许自己造日志。
4. 从返回编号中选择相关来源，执行 `python skill/scripts/research_session.py open Q001-S01 Q002-S01`。阅读 `research/primary-sources/` 下的原文。正文短、只有导航或验证码时继续用原生web查找出版方、作者主页、机构知识库等可追溯替代来源；搜索/打开新地址后再次sync，再归档新的编号。
5. 可用 `python skill/scripts/research_session.py status` 检查已查模块和正文获取状态。允许在本目录写工作笔记，不修改原件、skill、工具日志或采集回执。不读凭据、不发消息、不执行仓库代码。
6. 完成五模块调查后，返回完成摘要与检索边界。后续CLI基于你收集的材料生成完整结构化分析与表格；程序只校验出处、引文、日期和归档一致性。

研究时间上限30分钟，可在其中多轮检索和交叉核对。有效性优先，不设置必须找到正面证据的配额，不把无限重复请求当作质量。检索无命中与访问失败分别说明；背景论文不等于本成果独立采用，公开仓库不等于外部复用，关注不等于认可。
