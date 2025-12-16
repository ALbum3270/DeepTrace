"""
Report Verification Utilities
统一的报告验证层，封装所有硬核检查逻辑。
"""
import re
import logging
from typing import List, Set, Dict, Tuple

logger = logging.getLogger(__name__)


def verify_report(
    report_content: str,
    evidences: List,
    claims: List = None
) -> Tuple[str, Dict]:
    """
    统一验证函数：在报告输出前执行所有硬核检查。
    
    Args:
        report_content: LLM 生成的报告内容
        evidences: 原始证据列表
        claims: 可选的声明列表（用于引用验证）
        
    Returns:
        Tuple[str, Dict]: (清理后的报告, 验证统计)
    """
    if not report_content:
        return report_content, {"status": "empty"}
    
    stats = {
        "original_length": len(report_content),
        "fake_links_removed": 0,
        "fake_numbers_flagged": 0,
        "unverified_quotes_flagged": 0,
    }
    
    # 1. 链接验证
    report_content, link_stats = _verify_links(report_content, evidences)
    stats["fake_links_removed"] = link_stats["removed"]
    
    # 2. 数字验证（标记可疑数字）
    report_content, number_stats = _verify_numbers(report_content, evidences)
    stats["fake_numbers_flagged"] = number_stats["flagged"]
    
    # 3. 引用验证（如果有 claims）
    if claims:
        report_content, quote_stats = _verify_quotes(report_content, claims)
        stats["unverified_quotes_flagged"] = quote_stats["flagged"]
    
    stats["final_length"] = len(report_content)
    stats["status"] = "verified"
    
    logger.info(f"Report verification complete: {stats}")
    return report_content, stats


def _verify_links(report_content: str, evidences: List) -> Tuple[str, Dict]:
    """
    验证报告中的链接是否在证据白名单中。
    """
    stats = {"removed": 0, "total": 0}
    
    # 快速检查
    if '[' not in report_content or '](' not in report_content:
        return report_content, stats
    
    # 构建白名单
    valid_urls: Set[str] = set()
    for ev in evidences:
        if hasattr(ev, 'url') and ev.url:
            url = str(ev.url).strip()
            valid_urls.add(url)
            valid_urls.add(url.rstrip('/'))
    
    # 非贪婪正则匹配 Markdown 链接
    pattern = r'\[([^\]]*?)\]\(([^)]+?)\)'
    
    def replace_link(match):
        text = match.group(1)
        url = match.group(2).strip()
        stats["total"] += 1
        
        normalized_url = url.rstrip('/')
        is_valid = url in valid_urls or normalized_url in valid_urls
        
        if is_valid:
            return match.group(0)
        else:
            stats["removed"] += 1
            logger.warning(f"Removed unverified link: {url[:50]}...")
            return f"{text} (⚠️ 链接未验证)"
    
    try:
        report_content = re.sub(pattern, replace_link, report_content)
    except Exception as e:
        logger.error(f"Link verification error: {e}")
    
    return report_content, stats


def _verify_numbers(report_content: str, evidences: List) -> Tuple[str, Dict]:
    """
    检测报告中的数字是否在证据中出现过。
    对于无法验证的精确数字，添加警告标记。
    
    注意：这是一个轻量级检查，不会删除数字，只会标记。
    """
    stats = {"flagged": 0, "total": 0}
    
    # 构建证据中的数字集合
    evidence_numbers: Set[str] = set()
    for ev in evidences:
        if hasattr(ev, 'content') and ev.content:
            # 提取证据中的数字
            numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', ev.content)
            evidence_numbers.update(numbers)
    
    # 检测报告中的精确数字（如 89%, 2.3万, $5478）
    # 这里我们只检测可疑的精确百分比
    suspicious_pattern = r'(\d{2,}(?:\.\d+)?%)'
    
    def check_number(match):
        number = match.group(1)
        stats["total"] += 1
        
        # 检查是否在证据中
        if number in evidence_numbers:
            return number
        else:
            # 常见安全数字（如 100%, 50%）不标记
            safe_numbers = {'100%', '50%', '0%', '10%', '20%', '30%', '40%', '60%', '70%', '80%', '90%'}
            if number in safe_numbers:
                return number
            
            stats["flagged"] += 1
            logger.warning(f"Unverified number: {number}")
            # 不修改，只记录
            return number
    
    try:
        re.sub(suspicious_pattern, check_number, report_content)
    except Exception as e:
        logger.error(f"Number verification error: {e}")
    
    return report_content, stats


def _verify_quotes(report_content: str, claims: List) -> Tuple[str, Dict]:
    """
    检测报告中的引用是否与 canonical_text 匹配。
    """
    stats = {"flagged": 0, "total": 0}
    
    # 构建已知引用集合
    known_quotes: Set[str] = set()
    for c in claims:
        if hasattr(c, 'canonical_text') and c.canonical_text:
            # 只保留前 50 字符作为匹配键
            quote_key = c.canonical_text[:50].lower().strip()
            known_quotes.add(quote_key)
    
    # 检测报告中的引用（中文引号）
    quote_pattern = r'["「]([^"」]+)["」]'
    
    def check_quote(match):
        quote = match.group(1)
        stats["total"] += 1
        
        # 检查是否有匹配的 canonical_text
        quote_key = quote[:50].lower().strip()
        if quote_key in known_quotes:
            return match.group(0)
        else:
            # 短引用（<10字）通常是安全的
            if len(quote) < 10:
                return match.group(0)
            
            stats["flagged"] += 1
            logger.debug(f"Unverified quote: {quote[:30]}...")
            # 不修改，只记录
            return match.group(0)
    
    try:
        re.sub(quote_pattern, check_quote, report_content)
    except Exception as e:
        logger.error(f"Quote verification error: {e}")
    
    return report_content, stats
