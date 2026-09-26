from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


PLACEHOLDER_API_KEY = "REPLACE_WITH_GLM_API_KEY"
PLACEHOLDER_DASHBOARD_ACCESS_TOKEN = "REPLACE_WITH_DASHBOARD_ACCESS_TOKEN"


@dataclass(frozen=True)
class Settings:
    source_dir: Path = Path("source_data")
    workspace_dir: Path | None = None
    output_dir: Path = Path("outputs")
    metrics_path: Path = Path("metrics_framework.md")
    schema_path: Path = Path("evaluation_schema.json")
    # LLM 提供方：默认走 yunwu 中转（OpenAI 兼容）。API key 优先取 GLM_API_KEY，
    # 缺失时回退到环境里的 YUNWU_API_KEY，方便共享同一把 key。
    glm_api_key: str = os.getenv("GLM_API_KEY") or os.getenv("YUNWU_API_KEY", PLACEHOLDER_API_KEY)
    glm_base_url: str = os.getenv("GLM_BASE_URL", "https://yunwu.ai/v1")
    # 主评判模型：用能力较强的模型做 rubric 评分（可用 GLM_MODEL 覆盖）。
    glm_model: str = os.getenv("GLM_MODEL", "gpt-5.6-sol")
    # 候选成果只做结构化筛选和原文复制，默认使用低延迟模型；最终复核与归并仍用主模型。
    fact_extraction_model: str = os.getenv("IMPACT_EVAL_FACT_EXTRACTION_MODEL", "deepseek-v4-pro")
    fact_review_model: str = os.getenv("IMPACT_EVAL_FACT_REVIEW_MODEL", "deepseek-v4-pro")
    fact_hierarchy_model: str = os.getenv("IMPACT_EVAL_FACT_HIERARCHY_MODEL", "deepseek-v3.2")
    fact_extraction_timeout: float = float(os.getenv("IMPACT_EVAL_FACT_EXTRACTION_TIMEOUT", "180"))
    fact_review_timeout: float = float(os.getenv("IMPACT_EVAL_FACT_REVIEW_TIMEOUT", "240"))
    fact_review_max_retries: int = int(os.getenv("IMPACT_EVAL_FACT_REVIEW_MAX_RETRIES", "1"))
    # 权威成果 RAG 始终执行；该开关只控制是否额外遍历全部一般规则候选。
    llm_candidate_expansion: bool = os.getenv("IMPACT_EVAL_LLM_CANDIDATE_EXPANSION", "0") == "1"
    rag_top_k_per_achievement: int = int(os.getenv("IMPACT_EVAL_RAG_TOP_K", "10"))
    rag_candidate_supplement_limit: int = int(os.getenv("IMPACT_EVAL_RAG_SUPPLEMENT_LIMIT", "40"))
    # SOTA 检索用的模型（可与主模型不同，默认同一个）。
    sota_model: str = os.getenv("IMPACT_EVAL_SOTA_MODEL", "") or os.getenv("GLM_MODEL", "gpt-5.6-sol")
    # 对标路由是低温度结构化分类任务，独立使用低延迟模型并设置较短超时。
    comparison_router_model: str = os.getenv(
        "IMPACT_EVAL_COMPARISON_ROUTER_MODEL",
        os.getenv("IMPACT_EVAL_FACT_HIERARCHY_MODEL", "deepseek-v3.2"),
    )
    comparison_router_timeout: float = float(
        os.getenv("IMPACT_EVAL_COMPARISON_ROUTER_TIMEOUT", "90")
    )
    comparison_router_batch_size: int = int(
        os.getenv("IMPACT_EVAL_COMPARISON_ROUTER_BATCH_SIZE", "27")
    )
    # 多模态读图使用通道中明确支持图像输入的模型，不沿用纯文本主模型。
    vision_model: str = os.getenv("IMPACT_EVAL_VISION_MODEL", "qwen3-vl-plus")
    # Generic scoring prompts may take longer; fact-base calls use their own
    # tighter timeout above so a single audit batch cannot stall the workflow.
    llm_timeout: float = float(os.getenv("IMPACT_EVAL_LLM_TIMEOUT", "600"))
    # 图片型 PDF 逐页读图的最大页数（防超长 PPT 打爆 token）。
    vision_max_pages: int = int(os.getenv("IMPACT_EVAL_VISION_MAX_PAGES", "40"))
    # pdftotext 抽出汉字数低于此阈值，判定为图片型 PDF，转多模态读图。
    pdf_min_han_chars: int = int(os.getenv("IMPACT_EVAL_PDF_MIN_HAN", "80"))
    # 默认开启真实 LLM 评分；设 IMPACT_EVAL_USE_LLM=0 可关闭回退到规则分。
    use_llm: bool = os.getenv("IMPACT_EVAL_USE_LLM", "1") == "1"
    # 是否运行真实 SOTA 检索（deep-research）；默认开。
    use_sota_research: bool = os.getenv("IMPACT_EVAL_USE_SOTA", "1") == "1"
    max_chunk_chars: int = int(os.getenv("IMPACT_EVAL_MAX_CHUNK_CHARS", "2400"))
    # 外部验证（Crossref学术文献查询、GitHub仓库查询）配置
    external_search_enabled: bool = os.getenv("IMPACT_EVAL_EXTERNAL_SEARCH", "1") == "1"
    external_search_timeout: float = float(os.getenv("IMPACT_EVAL_EXTERNAL_TIMEOUT", "8"))
    external_search_max_results: int = int(os.getenv("IMPACT_EVAL_EXTERNAL_MAX_RESULTS", "3"))
    crossref_mailto: str = os.getenv("CROSSREF_MAILTO", "")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    # OCR（扫描件 PDF 转文字）配置 —— S03 验收底稿的表格/扫描件抽取用
    ocr_enabled: bool = os.getenv("IMPACT_EVAL_OCR_ENABLED", "1") == "1"
    ocr_languages: str = os.getenv("IMPACT_EVAL_OCR_LANGUAGES", "chi_sim+eng")
    ocr_dpi: int = int(os.getenv("IMPACT_EVAL_OCR_DPI", "300"))
    ocr_min_text_chars: int = int(os.getenv("IMPACT_EVAL_OCR_MIN_TEXT_CHARS", "40"))
    tesseract_cmd: str = os.getenv("TESSERACT_CMD", "")
    # 外部公开记录核验（发表物/文献）API 配置 —— focused_record_verification 用
    openalex_api_key: str = os.getenv("OPENALEX_API_KEY", "")
    semantic_scholar_api_key: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    ncbi_api_key: str = os.getenv("NCBI_API_KEY", "")
    ncbi_email: str = os.getenv("NCBI_EMAIL", "")
    ncbi_tool: str = os.getenv("NCBI_TOOL", "InnovationImpactEvaluation")
    dashboard_access_token: str = os.getenv("DASHBOARD_ACCESS_TOKEN", "")
    dashboard_cookie_secure: bool = os.getenv("DASHBOARD_COOKIE_SECURE", "0") == "1"

    @property
    def mutable_data_dir(self) -> Path:
        """Mutable metadata and supplements must stay outside the raw source layer."""
        return self.workspace_dir or self.source_dir.parent / "workspace_data"

    @property
    def has_real_api_key(self) -> bool:
        return bool(self.glm_api_key and self.glm_api_key != PLACEHOLDER_API_KEY)

    @property
    def dashboard_auth_enabled(self) -> bool:
        return bool(
            self.dashboard_access_token
            and self.dashboard_access_token != PLACEHOLDER_DASHBOARD_ACCESS_TOKEN
        )


DEFAULT_STAGE_WEIGHTS = {
    "T0": {
        "L1_common": 0.30,
        "L2_discipline": 0.20,
        "L3_subfield": 0.25,
        "L4_project_claims": 0.15,
        "evidence_integrity": 0.10,
    },
    "T1": {
        "L1_common": 0.25,
        "L2_discipline": 0.25,
        "L3_subfield": 0.25,
        "L4_project_claims": 0.15,
        "evidence_integrity": 0.10,
    },
    "T2": {
        "L1_common": 0.20,
        "L2_discipline": 0.25,
        "L3_subfield": 0.30,
        "L4_project_claims": 0.15,
        "evidence_integrity": 0.10,
    },
    "T3": {
        "L1_common": 0.18,
        "L2_discipline": 0.25,
        "L3_subfield": 0.30,
        "L4_project_claims": 0.17,
        "evidence_integrity": 0.10,
    },
    "T4": {
        "L1_common": 0.15,
        "L2_discipline": 0.25,
        "L3_subfield": 0.30,
        "L4_project_claims": 0.20,
        "evidence_integrity": 0.10,
    },
    "unknown": {
        "L1_common": 0.25,
        "L2_discipline": 0.25,
        "L3_subfield": 0.25,
        "L4_project_claims": 0.15,
        "evidence_integrity": 0.10,
    },
}

# 评分口径（面向"项目方里程碑汇报"场景：默认采信项目方材料，不因缺第三方而重罚）。
# 证据上限：项目方如实提供数据即可拿到较高分；仅"证据缺失/冲突"才明显压低。
EVIDENCE_CAPS = {"强": 100, "中": 90, "弱": 75, "不足": 50, "冲突": 45}
# 兼容历史产物的可比性/归因映射。新评分只将其作为审计信息，不乘入阶段绩效分。
COMPARABILITY_FACTORS = {"跨项目可比": 1.0, "同类项目可比": 0.95, "仅项目内可比": 0.88, "不可比": 0.8}
ATTRIBUTION_FACTORS = {"清晰": 1.0, "较清晰": 0.92, "部分归因": 0.82, "不清晰": 0.7}
