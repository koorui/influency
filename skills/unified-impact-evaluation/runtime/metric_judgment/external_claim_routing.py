from __future__ import annotations

import copy
from typing import Any


def _route(outcome_ids: list[str], scope: str, basis: str) -> dict[str, Any]:
    return {"outcome_ids": outcome_ids, "scope": scope, "basis": basis}


# Explicit, reviewable routing from external-search claims to the frozen Step 3
# outcome IDs. Claims must never be expanded by keyword matching.
EXTERNAL_CLAIM_ROUTES: dict[str, dict[str, dict[str, Any]]] = {
    "P01": {
        "SV-01": _route(["RES-MECH-01", "RES-MECH-04"], "shared_component", "列车压力重建同时支撑通用力学工具集和车轴载荷预测链。"),
        "SV-02": _route(["RES-MECH-01"], "direct", "汽车表面压力预测属于跨领域流场建模工具集。"),
        "SV-03": _route(["RES-MECH-01"], "direct", "MHD64属于工具集覆盖的磁流体PDE任务。"),
        "SV-04": _route(["RES-MECH-01", "RES-MECH-02"], "shared_component", "应力—应变符号回归既是工具集能力，也是智能本构模型的方法组件。"),
        "SV-05": _route(["RES-MECH-02"], "direct", "全温区本构识别直接对应连续介质智能本构模型库。"),
        "SV-06": _route(["RES-MECH-03"], "direct", "飞行器工程法基线直接对应跨流域飞行器仿真。"),
        "SV-07": _route(["RES-MECH-03"], "direct", "飞行器升阻预测直接对应跨流域飞行器仿真。"),
        "SV-08": _route(["RES-MECH-03"], "direct", "气动布局优化直接对应跨流域飞行器仿真。"),
        "SV-09": _route(["RES-MECH-03"], "direct", "DLR氢燃烧基线直接对应发动机燃烧求解链。"),
        "SV-10": _route(["RES-MECH-03"], "direct", "燃烧化学加速直接对应反应神经网络和并行求解器。"),
        "SV-11": _route(["RES-MECH-01", "RES-MECH-04"], "shared_component", "列车流场基线同时支撑流场工具和车轴真实载荷边界。"),
        "SV-12": _route(["RES-MECH-04"], "direct", "车轴材料疲劳性能直接对应梯度化车轴制造与验证。"),
        "SV-13": _route(["RES-MECH-04"], "direct", "列车结构应力与压力重建直接对应车轴载荷预测链。"),
        "SV-14": _route(["RES-MECH-05"], "direct", "爆炸冲击模拟直接对应地下工程爆炸安全评估系统。"),
        "SV-15": _route(["RES-MECH-05"], "direct", "Si–O机器学习势对应爆炸系统中的SiO及混凝土岩石跨尺度本构。"),
    },
    "P02": {
        "C01": _route([], "project_context", "总体筛选效率和研发周期是项目级汇总声明，不能分摊给某一成果。"),
        "C02": _route(["MAIN-003"], "direct", "拉曼探针是冻结成果MAIN-003的分支成果ACH-002。"),
        "C03": _route(["MAIN-005"], "direct", "反应条件优化属于冻结成果MAIN-005的功能反应闭环。"),
        "C04": _route(["MAIN-004"], "direct", "累五烯快速合成对应冻结分支成果ACH-003，归属于课题4；不能仅按功能反应字样归到课题5。"),
        "C05": _route(["MAIN-005"], "direct", "生物正交动力学属于冻结成果MAIN-005的功能分子分支。"),
        "C06": _route(["MAIN-005"], "direct", "OLED指标对应冻结分支成果ACH-004。"),
        "C07": _route(["MAIN-005"], "direct", "有机激光指标对应冻结成果MAIN-005的材料分支。"),
        "C08": _route(["MAIN-005"], "direct", "透明聚酰亚胺指标对应冻结分支成果ACH-013。"),
        "C09": _route(["MAIN-001"], "direct", "Innovator-VL多模态科研识别基准属于课题1科研大模型；不能与课题2的Uni-Mol分子预训练基座模型混同。"),
        "C10": _route(["MAIN-002"], "direct", "分子性质预测属于冻结成果MAIN-002的模型能力。"),
        "C11": _route(["MAIN-002"], "direct", "正向反应预测属于冻结成果MAIN-002的模型能力。"),
        "C12": _route(["MAIN-002"], "direct", "逆合成预测属于冻结成果MAIN-002的模型能力。"),
        "C13": _route(["MAIN-003"], "direct", "NMR数据库规模对应冻结分支成果ACH-014。"),
        "C14": _route(["MAIN-003"], "direct", "NMR训练数据效果对应冻结分支成果ACH-014。"),
        "C15": _route(["MAIN-003"], "direct", "NMR逆解析指标对应冻结分支成果ACH-014。"),
        "C16": _route(["MAIN-003"], "direct", "NMR正向预测指标对应冻结分支成果ACH-014。"),
        "C17": _route(["MAIN-003"], "direct", "NMR逆解析比较对应冻结分支成果ACH-014。"),
        "C18": _route(["MAIN-003"], "direct", "NMR自动化效率对应冻结分支成果ACH-014。"),
        "C19": _route(["MAIN-004", "MAIN-005"], "shared_component", "反应计划和自动化操作同时支撑冻结成果MAIN-004和MAIN-005。"),
        "C20": _route([], "project_context", "多任务排名和总体闭环效率是项目级综合声明，不重复挂到单项成果。"),
    },
    "P06": {
        "CLM-001": _route(["RES-SCI-01"], "direct", "生物多模态模型是丰登·基因科学家的直接模型基础。"),
        "CLM-002": _route(["RES-SCI-01"], "direct", "SeedBench推理增强直接对应育种推理能力。"),
        "CLM-003": _route(["RES-SCI-01"], "direct", "GeneScientist直接对应丰登·基因科学家。"),
        "CLM-004": _route([], "project_context", "Intern-S1是项目通用科学基础模型，当前材料未建立到某张主要成果卡的直接结果链。"),
        "CLM-005": _route([], "project_context", "Chem-R是通用化学推理成果，不能仅因领域相近强挂KrF或石墨成果。"),
        "CLM-006": _route([], "project_context", "SpectrumWorld是项目级光谱平台，当前成果卡未明确其直接归属。"),
        "CLM-007": _route([], "project_context", "CSX-Sim/Rank是项目级光谱组件，当前成果卡未明确其直接归属。"),
        "CLM-008": _route(["RES-SCI-02"], "direct", "LGBO直接进入KrF光刻胶优化闭环。"),
        "CLM-009": _route(["RES-SCI-02"], "direct", "KrF平台与树脂指标直接对应KrF光刻胶闭环研发。"),
        "CLM-010": _route(["RES-SCI-03"], "direct", "单晶石墨尺度指标直接对应单晶石墨智能制备。"),
        "CLM-011": _route(["RES-SCI-04"], "direct", "BrainOmni声明只对应BrainOmni 1.5。"),
        "CLM-012": _route(["RES-SCI-04"], "direct", "PNPL语言解码直接对应BrainOmni的语言解码任务。"),
        "CLM-013": _route([], "project_context", "MindSight不是TrialNet伪影去除成果，保留为神经课题背景。"),
        "CLM-014": _route([], "project_context", "ERNA感知DBS不是TrialNet伪影去除成果，保留为神经课题背景。"),
        "CLM-Y1-004": _route(["RES-SCI-04", "RES-SCI-05"], "shared_component", "EMEG数据资产同时支撑脑信号表征和伪影去除，但不等同两项成果本身。"),
    },
}


def external_claim_route(project_id: str, claim_id: str) -> dict[str, Any] | None:
    route = (EXTERNAL_CLAIM_ROUTES.get(project_id) or {}).get(claim_id)
    return copy.deepcopy(route) if route else None


__all__ = ["EXTERNAL_CLAIM_ROUTES", "external_claim_route"]
