"""
配置管理模块。
"""
import os
from dotenv import load_dotenv
from typing import NamedTuple

# 加载 .env 文件
load_dotenv()

class EvidenceDepthConfig(NamedTuple):
    """Evidence Depth 配置"""
    search_results: int  # 搜索结果数
    deep_fetch: int      # 深度抓取数
    comment_mode: str    # 评论模式: shallow/normal/deep

# 预定义的 Evidence Depth 模式
EVIDENCE_DEPTH_MODES = {
    "quick": EvidenceDepthConfig(search_results=5, deep_fetch=3, comment_mode="shallow"),
    "balanced": EvidenceDepthConfig(search_results=10, deep_fetch=5, comment_mode="normal"),
    "deep": EvidenceDepthConfig(search_results=15, deep_fetch=8, comment_mode="deep"),
}

class Settings:
    """全局配置类"""
    
    # LLM 配置
    # LLM 配置
    _openai_api_key = os.getenv("OPENAI_API_KEY", "")
    _dashscope_api_key = os.getenv("DASHSCOPE_API_KEY", "")
    
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o")
    embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v2")
    
    @property
    def openai_api_key(self):
        """Dynamic API Key selection"""
        if "dashscope" in self.openai_base_url and self._dashscope_api_key:
            return self._dashscope_api_key
        return self._openai_api_key
    
    # 项目配置
    project_name = "DeepTrace"
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    # Comment Triage
    comment_promotion_threshold: float = 0.7
    
    # Fetcher Configuration
    fetcher_mode = os.getenv("FETCHER_MODE", "auto")  # auto / mock / serpapi
    serpapi_key = os.getenv("SERPAPI_KEY", "")
    serpapi_engine = os.getenv("SERPAPI_ENGINE", "google")
    serpapi_num_results = int(os.getenv("SERPAPI_NUM_RESULTS", "10"))

    # --- Evidence Depth Configuration ---
    # Mode: auto (AI decides), quick, balanced, deep
    EVIDENCE_DEPTH_MODE = os.getenv("EVIDENCE_DEPTH_MODE", "auto")
    
    # --- Phase 9: Verification Logic Configuration ---
    CLAIM_IMPORTANCE_THRESHOLD = 60.0 # 重要性 >= 60 的声明才深挖验证
    VERIFICATION_CRED_THRESHOLD = 80.0 # 可信度 < 80 的声明需验证
    
    # Verification Loop Limits
    MAX_VERIFICATION_DEPTH = 3      # 单个声明最多验证 3 层
    MAX_BFS_DFS_CYCLES = 3          # 最多 3 轮 BFS-DFS 循环

    # --- Global Guardrails & Hard Limits ---
    # These limits are enforced regardless of mode
    
    # Per Query Hard Limits
    MAX_EVIDENCE_PER_QUERY = 50       # 单次查询最大证据数
    MAX_TOTAL_EVIDENCE = 200          # 总证据数上限
    MAX_TOTAL_COMMENTS = 1000         # 评论总数上限
    
    # Per Platform Hard Limits (per query)
    MAX_WEIBO_POSTS_PER_QUERY = 15
    MAX_WEIBO_COMMENTS_PER_QUERY = 500
    MAX_SERPAPI_RESULTS = 15
    
    # Recursion Limits
    MAX_RETRIEVAL_ROUNDS = 2  # Initial + 2 hops
    MAX_NEW_QUERIES_PER_ROUND = 3
    
    # HTTP Budget
    MAX_HTTP_REQUESTS_PER_QUERY = 100
    
    # --- Weibo Configuration ---
    # Search Mode: quick (3+1), balanced (5+3), deep (8+5)
    WEIBO_SEARCH_MODE = os.getenv("WEIBO_SEARCH_MODE", "balanced")
    # Comment Mode: auto (AI decides), shallow (1 page), normal (3 pages), deep (10 pages)
    WEIBO_COMMENT_MODE = os.getenv("WEIBO_COMMENT_MODE", "auto")

    # --- RAICT Lite Settings (Phase 10) ---
    MAX_LAYERS = 2  # default balanced
    MAX_BREADTH_STEPS_PER_LAYER = 3
    MAX_DEPTH_STEPS_PER_LAYER = 3

    # VoI Thresholds
    BREADTH_VOI_THRESHOLD = 0.5  # Only add breadth tasks > 0.5
    DEPTH_VOI_THRESHOLD = 0.5    # Only add depth tasks > 0.5

    # Cost Estimates (Original)
    COST_BREADTH_DEFAULT = 1.0
    COST_DEPTH_DEFAULT = 2.0
    
    # VoI Cost Model (Phase 10+)
    BREADTH_BASE_COST = 1.0
    DEPTH_BASE_COST = 2.0
    BREADTH_LAYER_COST_FACTOR = 0.5  # Cost increases 50% per layer
    DEPTH_LAYER_COST_FACTOR = 0.5
    
    # VoI Weights
    VOI_WEIGHT_BETA = 1.0         # Weight for claim importance (beta)
    VOI_WEIGHT_UNCERTAINTY = 1.0  # Weight for uncertainty (1 - alpha)
    
    # Top-K Filtering
    MAX_TOP_K_BREADTH_TASKS = 5   # Keep top 5 breadth tasks per triage
    MAX_TOP_K_DEPTH_TASKS = 10    # Keep top 10 depth tasks per triage
    
    # Credibility Threshold
    CREDIBILITY_VERIFIED_THRESHOLD = 0.85  # Claims with alpha >= 0.85 don't need verification

    # --- Phase 17: Strict Truth Constraints ---
    # Official domains (for automatic OFFICIAL evidence_type)
    OFFICIAL_DOMAINS = {
        "openai.com", "blog.openai.com",
        "google.com", "blog.google", "deepmind.com",
        "microsoft.com", "azure.microsoft.com",
        "anthropic.com",
        "meta.com", "ai.meta.com",
        "gov.cn", "xinhuanet.com", "people.com.cn",
        "apple.com", "developer.apple.com"
    }
    
    # Truth thresholds
    OFFICIAL_SOURCE_MIN_CONF = 0.90  # Official sources can achieve 90%+ confidence
    MULTI_SOURCE_MIN_COUNT = 3       # 3+ sources needed for consensus upgrade
    MULTI_SOURCE_MIN_CONF = 0.85     # Average confidence needed for consensus
    
    # Claim verification settings
    MAX_CANONICAL_TEXT_LENGTH = 200  # Max length for canonical text quotes
    
    # --- Phase 18: Advanced Event Modeling ---
    VERSION_FAMILIES = {} # Removed specific model families for generalization
    
    OFFICIAL_PRIORITY_WEIGHT = 1.5   # Events from official sources get 1.5x weight
    RUMOR_PENALTY_WEIGHT = 0.6       # Rumor/opinion events get 0.6x weight
    
    # Concurrency control
    EXTRACTION_BATCH_SIZE = 10        # Process evidences in batches of 3 (increased from 1 for better speed)

    
    @classmethod
    def get_evidence_depth_config(cls, mode: str = None) -> EvidenceDepthConfig:
        """获取 Evidence Depth 配置"""
        mode = mode or cls.EVIDENCE_DEPTH_MODE
        if mode == "auto":
            # Auto 模式默认使用 balanced，实际由 Supervisor 决定
            return EVIDENCE_DEPTH_MODES["balanced"]
        return EVIDENCE_DEPTH_MODES.get(mode, EVIDENCE_DEPTH_MODES["balanced"])

settings = Settings()

