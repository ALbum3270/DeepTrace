"""
Event Extractor Agent: 负责从证据中提取事件节点。
"""
import json
from typing import Optional
from ..core.models.evidence import Evidence
from ..core.models.events import EventNode, EventStatus
from ..core.models.claim import Claim
from ..core.models.credibility import evaluate_credibility
from ..config.settings import settings
from .prompts import EVENT_EXTRACTOR_SYSTEM_PROMPT
from ..llm.factory import init_llm, init_json_llm
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def _sanitize_quote(quote: str) -> str:
    """
    清理并标准化原文引用：
    1. 移除换行符
    2. 截断至最大长度
    3. 去除首尾空白
    """
    if not quote:
        return ""
    # 移除换行符和多余空白
    sanitized = quote.replace('\n', ' ').replace('\r', ' ')
    sanitized = ' '.join(sanitized.split())  # 合并多个空格
    sanitized = sanitized.strip()
    # 使用配置文件中的长度限制
    max_length = settings.MAX_CANONICAL_TEXT_LENGTH
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "…"
    return sanitized


def _sanitize_time_string(time_str: str) -> Optional[str]:
    """
    清理和标准化时间字符串为 ISO 8601 格式。
    
    Returns:
        标准化后的时间字符串，或 None（如果无法解析）
    """
    if not time_str or not isinstance(time_str, str):
        return None
    
    time_str = time_str.strip()
    
    # 空字符串 -> None
    if not time_str:
        return None
    
    # 不完整的日期（如 "2024-04"）-> 补全为月初
    if len(time_str) == 7 and time_str.count('-') == 1:
        return f"{time_str}-01"
    
    # 已经是标准格式 -> 直接返回
    if len(time_str) >= 10 and time_str[4] == '-' and time_str[7] == '-':
        return time_str
    
    # 其他情况 -> 返回 None（让 LLM 学习）
    return None


def _refine_source(source: Optional[str], evidence: Evidence) -> str:
    """优化来源字段，避免 generic terms"""
    if not source:
        return "未知来源"
    
    generic_terms = ["news", "weibo", "social_media", "web", "internet", "report", "unknown"]
    if source.lower() in generic_terms:
        # 尝试从 URL 提取域名
        if evidence.url:
            if "xinhuanet.com" in evidence.url: return "新华社"
            if "people.com.cn" in evidence.url: return "人民日报"
            if "cctv.com" in evidence.url: return "央视网"
            if "sina.com" in evidence.url: return "新浪网"
            if "weibo.com" in evidence.url: return "微博"
            
            try:
                from urllib.parse import urlparse
                domain = urlparse(evidence.url).netloc
                return domain.replace("www.", "")
            except:
                pass
                
        # 尝试从 Title 提取（如 "Title - Source"）
        if evidence.title and " - " in evidence.title:
            possible_source = evidence.title.split(" - ")[-1].strip()
            if len(possible_source) < 20:  # 避免提取到长标题的一部分
                return possible_source
                
    return source

def heuristic_importance(text: str, source_type: str, query: str) -> float:
    """
    计算声明的重要性分数 (0-100)。
    """
    score = 50.0
    
    # 1. 关键词加权
    keywords = ["正式", "官宣", "否认", "谣言", "事故原因", "发布", "声明", "致歉", "回应", "证实", "确认"]
    for kw in keywords:
        if kw in text:
            score += 20
            break
            
    # 2. Query 相关性 (简单包含)
    if query and query in text:
        score += 30
        
    return min(100.0, max(0.0, score))

async def extract_event_from_evidence(evidence: Evidence, query: str = "") -> Tuple[Optional[EventNode], List[Claim]]:
    """使用 LLM（Qwen）通过 JSON Mode 提取结构化事件信息和关键声明。

    Args:
        evidence: Evidence 对象
        query: 当前查询 query (用于重要性评分)

    Returns:
        (EventNode, List[Claim])
    """
    # 使用 JSON Mode LLM，确保输出是合法 JSON
    client = init_json_llm()

    # JSON 示例模板（使用双花括号转义，避免被 ChatPromptTemplate 解析为变量）
    # JSON 示例模板（直接作为变量传递，无需双花括号转义）
    json_template = """
{
    "title": "事件标题",
    "description": "事件详细描述",
    "time": "YYYY-MM-DD 或 YYYY-MM-DD HH:MM 或 null",
    "source": "具体来源名称",
    "actors": ["参与者1", "参与者2"],
    "tags": ["标签1", "标签2"],
    "status": "confirmed 或 inferred 或 hypothesis",
    "confidence": "0.0-1.0 之间的数字",
    "evidence_type": "official/media/rumor/opinion",
    "phase": "plan/announce/release/upgrade/unknown",
    "date_precision": "day/month/year/approx/unknown",
    "claims": [
        {
            "claim": "归纳后的关键声明",
            "quote": "从原文中直接复制的句子或短语（必须是原文子串）"
        }
    ]
}"""

    # 构造完整的提示内容（不使用 f-string 内嵌 JSON 示例）
    user_content = f"""Evidence Content: {evidence.content}
Publish Time: {evidence.publish_time}
Source Type: {evidence.source.value}
URL: {evidence.url if evidence.url else 'N/A'}
Title: {evidence.title if evidence.title else 'N/A'}

请分析以上证据，提取其中描述的关键事件。返回 JSON 格式。

注意：Source Type 只是大类（news/weibo/xhs），请从 URL、Title 或 Content 中推断具体的媒体名称。"""

    # 组合 user message
    user_message_content = user_content + "\n\nJSON 结构示例：" + json_template

    prompt = ChatPromptTemplate.from_messages([
        ("system", EVENT_EXTRACTOR_SYSTEM_PROMPT),
        ("user", "{input}")  # 使用变量占位符
    ])

    try:
        chain = prompt | client
        result = await chain.ainvoke({"input": user_message_content})
        
        # 解析 JSON 响应
        content = result.content if hasattr(result, 'content') else str(result)
        
        if not content or not content.strip():
            print("[WARN] LLM returned empty response, skipping this evidence")
            return None
        
        data = json.loads(content)
        
        # 处理可能的嵌套结构
        if "EventNode" in data and isinstance(data["EventNode"], dict):
            data = data["EventNode"]
        elif "event_node" in data and isinstance(data["event_node"], dict):
            data = data["event_node"]
        elif "event" in data and isinstance(data["event"], dict):
            data = data["event"]
        
        # 解析时间
        time_value = None
        if data.get("time"):
            from datetime import datetime
            try:
                time_str = _sanitize_time_string(data["time"])
                if time_str:
                    time_value = datetime.fromisoformat(time_str)
            except Exception:
                pass
        
        # Phase 18: Rule-Based Evidence Type Override
        ev_type = data.get("evidence_type", "media")
        
        # 1. Force Official if domain in whitelist
        if evidence.url:
            from urllib.parse import urlparse
            try:
                domain = urlparse(evidence.url).netloc.lower()
                # Check exact or subdomain match
                if any(domain == d or domain.endswith("." + d) for d in settings.OFFICIAL_DOMAINS):
                    ev_type = "official"
            except:
                pass
                
        # 2. Force Rumor if keywords detected (and not already official)
        if ev_type != "official":
            rumor_keywords = ["知情人士", "消息称", "爆料", "sources say", "rumor", "leak"]
            if any(kw in (data.get("description") or "") for kw in rumor_keywords):
                ev_type = "rumor"

        # Phase 18: Model Family & Version Line Inference
        text_content = (data.get("title") or "") + " " + (data.get("description") or "")
        text_lower = text_content.lower()
        
        model_family = None
        version_line = None
        
        for fam, members in settings.VERSION_FAMILIES.items():
            if any(m in text_lower for m in members):
                model_family = fam
                # Try to find specific version
                for m in members:
                    if m in text_lower:
                        version_line = m
                        break
                break

        # 构造 EventNode
        event = EventNode(
            title=data.get("title", "未知事件"),
            description=data.get("description", ""),
            time=time_value,
            source=_refine_source(data.get("source"), evidence),
            actors=data.get("actors", []),
            tags=data.get("tags", []),
            status=EventStatus(data.get("status", "confirmed")),
            confidence=float(data.get("confidence", 0.5)),
            evidence_ids=[evidence.id],
            # Phase 18 fields
            evidence_type=ev_type,
            phase=data.get("phase", "unknown"),
            date_precision=data.get("date_precision", "unknown"),
            model_family=model_family,
            version_line=version_line
        )
        
        claims = []
        raw_claims = data.get("claims", [])
        if isinstance(raw_claims, list):
            source_credibility = evaluate_credibility(evidence.url, evidence.content)
            for item in raw_claims:
                # 向后兼容：同时支持字符串格式和 {claim, quote} 格式
                if isinstance(item, str):
                    # 旧格式：纯字符串
                    claim_text = item.strip()
                    quote_text = ""
                elif isinstance(item, dict):
                    # 新格式：{claim, quote} 对象
                    claim_text = item.get("claim", "").strip()
                    quote_text = item.get("quote", "").strip()
                else:
                    continue
                
                if not claim_text:
                    continue
                    
                importance = heuristic_importance(claim_text, evidence.source.value, query)
                
                claims.append(Claim(
                    content=claim_text,
                    canonical_text=_sanitize_quote(quote_text),  # 清理并截断原文引用
                    source_evidence_id=evidence.id,
                    credibility_score=source_credibility.score,
                    importance=importance,
                    status="unverified"
                ))

        return event, claims
        
    except json.JSONDecodeError as e:
        print(f"[WARN] Failed to parse LLM response as JSON: {str(e)[:100]}")
        return None, []
    except Exception as e:
        print(f"[ERROR] Event extraction failed: {str(e)[:200]}")
        return None, []

