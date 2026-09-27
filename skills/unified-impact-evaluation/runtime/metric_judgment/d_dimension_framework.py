from __future__ import annotations

from typing import Any


D_DIMENSIONS: list[dict[str, Any]] = [
    {
        "question_id": "D1",
        "metric_id": "D1",
        "axis": "innovation",
        "name": "核心问题解决与技术先进性",
        "short_name": "问题解决与先进性",
        "question": "该成果是否解决项目最难、最关键的问题，并相较原有能力或性能形成真实提升？",
        "required_views": ["核心问题对应", "原有瓶颈", "技术或能力提升", "同口径先进性"],
        "ai_contribution_role": "AI贡献作为能力提升归因的重要依据，但不得把数据、算力、设备和人工贡献全部归给AI。",
    },
    {
        "question_id": "D2",
        "metric_id": "D2",
        "axis": "innovation",
        "name": "原创性与项目期新增",
        "short_name": "原创与项目新增",
        "question": "该成果在本项目评价窗口内新做出了什么，相对项目前基础和同期同行形成了多强的原创增量？",
        "required_views": ["项目前基础", "项目期新增", "新增性质", "原创增量可归因性"],
        "ai_contribution_role": "AI归因是原创增量可归因性的一部分，必须与新方法、新机制、数据、算力、自动化、设备、领域知识和人工贡献共同拆分。",
    },
    {
        "question_id": "D3",
        "metric_id": "D3",
        "axis": "influence",
        "name": "学术影响力",
        "short_name": "学术影响",
        "question": "该成果是否被同行引用、跟进、讨论、复现或认可，并开始形成可核验的学术影响？",
        "required_views": ["正式学术产出", "独立引用行为", "同行跟进或复现", "覆盖成果与独立团队"],
        "ai_contribution_role": "not_primary",
    },
    {
        "question_id": "D4",
        "metric_id": "D4",
        "axis": "influence",
        "name": "开放复用与生态影响力",
        "short_name": "开放复用",
        "question": "模型、代码、数据或工具是否可获得、可运行，并被原团队之外的主体复现、调用或二次开发？",
        "required_views": ["真实开放", "社区可用性", "独立运行或复现", "二次开发与维护"],
        "ai_contribution_role": "not_primary",
    },
    {
        "question_id": "D5",
        "metric_id": "D5",
        "axis": "influence",
        "name": "真实应用影响力",
        "short_name": "真实应用",
        "question": "该成果是否在项目内部或外部独立主体的真实科研、实验或工程任务中被使用，并带来可验证、可持续的效果？",
        "required_views": ["项目内部真实使用", "外部独立真实使用", "使用效果", "持续性与边界"],
        "ai_contribution_role": "AI归因可解释效果来自哪里，但本维度重点判断真实使用和结果。",
    },
    {
        "question_id": "D6",
        "metric_id": "D6",
        "axis": "influence",
        "name": "项目或组织主线集成影响力",
        "short_name": "项目主线集成",
        "question": "该成果是否正式进入项目或组织主线，发生实际调用并形成持续运行或服务？",
        "required_views": ["内部流程接入", "多环节或外部流程协同", "持续运行与维护"],
        "ai_contribution_role": "not_primary",
    },
    {
        "question_id": "D7",
        "metric_id": "D7",
        "axis": "influence",
        "name": "外部专业认可与领域影响",
        "short_name": "外部认可",
        "question": "项目之外的独立专业主体是否对成果本身形成明确评价、认可、采用或标准政策影响？",
        "required_views": ["独立专业评价", "专业社区或行业传播", "标准政策战略影响", "来源独立性"],
        "ai_contribution_role": "not_primary",
    },
]


# The same branch questions are used by all projects.  They define what must be
# judged; legacy L2-L4 metrics may support a branch, but never define the tree.
D_BRANCH_INDICATORS: list[dict[str, Any]] = [
    {
        "branch_id": "D1.1", "dimension_id": "D1", "name": "核心任务有效解决",
        "question": "成果是否对准项目核心问题，并完成了原有方法难以完成的关键任务？",
        "evidence_requirements": ["核心问题与成果对应关系", "任务完成记录", "原有瓶颈或失败边界"],
    },
    {
        "branch_id": "D1.2", "dimension_id": "D1", "name": "关键性能与效率提升",
        "question": "在同任务、同数据和同测试条件下，精度、效率、规模或成本是否形成实质提升？",
        "evidence_requirements": ["同口径基线", "原始测试结果", "精度—效率—成本联合比较"],
    },
    {
        "branch_id": "D1.3", "dimension_id": "D1", "name": "可靠性、边界与先进性",
        "question": "成果是否在极端条件、未见任务和真实约束下保持可靠，并达到可核验的先进水平？",
        "evidence_requirements": ["稳定性与失败案例", "适用边界", "外部强基线或当前最佳水平"],
    },
    {
        "branch_id": "D2.1", "dimension_id": "D2", "name": "项目期新增与前期区分",
        "question": "哪些方法、能力和结果是在本项目评价窗口内新增，而不是直接继承前期基础？",
        "evidence_requirements": ["T0前期基础", "带日期的项目期版本", "新增内容差异表"],
    },
    {
        "branch_id": "D2.2", "dimension_id": "D2", "name": "方法、机制或路线原创",
        "question": "成果是否提出同行已有路线之外的新方法、新机制或新技术路径？",
        "evidence_requirements": ["同期同行路线", "方法或机制差异", "原创点与结果之间的因果链"],
    },
    {
        "branch_id": "D2.3", "dimension_id": "D2", "name": "项目期原创增量的可归因性",
        "question": "项目期新增来自新方法、新机制、新科学能力还是数据、算力、自动化、工程规模等扩张；各类贡献能否区分？",
        "evidence_requirements": ["新增类型与作用链", "AI及非AI贡献拆分", "消融、反事实或版本差异证据"],
    },
    {
        "branch_id": "D3.1", "dimension_id": "D3", "name": "成果对应与独立引用",
        "question": "是否形成可追溯的学术产出，并获得与成果准确对应的独立引用？",
        "evidence_requirements": ["正式出版记录", "去自引引用", "成果与论文对应关系", "引用原文"],
    },
    {
        "branch_id": "D3.2", "dimension_id": "D3", "name": "外部学术行为深度",
        "question": "独立团队是背景提及、方法评价、作为基线、实际复现，还是在其上继续研究？",
        "evidence_requirements": ["引用行为分类", "独立跟进记录", "第三方复现实验", "公开比较或批评"],
    },
    {
        "branch_id": "D3.3", "dimension_id": "D3", "name": "学术影响覆盖与持续性",
        "question": "学术行为覆盖了多少冻结核心成果、多少独立团队，最深行为达到哪里并是否持续？",
        "evidence_requirements": ["核心成果覆盖", "独立团队去重", "行为深度", "持续引用或研究议题扩散"],
    },
    {
        "branch_id": "D4.1", "dimension_id": "D4", "name": "真实开放",
        "question": "代码、模型、权重、数据或工具是否有可访问地址、明确许可、版本和必要文档？",
        "evidence_requirements": ["公开地址", "许可", "版本与元数据", "数据或模型卡"],
    },
    {
        "branch_id": "D4.2", "dimension_id": "D4", "name": "外部可运行性与维护",
        "question": "外部主体能否按文档成功运行指定版本，问题是否获得可追溯的修复与维护？",
        "evidence_requirements": ["运行文档与环境", "第三方运行记录", "安装与复现反馈", "失败问题与维护记录"],
    },
    {
        "branch_id": "D4.3", "dimension_id": "D4", "name": "独立复用与二次开发",
        "question": "原团队之外的主体是否真正运行官方资源、复现结果、改造模型或形成衍生资产？",
        "evidence_requirements": ["第三方实际运行", "独立复现", "二次开发", "贡献或衍生资产"],
    },
    {
        "branch_id": "D5.1", "dimension_id": "D5", "name": "项目内部真实使用",
        "question": "项目自己的研究是否由明确使用者把成果用于真实任务，并形成输入、输出和后续结果链？",
        "evidence_requirements": ["内部使用者", "真实任务与输入", "输出及后续实验", "演示与正式使用区分"],
    },
    {
        "branch_id": "D5.2", "dimension_id": "D5", "name": "外部独立真实使用",
        "question": "项目之外的独立主体是否把成果用于自己的真实科研、实验或工程问题？",
        "evidence_requirements": ["外部独立使用者", "真实任务与过程记录", "第三方使用证明", "合作意向与实际使用区分"],
    },
    {
        "branch_id": "D5.3", "dimension_id": "D5", "name": "使用效果与持续性",
        "question": "真实使用改变了什么，是一次演示还是形成了可归因效果、持续使用或稳定服务？",
        "evidence_requirements": ["使用前后对照", "过程或结果日志", "效果归因与副作用", "持续使用周期"],
    },
    {
        "branch_id": "D6.1", "dimension_id": "D6", "name": "内部流程接入",
        "question": "成果是否已实际接入项目内部流程；在何处由谁使用并产生何种输出？",
        "evidence_requirements": ["实际流程输入输出", "部署、接口或任务记录", "成果版本与流程位置"],
    },
    {
        "branch_id": "D6.2", "dimension_id": "D6", "name": "项目主线实际调用",
        "question": "成果是否与多环节或外部流程实际协同，有哪些任务、交付与反馈？",
        "evidence_requirements": ["平台或流程侧调用主体", "服务任务", "接口调用日志", "非原团队反馈"],
    },
    {
        "branch_id": "D6.3", "dimension_id": "D6", "name": "项目主线持续运行",
        "question": "接入和调用后是否形成持续运行、稳定服务、版本维护和明确责任？",
        "evidence_requirements": ["持续运行日志", "服务周期", "维护责任与版本", "平台或流程侧复核"],
    },
    {
        "branch_id": "D7.1", "dimension_id": "D7", "name": "独立第三方评价与认可",
        "question": "是否有与项目无利益绑定的专业主体对成果本身形成正面评价、专业质疑或争议？具体方向及对象是什么？",
        "evidence_requirements": ["第三方身份与独立性", "评价原文及正面、负面、争议方向", "评价对象与成果对应关系", "排除项目方宣传和专利自证"],
    },
    {
        "branch_id": "D7.2", "dimension_id": "D7", "name": "行业、社区与社会扩散",
        "question": "是否在专业社区、行业组织产生可核验的采用、跟进或公开专业讨论与争议？",
        "evidence_requirements": ["专业社区采用", "行业跟进", "公开专业讨论与争议原文", "传播规模、方向与实际影响区分"],
    },
    {
        "branch_id": "D7.3", "dimension_id": "D7", "name": "标准、政策与战略影响",
        "question": "成果是否进入标准、规范、政策建议或重要战略任务并产生实际作用？",
        "evidence_requirements": ["标准或政策文本", "采纳过程", "成果贡献的可追溯位置"],
    },
]


DIMENSION_STATUSES = [
    {"status": "明确成立", "definition": "多类可追溯证据一致支持该维度判断，且关键反证不足以改变结论。"},
    {"status": "部分成立", "definition": "已有实质事实，但适用范围、独立性、时间归属或证据链仍受限制。"},
    {"status": "尚未形成", "definition": "已有证据明确显示当前尚未形成该类创新或影响，而非单纯缺材料。"},
    {"status": "本轮未体现", "definition": "材料缺失、冲突或不可比，当前不能可靠判断。"},
    {"status": "不适用", "definition": "仅在成果类型或评价范围有明确依据时使用，材料缺失不能判为不适用。"},
]


DIMENSION_INPUT_CONTRACTS: dict[str, dict[str, Any]] = {
    "D1": {
        "required_sources": ["Step 1原始核心问题", "Step 3冻结成果映射", "项目材料", "同口径检索核验", "AI归因"],
        "synthesis_rule": "核心问题直接推进、同任务能力增量和评审时点横向先进性分别判断；缺同口径比较不得声称全面领先。",
        "expert_trigger": "比较协议是否公平、专业性能是否达到领域实用门槛。",
    },
    "D2": {
        "required_sources": ["Step 3冻结成果", "项目前时间线", "项目期版本差异", "同期同行检索核验", "AI及非AI贡献归因"],
        "synthesis_rule": "先区分项目前基础与项目期新增，再判断新增性质及其可归因性；时间线不清直接本轮未体现。",
        "expert_trigger": "新增是否构成方法、机制或科学能力上的实质原创。",
    },
    "D3": {
        "required_sources": ["成果—论文对应", "独立引用原文", "引用行为分类", "独立团队去重"],
        "synthesis_rule": "按核心成果覆盖、独立团队数量和学术行为深度综合，不把论文数量或总引用数直接换算为影响强度。",
        "expert_trigger": "引用行为的专业含义存在会改变判断的争议。",
    },
    "D4": {
        "required_sources": ["公开地址与许可", "版本和运行文档", "社区可用性记录", "独立运行、复现或二次开发"],
        "synthesis_rule": "只开放而无外部使用为部分成立；有独立运行或复现可判复用成立；二次开发和多主体维护才表述生态深度。",
        "expert_trigger": "成果形态是否天然适合开放，或复现记录的技术有效性存在争议。",
    },
    "D5": {
        "required_sources": ["项目内部使用链", "外部独立使用链", "任务输入输出", "效果对照与持续记录", "AI归因"],
        "synthesis_rule": "内部使用、外部独立使用、效果与持续性分别判断；只有基准测试、演示、合同或合作意向不计真实应用。",
        "expert_trigger": "使用效果是否达到领域实用门槛，或是否确由成果造成。",
    },
    "D6": {
        "required_sources": ["内部流程实际接入", "多环节或外部流程的任务与输出", "持续运行和维护记录（判断更高档）"],
        "synthesis_rule": "G2核查内部流程实际接入，G3核查多环节或外部流程协同，G4核查稳定平台或主线能力。三项分支不是所有档位必须同时通过的门槛；内部真实协同可按对象与任务进入D6，不以正式纳管作为低档前提。",
        "expert_trigger": "由项目主线负责人确认接入层级、可集成性和真实运行状态。",
    },
    "D7": {
        "required_sources": ["独立专业评价原文", "来源独立性核验", "专业社区或行业传播", "标准政策采纳位置"],
        "synthesis_rule": "按来源独立性、专业性和实际行为判断外部影响是否发生，并分别说明正面认可、负面质疑和争议。负面专业讨论可以证明影响发生，但不能写成正面认可；项目方宣传、同源转载、专利和一般评审通过不计独立认可。",
        "expert_trigger": "评价主体独立性或标准政策中的成果贡献归属存在争议。",
    },
}


# Per-dimension hand-off contract for the three evidence-producing upstream
# groups.  Step 3 frozen outcomes are the common evaluation object and are not
# counted as a fourth evidence group.
UPSTREAM_COMPONENT_CONTRACTS: dict[str, list[dict[str, Any]]] = {
    "D1": [
        {
            "group_id": "internal_search", "group_name": "内部 Search 组",
            "components": ["核心问题—成果映射", "原始卡点与任务条件", "项目内性能、实验和失败记录"],
            "evaluation_use": "先判断成果是直接推进核心问题还是仅提供支撑，再提取同任务、同条件下的能力或性能增量。",
            "prohibited_use": "不得仅凭成果名称自动匹配核心问题；项目方自报性能不能直接当作已核验先进性。",
        },
        {
            "group_id": "ai_contribution", "group_name": "AI贡献组",
            "components": ["AI作用环节与结果因果链", "消融、反事实或版本差异", "数据、算力、设备、传统方法和人工混杂"],
            "evaluation_use": "用于判断性能或能力提升中哪些部分确由AI造成，并说明AI是核心驱动、辅助工具还是非必要因素。",
            "prohibited_use": "AI贡献较强不等于D1自动成立；仍须证明核心问题推进和真实能力增量。",
        },
        {
            "group_id": "external_search", "group_name": "外部 Search 组",
            "components": ["评审时点同期强基线", "同任务、同数据、同指标、同协议比较", "外部benchmark、泛化结果和失败边界"],
            "evaluation_use": "核验项目基线是否完整、公平，并判断能力增量在同期同行中的位置及适用边界。",
            "prohibited_use": "协议不同或同期强方法未核全时，不得写成全面SOTA或国际领先。",
        },
    ],
    "D2": [
        {
            "group_id": "internal_search", "group_name": "内部 Search 组",
            "components": ["项目前已有基础（T0）", "项目期版本、实验与交付记录（T1）", "前后版本差异和新增声明"],
            "evaluation_use": "先建立项目前基础，再识别项目期新增内容，形成可核验的增量清单。",
            "prohibited_use": "不得把项目前已有方法、论文或模型整体包装成本项目新增。",
        },
        {
            "group_id": "ai_contribution", "group_name": "AI贡献组",
            "components": ["项目期新增的AI方法或能力", "AI与非AI贡献拆分", "消融、反事实和版本差异证据"],
            "evaluation_use": "用于D2.3判断原创增量来自新方法、新机制或新科学能力，还是主要来自数据、算力、自动化和工程扩张。",
            "prohibited_use": "不得把AI使用本身等同于原创，也不得把共同成果全部归因给AI。",
        },
        {
            "group_id": "external_search", "group_name": "外部 Search 组",
            "components": ["项目前既有成果追溯", "同期同行方法与技术路线", "论文、专利和模型版本时间线"],
            "evaluation_use": "校验新增时间归属，并把项目期增量与同期同行路线比较，判断方法、机制或路线原创性。",
            "prohibited_use": "后续影响不能反向证明项目期原创；时间线未闭合时必须本轮未体现。",
        },
    ],
    "D3": [
        {
            "group_id": "internal_search", "group_name": "内部 Search 组",
            "components": ["成果—论文准确对应关系", "正式发表信息", "项目方提供的引用或同行跟进线索"],
            "evaluation_use": "只用于锁定学术产出对象和提供待核线索，避免引用挂错成果。",
            "prohibited_use": "论文数量、期刊层级和项目方自报引用不能直接换算为学术影响力。",
        },
        {
            "group_id": "ai_contribution", "group_name": "AI贡献组",
            "components": ["默认无必需评分组件", "成果身份含混时的AI对象边界说明"],
            "evaluation_use": "仅在需要区分模型、数据、平台或具体AI方法时帮助确定被引用对象，不参与影响强度判断。",
            "prohibited_use": "AI技术先进或贡献显著不能证明已经产生外部学术影响。",
        },
        {
            "group_id": "external_search", "group_name": "外部 Search 组",
            "components": ["独立引用原文与去自引结果", "引用行为分类", "独立团队去重、复现、批评和持续跟进"],
            "evaluation_use": "按背景提及、方法评价、作为基线、实际复现和继续研究的行为深度，综合覆盖度与持续性。",
            "prohibited_use": "不能只报总引用数，也不能把实际运行官方代码仅算作普通引用。",
        },
    ],
    "D4": [
        {
            "group_id": "internal_search", "group_name": "内部 Search 组",
            "components": ["项目方开放资产清单", "代码、模型、数据、权重或API地址", "版本、许可和运行文档声明"],
            "evaluation_use": "建立逐成果开放资产底账，明确声称开放了什么，并交由外部Search核验可访问性与复用。",
            "prohibited_use": "项目方声称已开源，或仅提供仓库链接，不能直接证明可用和已被复用。",
        },
        {
            "group_id": "ai_contribution", "group_name": "AI贡献组",
            "components": ["可选的AI资产边界", "模型、数据与代码之间的依赖关系"],
            "evaluation_use": "仅用于界定被开放和被复用的具体AI资产，避免把整个平台热度归到单一成果。",
            "prohibited_use": "AI组件存在、可导出或可部署不能证明外部主体已经运行或二次开发。",
        },
        {
            "group_id": "external_search", "group_name": "外部 Search 组",
            "components": ["公开地址、许可、版本和文档核验", "下载、issue、维护与安装失败记录", "第三方运行、复现、fork和二次开发"],
            "evaluation_use": "分别判断真实开放、社区可用性和独立复用；负面复现记录同时用于限制结论。",
            "prohibited_use": "Star、下载和媒体热度只能说明关注，不能单独表述为形成生态。",
        },
    ],
    "D5": [
        {
            "group_id": "internal_search", "group_name": "内部 Search 组",
            "components": ["项目内部使用者与真实任务", "任务输入—成果输出—后续实验链", "使用前后效果、日志和持续周期"],
            "evaluation_use": "用于D5.1判断项目内部是否真实使用，并为D5.3提供效果和持续性事实。",
            "prohibited_use": "演示、基准测试、合同或合作意向不能替代真实任务使用记录。",
        },
        {
            "group_id": "ai_contribution", "group_name": "AI贡献组",
            "components": ["AI在真实使用链中的位置", "没有AI时的替代路径或反事实", "AI、自动化、设备、数据和人工对效果的贡献拆分"],
            "evaluation_use": "解释真实使用效果由什么造成，判断AI是否实质进入科研或工程任务，而不是只在外围辅助。",
            "prohibited_use": "不能把自动化平台、设备能力或人工筛选带来的效果全部写成AI应用影响。",
        },
        {
            "group_id": "external_search", "group_name": "外部 Search 组",
            "components": ["外部独立使用者身份", "第三方真实任务、过程与结果证明", "外部使用效果、持续使用和失败记录"],
            "evaluation_use": "用于D5.2判断外部真实应用，并与内部材料共同校验效果是否可验证、可持续。",
            "prohibited_use": "公开检索未找到外部使用只能记为本轮未体现，不能写成不存在外部应用。",
        },
    ],
    "D6": [
        {
            "group_id": "internal_search", "group_name": "内部 Search 组",
            "components": ["项目方声明的项目主线位置", "候选接口、部署或纳管材料", "项目内部调用与协同记录"],
            "evaluation_use": "核查具体成果在内部流程的位置、真实调用及跨环节输出；项目内部记录可支持G2/G3，声明和计划需与实际行为分开。",
            "prohibited_use": "只有设计图、拟接入或单位名单不能证明实际协同；不得一概排除项目内部真实使用与跨环节协同。",
        },
        {
            "group_id": "ai_contribution", "group_name": "AI贡献组",
            "components": ["可选的技术接口与能力边界", "主线可集成性说明"],
            "evaluation_use": "只说明计划接入的AI能力是什么，帮助项目主线负责人判断技术对象和可集成性。",
            "prohibited_use": "技术上可集成、已经封装接口或AI贡献较强，都不能证明已正式进入项目主线。",
        },
        {
            "group_id": "external_search", "group_name": "外部 Search 组",
            "components": ["项目或组织平台官方平台目录与新闻", "公开接口、服务或部署说明", "可公开核验的主线运行信息"],
            "evaluation_use": "用于核验公开身份和主线位置；正式纳管、实际调用和持续运行仍须平台或流程侧记录或负责人确认。",
            "prohibited_use": "搜到项目或组织平台新闻稿不能直接判D6成立；公开未检出也不能判定未接入。",
        },
    ],
    "D7": [
        {
            "group_id": "internal_search", "group_name": "内部 Search 组",
            "components": ["项目方申报的奖项、报道和评价线索", "成果与认可对象的对应关系", "标准、政策或战略任务声明"],
            "evaluation_use": "形成本轮未体现的认可清单，并锁定外部评价究竟针对哪项冻结成果。",
            "prohibited_use": "项目方宣传、承担单位官网、专利和一般专家评审通过不能直接支撑D7。",
        },
        {
            "group_id": "ai_contribution", "group_name": "AI贡献组",
            "components": ["默认无必需评分组件", "认可对象涉及AI时的技术贡献边界"],
            "evaluation_use": "仅帮助确认外部主体认可的是具体AI成果、整个平台还是其他非AI贡献。",
            "prohibited_use": "AI贡献突出不能代替独立第三方评价、认可或采用。",
        },
        {
            "group_id": "external_search", "group_name": "外部 Search 组",
            "components": ["独立专业评价、推荐、质疑或争议原文及方向", "来源独立性与同源转载核验", "行业组织、独立奖项、标准和政策采纳证据"],
            "evaluation_use": "按来源独立性、评价专业性、对象准确性和实际行为判断领域影响，分别说明正面认可、负面质疑与争议。",
            "prohibited_use": "新闻数量不能代替专业认可，同源转载不得重复计数。",
        },
    ],
}


_UPSTREAM_PACKAGE_SPECS: dict[tuple[str, str], dict[str, Any]] = {
    ("D1", "internal_search"): {
        "package_id": "IS-D1", "package_name": "核心任务与内部能力证据包", "target_branches": ["D1.1", "D1.2", "D1.3"],
        "required_fields": ["problem_id、outcome_id、直接解决/技术支撑关系", "原始卡点、任务、数据、指标和测试条件", "提升前后数值、失败案例、材料位置和日期"],
    },
    ("D1", "ai_contribution"): {
        "package_id": "AI-D1", "package_name": "能力增量因果归因包", "target_branches": ["D1.1", "D1.2"],
        "required_fields": ["AI组件、进入环节、输入和输出", "有AI/无AI或新旧版本结果差异", "数据、算力、设备、传统方法和人工贡献"],
    },
    ("D1", "external_search"): {
        "package_id": "ES-D1", "package_name": "同口径先进性核验包", "target_branches": ["D1.2", "D1.3"],
        "required_fields": ["baseline名称、版本、发布日期和评审窗口", "任务、数据、split、指标和协议可比性", "项目值、外部值、来源原文、限制和反证"],
    },
    ("D2", "internal_search"): {
        "package_id": "IS-D2", "package_name": "项目前后版本差异包", "target_branches": ["D2.1"],
        "required_fields": ["T0已有方法、能力、论文、专利和版本", "T1项目期版本、实验、交付及日期", "逐项新增/继承/扩展差异与材料位置"],
    },
    ("D2", "ai_contribution"): {
        "package_id": "AI-D2", "package_name": "原创增量归因包", "target_branches": ["D2.2", "D2.3"],
        "required_fields": ["项目期新增AI方法、机制或科学能力", "消融、反事实或版本差异", "AI与数据、算力、自动化、设备和人工贡献拆分"],
    },
    ("D2", "external_search"): {
        "package_id": "ES-D2", "package_name": "前序成果与同期路线核验包", "target_branches": ["D2.1", "D2.2"],
        "required_fields": ["项目前同团队成果及可核日期", "同期同行方法、机制和替代路线", "相同点、差异点、时间边界与来源原文"],
    },
    ("D3", "internal_search"): {
        "package_id": "IS-D3", "package_name": "学术产出身份包", "target_branches": ["D3.1"],
        "required_fields": ["outcome_id与论文DOI/题名的对应", "作者、机构、发表日期和正式状态", "项目方引用线索及其来源位置"],
    },
    ("D3", "ai_contribution"): {
        "package_id": "AI-D3", "package_name": "被引用AI对象边界说明", "target_branches": ["D3.1"],
        "required_fields": ["被引用的是模型、数据、平台还是具体方法", "AI组件正式名称、版本和成果对应ID", "与非AI成果的边界说明"],
    },
    ("D3", "external_search"): {
        "package_id": "ES-D3", "package_name": "独立学术行为核验包", "target_branches": ["D3.1", "D3.2", "D3.3"],
        "required_fields": ["引用论文、独立团队和去自引标记", "引用原文及背景提及/评价/baseline/复现/跟进分类", "覆盖成果、行为时间、负面意见和持续性"],
    },
    ("D4", "internal_search"): {
        "package_id": "IS-D4", "package_name": "开放资产声明包", "target_branches": ["D4.1"],
        "required_fields": ["资产类型、名称、outcome_id和公开地址", "版本、许可、发布时间和维护主体", "代码/权重/数据/文档/API完整性声明"],
    },
    ("D4", "ai_contribution"): {
        "package_id": "AI-D4", "package_name": "AI资产依赖说明", "target_branches": ["D4.1", "D4.2"],
        "required_fields": ["可独立复用的AI组件及版本", "模型、权重、数据、代码和运行环境依赖", "整个平台与单项成果的资产边界"],
    },
    ("D4", "external_search"): {
        "package_id": "ES-D4", "package_name": "真实开放与复用核验包", "target_branches": ["D4.1", "D4.2", "D4.3"],
        "required_fields": ["访问、下载、许可、文档和版本核验结果", "外部运行主体、日期、过程、结果与来源", "issue、失败复现、fork、二次开发和衍生资产"],
    },
    ("D5", "internal_search"): {
        "package_id": "IS-D5", "package_name": "内部真实使用链包", "target_branches": ["D5.1", "D5.3"],
        "required_fields": ["使用者、真实任务、时间和场景", "任务输入、成果输出、后续实验或工程动作", "使用前后效果、过程日志、持续周期和失败记录"],
    },
    ("D5", "ai_contribution"): {
        "package_id": "AI-D5", "package_name": "应用效果归因包", "target_branches": ["D5.1", "D5.3"],
        "required_fields": ["AI在真实使用链中的具体步骤", "无AI替代流程、人工干预和反事实", "效果中AI、自动化、设备、数据和人工的分别贡献"],
    },
    ("D5", "external_search"): {
        "package_id": "ES-D5", "package_name": "外部真实应用核验包", "target_branches": ["D5.2", "D5.3"],
        "required_fields": ["外部使用者身份、独立性和联系方式/公开来源", "其自身真实任务、输入、过程、输出和验证", "使用效果、持续周期、反馈、停止或失败记录"],
    },
    ("D6", "internal_search"): {
        "package_id": "IS-D6", "package_name": "项目主线接入候选包", "target_branches": ["D6.1", "D6.2"],
        "required_fields": ["声明接入的项目主线名称和流程位置", "部署环境、接口、纳管或服务材料", "项目内部调用记录及其与项目主线证据的区分"],
    },
    ("D6", "ai_contribution"): {
        "package_id": "AI-D6", "package_name": "主线可集成对象说明", "target_branches": ["D6.1（仅辅助）"],
        "required_fields": ["拟接入AI能力、接口、输入输出和版本", "运行依赖、安全边界和维护要求", "已接入事实与未来可集成性的明确区分"],
    },
    ("D6", "external_search"): {
        "package_id": "ES-D6", "package_name": "项目或组织平台公开集成核验包", "target_branches": ["D6.1", "D6.2", "D6.3"],
        "required_fields": ["项目或组织平台官方目录、接口、服务或部署原文", "平台或流程侧调用主体、任务、日志和时间", "持续运行周期、维护责任、版本及负责人复核状态"],
    },
    ("D7", "internal_search"): {
        "package_id": "IS-D7", "package_name": "外部认可候选清单", "target_branches": ["D7.1", "D7.2", "D7.3"],
        "required_fields": ["认可类型、名称、日期和申报来源", "评价主体与项目团队的关系", "认可对象与outcome_id的对应及原材料位置"],
    },
    ("D7", "ai_contribution"): {
        "package_id": "AI-D7", "package_name": "认可对象贡献边界说明", "target_branches": ["D7.1（仅辅助）"],
        "required_fields": ["外部认可针对的具体AI组件或能力", "AI与平台、数据、实验和团队整体贡献边界", "组件版本及冻结成果对应ID"],
    },
    ("D7", "external_search"): {
        "package_id": "ES-D7", "package_name": "独立认可与采纳核验包", "target_branches": ["D7.1", "D7.2", "D7.3"],
        "required_fields": ["独立评价、推荐、奖项或采用的原文", "来源独立性、同源转载和利益关系核验", "标准/政策采纳位置、实际作用、持续传播与负面意见", "公开专业讨论原文及正面、负面、争议方向"],
    },
}

AGENT_EXECUTION_PROTOCOL = [
    {
        "step_id": "P1",
        "name": "锁定成果、维度和分支",
        "instruction": "先读取 outcome_card、dimension 和组件包的 target_branches；只评价当前 Step 3 冻结成果、当前 D 维度，不改写成果边界，也不把组件送入未列出的原子分支。",
        "writes_to": ["branch_judgments[*].branch_id"],
    },
    {
        "step_id": "P2",
        "name": "检查必需字段和来源",
        "instruction": "逐项核对 required_fields、日期、来源编号和时间角色。缺少会改变结论的材料时，不把“未提供”写成“不存在”，而是登记缺口并将受影响分支保留为本轮未体现或部分成立。",
        "writes_to": ["missing_inputs", "time_assessment", "evidence_confidence"],
    },
    {
        "step_id": "P3",
        "name": "把证据作用落到原子判断",
        "instruction": "区分项目方声明与已核验事实；每条事实只标记为支持、限制或反驳，并附来源编号。先更新三个 branch_judgments，不能用材料数量投票，也不能让一个上游组替代另一个组。",
        "writes_to": ["branch_judgments[*]", "evidence_chain", "basis", "counterevidence"],
    },
    {
        "step_id": "P4",
        "name": "按本维度规则综合",
        "instruction": "三个原子判断完成后，再依据 dimension_input_contract.synthesis_rule 形成五态维度结论；D1、D2、D5另写人工智能归因，但归因不是独立分数。",
        "writes_to": ["status", "conclusion", "expert_analysis", "ai_attribution"],
    },
    {
        "step_id": "P5",
        "name": "只把真争议交给专家",
        "instruction": "仅当项目材料和外部核验都不能解决、且答案会改变当前结论时，提出一个可回答的专家问题；一般缺材料直接列入 missing_inputs。",
        "writes_to": ["expert_question", "judgment_confidence"],
    },
]


def _agent_step(label: str, instruction: str, *writes_to: str) -> dict[str, Any]:
    return {"label": label, "instruction": instruction, "writes_to": list(writes_to)}


_AGENT_USE_SPECS: dict[tuple[str, str], dict[str, Any]] = {
    ("D1", "internal_search"): {
        "input_path": "adapted_evidence.step3_problem_links + step1_core_problems + internal_search + project_facts",
        "agent_use_steps": [
            _agent_step("核对显式问题链接", "用 problem_id 与 outcome_id 核对 Step 3 已确认的成果—核心问题链接。存在直接解决关系才支持 D1.1；只有技术支撑则写明支撑层级；没有显式链接时 D1.1 必须本轮未体现，禁止按关键词自行匹配。", "branch_judgments[D1.1]", "missing_inputs", "core_position"),
            _agent_step("提取同条件增量", "从原始卡点、任务、数据、指标、测试条件和提升前后数值建立同口径事实链；成功结果进入支持依据，失败案例与适用边界进入限制或反证，用于 D1.2。", "branch_judgments[D1.2]", "evidence_chain", "basis", "counterevidence"),
            _agent_step("约束先进性结论", "内部材料只能形成项目方基线与本轮未体现声明，可为 D1.3 提供候选事实，但不能单独写成领先；所有决定性事实均回填来源编号。", "branch_judgments[D1.3]", "basis", "evidence_confidence"),
        ],
    },
    ("D1", "ai_contribution"): {
        "input_path": "adapted_evidence.ai_contribution",
        "agent_use_steps": [
            _agent_step("定位人工智能环节", "把组件名称、输入、输出和进入任务链的位置对应到 D1.1/D1.2，判断人工智能是核心驱动、必要环节、辅助工具还是未进入实质链条。", "branch_judgments[D1.1]", "branch_judgments[D1.2]", "ai_attribution"),
            _agent_step("计算可归因增量", "比较有无人工智能、消融或新旧版本结果；把人工智能贡献与数据、算力、设备、传统方法和人工拆开。差异充分则支持归因，混杂未排除则限制归因，但不抹除已核实的总体性能事实。", "evidence_chain", "ai_attribution", "counterevidence"),
            _agent_step("处理归因缺口", "缺少反事实或版本差异时登记具体缺口并降低归因把握度；不得因为人工智能贡献强就跳过核心问题链接或外部先进性核验。", "missing_inputs", "judgment_confidence", "expert_analysis"),
        ],
    },
    ("D1", "external_search"): {
        "input_path": "adapted_evidence.external_search",
        "agent_use_steps": [
            _agent_step("先审可比性", "逐条核对评审窗口、任务、数据集、split、指标和测试协议。完全同口径才可直接比较；口径不一致的记录只能作为限制说明，不能充当领先证据。", "evidence_chain", "counterevidence", "time_assessment"),
            _agent_step("核验性能位置", "将项目值与评审窗口内外部基线逐项对照，分别把支持、限制和反驳写入 D1.2；来源原文编号写入该分支 decisive_source_ids。", "branch_judgments[D1.2]", "basis", "counterevidence"),
            _agent_step("判断横向先进性", "只有同期强基线基本覆盖且同口径比较成立时才支持 D1.3；缺强基线、协议不齐或仅有项目方自报时保留本轮未体现或部分成立，并明确适用边界。", "branch_judgments[D1.3]", "missing_inputs", "expert_analysis"),
        ],
    },
    ("D2", "internal_search"): {
        "input_path": "adapted_evidence.internal_search + project_facts",
        "agent_use_steps": [
            _agent_step("建立项目开始前基线", "按日期汇总 T0 已有论文、专利、方法、模型和版本，先写入 prior_baseline；来源不清或日期晚于项目开始的内容不能算前序基础。", "time_assessment.prior_baseline", "evidence_chain"),
            _agent_step("形成逐项差异表", "把 T1 项目期版本与 T0 对照，将每项变化标为新增、继承或扩展，并关联实验、交付记录和来源位置；只用可核日期的新增支持 D2.1。", "branch_judgments[D2.1]", "time_assessment.current_window_increment", "basis"),
            _agent_step("处理时间链缺口", "若只有最终成果、没有 T0 或版本日期，不能倒推项目期新增，应在 D2.1 写本轮未体现并列出需要补充的历史版本或过程记录。", "branch_judgments[D2.1]", "missing_inputs", "evidence_confidence"),
        ],
    },
    ("D2", "ai_contribution"): {
        "input_path": "adapted_evidence.ai_contribution",
        "agent_use_steps": [
            _agent_step("识别新增性质", "读取项目期新增人工智能方法、机制或科学能力，区分真正的方法/机制变化与单纯换数据、加算力、做自动化或工程扩容，用于 D2.2。", "branch_judgments[D2.2]", "evidence_chain"),
            _agent_step("验证可归因性", "用消融、反事实或版本差异检验新增效果是否由该人工智能变化造成；证据充分支持 D2.3，混杂因素未拆开则部分成立或本轮未体现。", "branch_judgments[D2.3]", "ai_attribution", "counterevidence"),
            _agent_step("记录混杂边界", "明确数据、算力、自动化、设备和人工各自作用；不把共同成果全部归给人工智能，也不把“使用了人工智能”本身写成原创。", "ai_attribution", "expert_analysis", "judgment_confidence"),
        ],
    },
    ("D2", "external_search"): {
        "input_path": "adapted_evidence.external_search",
        "agent_use_steps": [
            _agent_step("核对前序成果", "按发布日期、预印本日期、版本记录核验同团队在项目开始前已经具备什么；发现前序同构成果时限制 D2.1，不能将继承内容计为新增。", "branch_judgments[D2.1]", "time_assessment.prior_baseline", "counterevidence"),
            _agent_step("比较同期路线", "比较评审窗口内同行方法、机制和替代路线的实质相同点与差异点，用于 D2.2；后续论文或影响只能写 subsequent_effect，不能反证当时原创。", "branch_judgments[D2.2]", "time_assessment.subsequent_effect", "evidence_chain"),
            _agent_step("关闭时间边界", "时间线、作者关系或技术差异无法闭合时，列出具体缺口并将对应分支保留本轮未体现；原文来源进入 decisive_source_ids。", "missing_inputs", "branch_judgments[D2.1]", "branch_judgments[D2.2]"),
        ],
    },
    ("D3", "internal_search"): {
        "input_path": "adapted_evidence.internal_search + project_facts",
        "agent_use_steps": [
            _agent_step("锁定被评价产出", "用 outcome_id 对应论文 DOI/题名、作者、机构和正式发表状态，只把确属当前冻结成果的论文交给外部核验。", "branch_judgments[D3.1]", "evidence_chain"),
            _agent_step("生成引用核验线索", "将项目方提供的引用、复现或同行跟进清单作为候选线索，并保留材料位置；在外部原文确认前不得作为独立学术行为成立依据。", "missing_inputs", "evidence_chain"),
            _agent_step("避免数量替代行为", "论文数量、期刊层级和自报引用只描述产出底账，不直接提高 D3 状态；身份对应不清时 D3.1 本轮未体现。", "branch_judgments[D3.1]", "expert_analysis"),
        ],
    },
    ("D3", "ai_contribution"): {
        "input_path": "adapted_evidence.ai_contribution（本维度仅作对象消歧）",
        "agent_use_steps": [
            _agent_step("消歧被引用对象", "当论文同时包含模型、数据、平台和非人工智能工作时，只确认外部文献实际引用的是哪个组件、版本及对应成果。", "branch_judgments[D3.1]", "expert_analysis"),
            _agent_step("限制组件作用", "该组件只修正成果身份和引用对象边界，不参与 D3.2 行为深度或 D3.3 覆盖持续性判断，也不单独写成人工智能影响力。", "ai_attribution", "evidence_chain"),
        ],
    },
    ("D3", "external_search"): {
        "input_path": "adapted_evidence.external_search",
        "agent_use_steps": [
            _agent_step("确认独立引用", "核对引用原文、作者机构和去自引标记；正式且独立的引用支持 D3.1，同团队自引或来源不明记录不计入。", "branch_judgments[D3.1]", "basis", "counterevidence"),
            _agent_step("判定行为深度", "阅读引用上下文，将行为分为背景提及、方法评价、作为基线、实际复现、批评或继续研究；只有更深行为才支持 D3.2，负面复现同时作为反证或限制。", "branch_judgments[D3.2]", "evidence_chain", "counterevidence"),
            _agent_step("综合覆盖与持续性", "按独立团队去重后，检查行为覆盖了多少冻结成果、跨越多长时间以及是否持续跟进，用于 D3.3；不以总引用次数直接替代。", "branch_judgments[D3.3]", "expert_analysis", "judgment_confidence"),
        ],
    },
    ("D4", "internal_search"): {
        "input_path": "adapted_evidence.internal_search + project_facts",
        "agent_use_steps": [
            _agent_step("建立开放资产底账", "按 outcome_id 列明代码、模型、权重、数据、文档或接口的名称、版本、许可、地址、发布时间和维护主体，作为 D4.1 待核对象。", "branch_judgments[D4.1]", "evidence_chain"),
            _agent_step("检查声明完整性", "标记缺失的许可、权重、数据依赖、运行文档或版本信息；项目方“已开源”声明只能形成候选支持，不能越过外部访问核验。", "missing_inputs", "counterevidence", "evidence_confidence"),
            _agent_step("限定内部材料作用", "内部材料不直接证明社区可用或独立复用，因此不单独更新 D4.2/D4.3 的成立状态。", "expert_analysis", "branch_judgments[D4.1]"),
        ],
    },
    ("D4", "ai_contribution"): {
        "input_path": "adapted_evidence.ai_contribution（本维度仅作资产边界）",
        "agent_use_steps": [
            _agent_step("界定可复用组件", "说明模型、权重、数据、代码、环境之间的依赖，确认外部主体获得哪些材料才能独立运行，用于限制 D4.1/D4.2 的完整性判断。", "branch_judgments[D4.1]", "branch_judgments[D4.2]", "evidence_chain"),
            _agent_step("区分成果与平台", "将单项冻结成果的人工智能资产与整个平台公共能力分开；平台总体热度不得归入单项成果。", "expert_analysis", "counterevidence"),
            _agent_step("不替代复用证据", "组件可导出、可部署或技术上可复用，只表示条件具备，不支持 D4.3；D4.3 必须读取外部主体的真实运行或二次开发记录。", "branch_judgments[D4.3]", "missing_inputs"),
        ],
    },
    ("D4", "external_search"): {
        "input_path": "adapted_evidence.external_search",
        "agent_use_steps": [
            _agent_step("验证真实开放", "实际访问地址并核对下载、许可、版本和关键材料是否存在；可访问且对象对应才支持 D4.1，失效链接、许可冲突或关键资产缺失作为限制/反证。", "branch_judgments[D4.1]", "basis", "counterevidence"),
            _agent_step("验证社区可用", "结合安装文档、issue、维护响应和第三方运行过程判断 D4.2；仅有 star、下载量或宣传报道不能证明可用。", "branch_judgments[D4.2]", "evidence_chain", "counterevidence"),
            _agent_step("验证独立复用", "只有独立主体的复现、fork、二次开发或衍生资产且对象、过程、结果可核时才支持 D4.3；公开未找到时写本轮未体现而非无人复用。", "branch_judgments[D4.3]", "basis", "missing_inputs"),
        ],
    },
    ("D5", "internal_search"): {
        "input_path": "adapted_evidence.internal_search + project_facts",
        "agent_use_steps": [
            _agent_step("重建内部使用链", "核对内部使用者、真实任务、时间、输入、成果输出及后续实验/工程动作；链条闭合才支持 D5.1，演示、基准测试或合作意向不计真实使用。", "branch_judgments[D5.1]", "evidence_chain", "basis"),
            _agent_step("提取效果与持续性", "比较使用前后效果，结合过程日志、持续周期和失败记录更新 D5.3；只有一次调用或只有结果截图时限制结论。", "branch_judgments[D5.3]", "basis", "counterevidence"),
            _agent_step("标记待外部核验部分", "内部使用事实不能支持 D5.2；外部使用者或效果声明只能形成检索线索并列入缺口。", "branch_judgments[D5.2]", "missing_inputs", "expert_analysis"),
        ],
    },
    ("D5", "ai_contribution"): {
        "input_path": "adapted_evidence.ai_contribution",
        "agent_use_steps": [
            _agent_step("定位真实使用中的人工智能", "把人工智能组件对应到任务链的具体步骤，判断它是否直接改变科研/工程决策或产出，还是只做外围整理、展示或自动化。", "branch_judgments[D5.1]", "ai_attribution"),
            _agent_step("拆解效果来源", "用无人工智能替代流程、人工干预和反事实，把效果拆为人工智能、自动化、设备、数据和人工贡献；只把可归因部分用于 D5.3。", "branch_judgments[D5.3]", "ai_attribution", "evidence_chain"),
            _agent_step("限制混杂结论", "反事实缺失或设备/人工混杂严重时，不否定真实使用本身，但降低效果归因强度，并把关键争议写入限制或专家问题。", "counterevidence", "judgment_confidence", "expert_question"),
        ],
    },
    ("D5", "external_search"): {
        "input_path": "adapted_evidence.external_search",
        "agent_use_steps": [
            _agent_step("核验外部主体独立性", "确认使用者不属于项目内部团队，并核对其自身任务、输入、过程、输出和验证记录；闭环成立才支持 D5.2。", "branch_judgments[D5.2]", "basis", "evidence_chain"),
            _agent_step("核验外部效果", "把外部使用前后效果、持续周期、反馈、停止或失败记录与内部材料交叉核对，用于 D5.3；营销案例或无过程证明的客户名单只作线索。", "branch_judgments[D5.3]", "counterevidence", "expert_analysis"),
            _agent_step("处理公开未命中", "未检索到外部应用时只登记缺口并将 D5.2 保留本轮未体现；只有明确的否定性原始记录才能作为反证。", "missing_inputs", "branch_judgments[D5.2]", "evidence_confidence"),
        ],
    },
    ("D6", "internal_search"): {
        "input_path": "adapted_evidence.internal_search + project_facts",
        "agent_use_steps": [
            _agent_step("提取项目或组织平台接入候选", "读取内部流程位置、接口及任务记录；按证据分别确认已实际接入与仅计划接入，不把形式手续作为G2/G3唯一依据。", "branch_judgments[D6.1]", "evidence_chain", "missing_inputs"),
            _agent_step("核查项目内部协同", "核查被评价成果实际交付了什么、谁在何任务使用以及后续结果；内部多环节协同可支持G3，不能因未正式纳管而剔除。", "counterevidence", "expert_analysis"),
            _agent_step("保持调用与运行待核", "内部日志可建立具体成果的实际调用和跨环节协同；持续运行另需日期、重复任务和维护记录。", "branch_judgments[D6.2]", "branch_judgments[D6.3]", "missing_inputs"),
        ],
    },
    ("D6", "ai_contribution"): {
        "input_path": "adapted_evidence.ai_contribution（本维度仅作技术对象说明）",
        "agent_use_steps": [
            _agent_step("说明拟接入对象", "读取人工智能能力、接口、输入输出、版本、运行依赖与安全边界，说明项目主线可能接入的具体技术对象。", "expert_analysis", "evidence_chain"),
            _agent_step("辅助可集成性复核", "组件信息用于说明被调用对象；只有封装接口或可集成性不能证明实际接入，须查真实任务输入输出。", "branch_judgments[D6.1]", "counterevidence"),
            _agent_step("禁止推断调用运行", "该组件不更新 D6.2/D6.3；实际调用、持续服务和维护状态必须来自平台或流程侧记录或负责人确认。", "branch_judgments[D6.2]", "branch_judgments[D6.3]", "missing_inputs"),
        ],
    },
    ("D6", "external_search"): {
        "input_path": "adapted_evidence.external_search",
        "agent_use_steps": [
            _agent_step("核验主线正式身份", "用项目或组织平台官方目录、接口、服务或部署原文确认成果是否被正式纳管以及处于哪一主线位置；新闻稿只作线索，不能单独支持 D6.1。", "branch_judgments[D6.1]", "basis", "counterevidence"),
            _agent_step("核验平台或流程侧实际调用", "核对调用主体、真实任务、日志、日期和跨环节输出；内部协同与外部流程均可支持D6.2，须保留关系区别。", "branch_judgments[D6.2]", "evidence_chain", "basis"),
            _agent_step("核验持续运行", "依据持续周期、维护责任、版本更新和负责人复核判断 D6.3；公开未检出不能判未接入，关键事实无公开记录时提出面向项目或组织平台负责人的单一复核问题。", "branch_judgments[D6.3]", "missing_inputs", "expert_question"),
        ],
    },
    ("D7", "internal_search"): {
        "input_path": "adapted_evidence.internal_search + project_facts",
        "agent_use_steps": [
            _agent_step("建立认可候选清单", "按类型、名称、日期和原材料位置整理奖项、评价、报道、标准或政策线索，并用 outcome_id 锁定其是否针对当前冻结成果。", "evidence_chain", "missing_inputs"),
            _agent_step("预检主体关系", "标记评价主体与项目团队、承担单位或利益相关方的关系；项目方宣传、单位官网、自荐材料和一般评审通过不能直接支持 D7。", "counterevidence", "evidence_confidence"),
            _agent_step("路由到对应分支", "专业第三方评价送 D7.1，行业/社区/社会传播送 D7.2，标准/政策/战略任务采纳送 D7.3；在外部原文核验前均保持候选状态。", "branch_judgments[D7.1]", "branch_judgments[D7.2]", "branch_judgments[D7.3]"),
        ],
    },
    ("D7", "ai_contribution"): {
        "input_path": "adapted_evidence.ai_contribution（本维度仅作认可对象消歧）",
        "agent_use_steps": [
            _agent_step("确认认可对象", "读取外部认可涉及的人工智能组件、版本和冻结成果对应关系，区分认可的是具体人工智能成果、整个平台、数据资源还是团队整体。", "branch_judgments[D7.1]", "expert_analysis"),
            _agent_step("限定贡献边界", "只修正认可对象归属，不用人工智能贡献大小代替第三方独立性、专业性或实际采纳事实。", "ai_attribution", "counterevidence"),
            _agent_step("不独立提高状态", "没有外部原文时，该组件不能使 D7.1–D7.3 成立；对象边界不清则登记需核验的具体版本或成果。", "missing_inputs", "evidence_confidence"),
        ],
    },
    ("D7", "external_search"): {
        "input_path": "adapted_evidence.external_search",
        "agent_use_steps": [
            _agent_step("验证独立专业评价", "读取评价、推荐、质疑或争议原文，核对主体独立性、专业性、利益关系和评价对象；同源转载去重，分别记录正面、负面或争议方向。专业质疑可证明领域影响发生，但不能写成正面认可。", "branch_judgments[D7.1]", "basis", "counterevidence", "key_facts", "evidence_chain"),
            _agent_step("判断扩散深度", "区分一般报道、专业社区讨论、行业组织推荐和持续采用，结合传播时间与负面意见更新 D7.2；新闻数量不能替代认可强度。", "branch_judgments[D7.2]", "evidence_chain", "counterevidence"),
            _agent_step("核验采纳位置", "只有标准、政策或战略任务原文明确采用当前成果并说明实际作用时才支持 D7.3；仅列名、参会或项目入选不足以成立。", "branch_judgments[D7.3]", "basis", "missing_inputs"),
        ],
    },
}


for _dimension_id, _group_contracts in UPSTREAM_COMPONENT_CONTRACTS.items():
    for _group_contract in _group_contracts:
        _group_contract.update(
            _UPSTREAM_PACKAGE_SPECS[(_dimension_id, _group_contract["group_id"])]
        )
        _group_contract.update(
            _AGENT_USE_SPECS[(_dimension_id, _group_contract["group_id"])]
        )


HARD_RULES = [
    {
        "rule_id": "B01",
        "name": "项目期新增边界",
        "effect": "缺少项目实施期新增证据时，D2只能判为本轮未体现或尚未形成。",
        "flexibility": "可补充带日期的版本、实验记录、合同交付或第三方记录。",
    },
    {
        "rule_id": "B02",
        "name": "人工智能贡献边界",
        "effect": "人工智能未进入真实研究或工程链条时，不得表述为人工智能驱动的突破。",
        "flexibility": "这不否定成果本身的科学或工程价值，可明确表述为人工智能辅助。",
    },
    {
        "rule_id": "B03",
        "name": "成果形态边界",
        "effect": "模型榜单不能直接等同于科学发现、工程突破或真实应用。",
        "flexibility": "方法或模型成果仍可依据同口径比较、消融和未见任务验证判断先进性。",
    },
    {
        "rule_id": "B04",
        "name": "影响力边界",
        "effect": "合同、报道、合作意向、项目方宣传和专利本身不能单独证明实际影响或第三方认可。",
        "flexibility": "交付记录、真实调用、流程改变或持续使用可构成直接证据。",
    },
    {
        "rule_id": "B05",
        "name": "比较口径边界",
        "effect": "缺少有效的同口径比较时，不得表述为国际领先。",
        "flexibility": "没有直接可比对象时可依据能力边界、替代路线和公开文献评价原创性。",
    },
    {
        "rule_id": "B06",
        "name": "场景差异校准",
        "effect": "不得把通用人工智能的样本量、速度或榜单阈值机械套用于科学研究场景。",
        "flexibility": "应综合数据获取成本、伦理限制、极端工况、计算规模与验证质量。",
    },
    {
        "rule_id": "B07",
        "name": "项目主线集成边界",
        "effect": "D6按内部实际接入、多环节或外部流程协同、稳定平台逐档判断；计划不能代替实际使用，内部协同不因未正式纳管而被排除。",
        "flexibility": "同一协同事实可分别说明本成果D6与项目协同，但不能重复计数；形成流程的工具或方法与流程产出的产品分别判断。",
    },
    {
        "rule_id": "B08",
        "name": "材料可追溯性",
        "effect": "历史模拟审查材料和不可追溯意见不得直接支撑当前结论。",
        "flexibility": "未决问题应转为补充可追溯材料或公开检索核验任务。",
    },
    {
        "rule_id": "B09",
        "name": "时间归属边界",
        "effect": "里程碑后形成的认可、使用和影响不得反向证明项目期当时已经领先。",
        "flexibility": "后续材料可以更新持续影响判断，但必须与项目期结论分开呈现。",
    },
    {
        "rule_id": "B10",
        "name": "检索证据角色边界",
        "effect": "检索核验只产生外部事实及其支持、限制或反驳关系，不能直接给出D1-D7最终结论。",
        "flexibility": "通过时间、对象、协议和来源独立性核验后，检索事实才能路由到对应原子判断并与其他来源合并。",
    },
    {
        "rule_id": "B11",
        "name": "未检出不等于未形成",
        "effect": "公开检索未找到证据时只能判为本轮未体现；只有检索范围充分且存在明确否定事实时，才能判尚未形成。",
        "flexibility": "可向项目方索取第三方使用证明、运行日志或平台或流程侧材料。",
    },
    {
        "rule_id": "B12",
        "name": "复用与应用分界",
        "effect": "引用或作为比较对象属于D3；运行、复现或二次开发官方资源属于D4；解决真实科研、实验或工程问题才属于D5。",
        "flexibility": "同一事实可在证据链清楚时支持多个维度，但必须分别说明其行为含义。",
    },
    {
        "rule_id": "B13",
        "name": "独立认可边界",
        "effect": "项目承担单位官网、团队公众号、同源转载、项目方供稿和专家评审通过不得单独支撑D7。",
        "flexibility": "独立专业评论、机构正式评价、标准采纳、行业组织推荐或独立奖项可构成有效依据；专业质疑和争议保留为不同方向的领域影响，不计作正面认可。",
    },
]


LAYER_SUMMARY_METHOD = {
    "specific_layer": {
        "name": "特定层",
        "question": "这个项目自己的核心问题解决得怎么样？",
        "primary_dimensions": ["D1", "D2", "D5"],
        "rule": "以系统判断的核心成果牵引D1/D2，分别说明核心问题推进、项目期新增、同期比较和AI贡献；并归纳项目内部真实使用及效果。无已确认核心时保留待判断，不另行计分。",
    },
    "global_layer": {
        "name": "全局层",
        "question": "这些成果是否走出自己的题目并产生更广泛价值？",
        "primary_dimensions": ["D3", "D4", "D6", "D7"],
        "supporting_dimensions": ["D5"],
        "rule": "以核心成果为主，并按维度纳入非核心成果的真实学术、复用、应用、项目主线或专业影响；以覆盖度、深度和集中度校正范围，共享来源与事件去重，不另评一套指标。",
    },
    "system_collaboration": {
        "name": "项目系统性 / 课题协同性",
        "question": "课题是否形成数据、模型、平台、实验或任务链上的真实协作？",
        "rule": "从任务书设计关系到真实输入输出、跨课题任务链、反馈闭环、持续重复运行逐级核查。每条链说明谁给谁什么、任务、结果、调用与反馈证据。项目协同单独汇总；同一事实适用于具体成果D6时可引用但不得重复计数，不把整条流程作用转记给产物。",
    },
}


def route_professional_metric(metric: dict[str, Any]) -> dict[str, Any]:
    from .material_routing import reviewed_route
    return reviewed_route(metric)


def d_dimension_contract() -> dict[str, Any]:
    return {
        "schema_version": "outcome-d1-d7-framework.v3",
        "agent_execution_protocol": [
            {**row, "writes_to": list(row["writes_to"])}
            for row in AGENT_EXECUTION_PROTOCOL
        ],
        "dimensions": [dict(row) for row in D_DIMENSIONS],
        "branch_indicators": [
            {**row, "evidence_requirements": list(row["evidence_requirements"])}
            for row in D_BRANCH_INDICATORS
        ],
        "statuses": [dict(row) for row in DIMENSION_STATUSES],
        "dimension_input_contracts": {
            key: {**value, "required_sources": list(value["required_sources"])}
            for key, value in DIMENSION_INPUT_CONTRACTS.items()
        },
        "upstream_component_contracts": {
            key: [
                {
                    **row,
                    "components": list(row["components"]),
                    "agent_use_steps": [
                        {**step, "writes_to": list(step["writes_to"])}
                        for step in row["agent_use_steps"]
                    ],
                }
                for row in rows
            ]
            for key, rows in UPSTREAM_COMPONENT_CONTRACTS.items()
        },
        "layer_summary_method": {key: dict(value) for key, value in LAYER_SUMMARY_METHOD.items()},
        "professional_metric_policy": "L2-L4只作为专业事实和专业尺度归集到D1-D7，不独立评分、不单独综合。",
        "ai_contribution_policy": "AI归因贯穿D1、D2和D5的相应事实链，不作为等权独立分数；必须与数据、算力、自动化、设备、传统方法、领域知识和人工贡献区分。",
        "scoring_policy": "逐成果、逐维度形成有依据的定性判断；不计算平均分或总分。",
    }


__all__ = [
    "D_DIMENSIONS",
    "D_BRANCH_INDICATORS",
    "DIMENSION_STATUSES",
    "DIMENSION_INPUT_CONTRACTS",
    "UPSTREAM_COMPONENT_CONTRACTS",
    "AGENT_EXECUTION_PROTOCOL",
    "LAYER_SUMMARY_METHOD",
    "d_dimension_contract",
    "route_professional_metric",
]
