from pydantic import BaseModel
from urllib.parse import urlparse

class CredibilityScore(BaseModel):
    """
    来源可信度评分模型 (0.0 - 100.0)
    """
    score: float          # 0.0 - 100.0 (带小数，如 85.3)
    reason: str           # 简要说明：为什么给这个分
    source_type: str      # official / authoritative / mainstream / user_generated / unknown

    @property
    def tier(self) -> str:
        """
        获取可信度层级 (仅用于展示简述，核心逻辑请使用 score)
        """
        if self.score >= 90: return "very_high"
        if self.score >= 70: return "high"
        if self.score >= 40: return "medium"
        return "low"

# 域名白名单数据库 (Domain Whitelists)
OFFICIAL_DOMAINS = {
    "google.com": 95.0, "blog.google": 98.0, 
    "openai.com": 95.0, "microsoft.com": 95.0, "apple.com": 95.0,
    "github.com": 85.0, # GitHub 本身可信，但内容视情况而定，这里给个基准
    "deepmind.com": 95.0, "deepmind.google": 95.0,
    "gemini.google.com": 98.0
}

AUTHORITATIVE_DOMAINS = {
    "reuters.com": 90.0, "xinhuanet.com": 90.0, "bloomberg.com": 88.0,
    "nytimes.com": 85.0, "wsj.com": 85.0, "bbc.com": 85.0,
    "theverge.com": 80.0, "techcrunch.com": 75.0, "wired.com": 75.0,
    "arxiv.org": 85.0, "nature.com": 92.0, "science.org": 92.0,
    "caixin.com": 80.0, "jiemian.com": 75.0, "people.com.cn": 90.0
}

MAINSTREAM_DOMAINS = {
    "medium.com": 50.0, "substack.com": 50.0, # 平台本身中性，视作者而定
    "zhihu.com": 45.0, "weibo.com": 30.0, "twitter.com": 30.0, "x.com": 30.0,
    "reddit.com": 25.0, "v2ex.com": 40.0, "juejin.cn": 45.0, "csdn.net": 40.0,
    "36kr.com": 65.0, "huxiu.com": 60.0, "qbitai.com": 65.0
}

def evaluate_credibility(url: str, content: str = "") -> CredibilityScore:
    """
    基于域名、内容特征进行 0-100 打分。
    
    Args:
        url: 来源 URL
        content: 内容片段 (可选，用于辅助判断)
    
    Returns:
        CredibilityScore
    """
    if not url:
        return CredibilityScore(score=0.0, reason="No URL provided", source_type="unknown")

    try:
        domain = urlparse(url).netloc.lower()
        # Remove 'www.' prefix
        if domain.startswith("www."):
            domain = domain[4:]
    except:
        return CredibilityScore(score=0.0, reason="Invalid URL", source_type="unknown")

    # 1. Check Official
    for d, score in OFFICIAL_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return CredibilityScore(score=score, reason=f"Official domain match: {d}", source_type="official")

    # 2. Check Authoritative
    for d, score in AUTHORITATIVE_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return CredibilityScore(score=score, reason=f"Authoritative media match: {d}", source_type="authoritative")

    # 3. Check Mainstream / Social
    for d, score in MAINSTREAM_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            # Special logic for some platforms (e.g. Verified users on Weibo/Twitter could be higher, 
            # but we can't easily valid that from URL alone without metadata. 
            # For now return base score)
            
            # Simple heuristic: Official accounts on social media might have specific URL patterns?
            # Keeping it simple for now.
            
            src_type = "user_generated" if score < 50 else "mainstream"
            return CredibilityScore(score=score, reason=f"Mainstream/Social domain match: {d}", source_type=src_type)

    # 4. Unknown Domain
    return CredibilityScore(score=20.0, reason="Unknown domain, treating as low credibility", source_type="unknown")
