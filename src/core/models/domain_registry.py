"""
Domain Registry: 统一管理所有可信域名白名单和评分规则。

此模块作为唯一真实来源 (Single Source of Truth) 管理：
- 官方域名 (OFFICIAL_DOMAINS)
- 权威域名 (AUTHORITATIVE_DOMAINS)
- 主流域名 (MAINSTREAM_DOMAINS)

所有其他模块应从此处导入，避免重复定义。
"""

# 官方域名：公司/组织的官方网站（最高可信度）
OFFICIAL_DOMAINS = {
    # AI 公司官方
    "openai.com": 95.0,
    "blog.openai.com": 98.0,
    "google.com": 95.0,
    "blog.google": 98.0,
    "deepmind.com": 95.0,
    "deepmind.google": 95.0,
    "gemini.google.com": 98.0,
    "microsoft.com": 95.0,
    "azure.microsoft.com": 95.0,
    "anthropic.com": 95.0,
    "meta.com": 95.0,
    "ai.meta.com": 95.0,
    "apple.com": 95.0,
    "developer.apple.com": 95.0,
    # 政府/官方机构
    "gov.cn": 95.0,
    "xinhuanet.com": 90.0,
    "people.com.cn": 90.0,
    # 技术平台（部分可信）
    "github.com": 85.0,
}

# 权威域名：知名新闻机构、专业媒体（高可信度）
AUTHORITATIVE_DOMAINS = {
    "reuters.com": 90.0,
    "bloomberg.com": 88.0,
    "nytimes.com": 85.0,
    "wsj.com": 85.0,
    "bbc.com": 85.0,
    "ft.com": 85.0,
    "theguardian.com": 83.0,
    "economist.com": 88.0,
    "theverge.com": 80.0,
    "techcrunch.com": 75.0,
    "wired.com": 75.0,
    "arstechnica.com": 78.0,
}

# 主流域名：一般新闻网站、内容平台（中等可信度）
MAINSTREAM_DOMAINS = {
    "cnet.com": 70.0,
    "zdnet.com": 72.0,
    "engadget.com": 68.0,
    "venturebeat.com": 70.0,
    "medium.com": 60.0,
    "reddit.com": 55.0,
    "youtube.com": 50.0,
    "twitter.com": 45.0,
    "weibo.com": 40.0,
    "zhihu.com": 50.0,
}

# 合并所有域名（用于快速查找）
ALL_DOMAINS = {**OFFICIAL_DOMAINS, **AUTHORITATIVE_DOMAINS, **MAINSTREAM_DOMAINS}


def get_domain_score(domain: str) -> tuple[float, str]:
    """
    获取域名的信任评分和类型。

    Args:
        domain: 域名字符串（如 "openai.com"）

    Returns:
        (score, domain_type) 元组
        - score: 0.0-100.0 的可信度评分
        - domain_type: "official" / "authoritative" / "mainstream" / "unknown"
    """
    domain = domain.lower().replace("www.", "")

    # 检查是否为官方域名
    for d, score in OFFICIAL_DOMAINS.items():
        if domain.endswith(d):
            return score, "official"

    # 检查是否为权威域名
    for d, score in AUTHORITATIVE_DOMAINS.items():
        if domain.endswith(d):
            return score, "authoritative"

    # 检查是否为主流域名
    for d, score in MAINSTREAM_DOMAINS.items():
        if domain.endswith(d):
            return score, "mainstream"

    # 未知域名
    return 0.0, "unknown"


# 用于配置的官方域名集合（仅包含名称，不含评分）
OFFICIAL_DOMAIN_SET = set(OFFICIAL_DOMAINS.keys())
AUTHORITATIVE_DOMAIN_SET = set(AUTHORITATIVE_DOMAINS.keys())
MAINSTREAM_DOMAIN_SET = set(MAINSTREAM_DOMAINS.keys())
