# 可选HTTP归档工具

当前主流程见[CLI原生研究](cli-research.md)。以下脚本由CLI按需调用，不决定查询策略。

# 程序采集与原文留存

在无法使用原生检索工具时，以实际 HTTP 请求作为本次检索记录。脚本支持 Python 3.11+；运行环境预先安装requirements.txt中的依赖，JSON契约使用Pydantic，PDF提取使用pypdf。目录必须是新目录，避免覆盖前次证据。

1. 根据原始成果声明准备 `plan.json`，结构为 `{"queries":[{"module":"sota","channel":"crossref","query":"论文全名"}]}`。模块为 sota/prior_work/usage_media/github/indicator，渠道为 crossref/openalex/github/bing。完整任务覆盖五模块，查询须有针对性。
2. `python scripts/collect_public_search.py --plan plan.json --output collected`。返回响应、失败和每次请求 receipt。
3. `python scripts/parse_public_search.py --archive collected --output candidates.json`。候选保持原索引日期精度；年份不可自动补为一月一日。HTML 未解析到结果可能是访问拦截，不等于没有证据。
4. 从候选挑选匹配对象的来源，准备 `selected.json`，结构为 `[{"id":"Q001-S01","url":"https://doi.org/..."}]`。同名异领域来源排除并解释。
5. `python scripts/archive_public_sources.py --selections selected.json --output primary`。原始响应、提取正文及失败记录留存；默认不自动标注 full_text。仅在实际文本含所需原文、且非验证码/摘要/登录页时由评测者认定全文读取。

模型评测输入应包含查询记录、候选和实际文本。source 的 ID/URL 对应候选；来源可用于不同于最初查询模块的核验，但原查询模块留在查询日志中。queries 完整保留失败请求；引文须在实际文本或明确标为 metadata_only 的索引记录中逐字找到。sources 不使用内部项目材料 ID。时点判断仍按 execution-contract 执行。

平台分阶段执行时，模型分析阶段的输出格式可能省略queries。此时查询日志由程序从真实receipt生成，不由模型转录。最终导出的完整JSON仍符合search-result.schema.json。模型收到的声明ID和候选ID枚举限定本次对象，不能用模块名替代声明ID。

程序负责的事实字段不要求模型重写：URL来自候选，采集日从receipt时间戳统一本地时区。原文按顺序切成带编号的片段，完整覆盖已提取文本；模型选择quote_ref，程序复制原句为最终quote。不得用改写后的句子冒充引文。未知首次公开日、事件日仍由模型保留null，不能以采集日期替代。

检索接口响应跑题时记录未找到可核验匹配，不据此宣称全网不存在。GitHub 当前信息不能证明历史状态；有仓库也不等于复现通过。

完整结果由调用方保存为result.json后，使用 `python scripts/export_search.py result.json --output report --collection-root collected-task-root --context input.json` 导出。collection-root下放public-search与primary-sources两个采集目录；context保留上游intake以追溯项目声明及原材料摘录。导出包含原规范21张表、负检索表、五模块报告和证据索引。空表会列入覆盖检查，不能据此声称该类核验已经成功。
