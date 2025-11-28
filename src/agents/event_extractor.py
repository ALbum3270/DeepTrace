"""
Event Extractor Agent: 负责从证据中提取事件节点。
"""
import json
from typing import Optional
from ..core.models.evidence import Evidence
from ..core.models.events import EventNode, EventStatus
from ..config.settings import settings
from .prompts import EVENT_EXTRACTOR_SYSTEM_PROMPT
from ..llm.factory import init_llm
from langchain_core.prompts import ChatPromptTemplate


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

async def extract_event_from_evidence(evidence: Evidence) -> Optional[EventNode]:
    """使用 LLM（Qwen）通过 Function Calling 提取结构化事件信息。

    Args:
        evidence: Evidence 对象

    Returns:
        EventNode 实例，或在失败时返回 None。
    """
    client = init_llm()

    # 构造完整的提示内容（直接格式化，避免变量占位）
    user_message = f"""Evidence Content: {evidence.content}
Publish Time: {evidence.publish_time}
Source Type: {evidence.source.value}
URL: {evidence.url if evidence.url else 'N/A'}
Title: {evidence.title if evidence.title else 'N/A'}

请分析以上证据，提取其中描述的关键事件。注意：Source Type 只是大类（news/weibo/xhs），请从 URL、Title 或 Content 中推断具体的媒体名称（如：新华社、人民日报、BBC、微博用户@XXX）。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", EVENT_EXTRACTOR_SYSTEM_PROMPT),
        ("user", user_message)
    ])

    try:
        # 使用结构化输出
        structured_llm = client.with_structured_output(EventNode)
        chain = prompt | structured_llm
        
        # 调用链式执行（不传递变量，因为已经在 prompt 中格式化）
        result = await chain.ainvoke({})

        # result 可能是 EventNode 实例或普通 dict
        if isinstance(result, EventNode):
            event = result
        else:
            # 若返回 dict，手动构造 EventNode
            time_value = None
            if isinstance(result, dict) and result.get("time"):
                from datetime import datetime
                try:
                    time_str = _sanitize_time_string(result["time"])
                    if time_str:
                        time_value = datetime.fromisoformat(time_str)
                except Exception:
                    pass
            event = EventNode(
                title=result["title"] if isinstance(result, dict) else getattr(result, "title"),
                description=result["description"] if isinstance(result, dict) else getattr(result, "description"),
                time=time_value,
                source=result.get("source") if isinstance(result, dict) else getattr(result, "source", None),
                actors=result.get("actors", []) if isinstance(result, dict) else getattr(result, "actors", []),
                tags=result.get("tags", []) if isinstance(result, dict) else getattr(result, "tags", []),
                status=EventStatus(result["status"] if isinstance(result, dict) else getattr(result, "status")),
                confidence=result["confidence"] if isinstance(result, dict) else getattr(result, "confidence"),
                evidence_ids=[evidence.id]
            )
        
        # 优化 source
        if event:
            event.source = _refine_source(event.source, evidence)

        # 确保 evidence_ids 被正确设置
        if event and not event.evidence_ids:
            event.evidence_ids = [evidence.id]
            
        return event
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Event extraction failed: {error_msg[:200]}")
        
        # 检查是否是嵌套 JSON 问题
        if "Field required" in error_msg and "EventNode" in error_msg:
            print("[WARN] Detected nested JSON response, attempting to fix...")
            try:
                # 尝试获取原始响应并手动解析
                raw_chain = prompt | client
                raw_result = await raw_chain.ainvoke({})
                content = raw_result.content if hasattr(raw_result, 'content') else str(raw_result)
                
                # 验证 content 不为空
                if not content or not content.strip():
                    print("[WARN] LLM returned empty response, skipping this evidence")
                    return None
                
                data = json.loads(content)
                
                # 如果 LLM 返回了嵌套结构 {"EventNode": {...}} 或 {"event_node": {...}}，提取内层
                if "EventNode" in data and isinstance(data["EventNode"], dict):
                    data = data["EventNode"]
                elif "event_node" in data and isinstance(data["event_node"], dict):
                    data = data["event_node"]
                
                # 手动构造 EventNode
                time_value = None
                if data.get("time"):
                    from datetime import datetime
                    try:
                        time_str = _sanitize_time_string(data["time"])
                        if time_str:
                            time_value = datetime.fromisoformat(time_str)
                    except Exception:
                        pass
                
                event = EventNode(
                    title=data.get("title", "未知事件"),
                    description=data.get("description", ""),
                    time=time_value,
                    source=_refine_source(data.get("source"), evidence),
                    actors=data.get("actors", []),
                    tags=data.get("tags", []),
                    status=EventStatus(data.get("status", "confirmed")),
                    confidence=data.get("confidence", 0.5),
                    evidence_ids=[evidence.id]
                )
                return event
            except json.JSONDecodeError:
                # JSON 解析失败，静默跳过（不打印 traceback）
                print("[WARN] Failed to parse LLM response as JSON, skipping this evidence")
                return None
            except Exception as e2:
                print(f"[WARN] Fallback parsing failed: {str(e2)[:100]}")
                return None
        
        return None
