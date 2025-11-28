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
Source: {evidence.source.value}

请分析以上证据，提取其中描述的关键事件。"""

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
                    time_value = datetime.fromisoformat(result["time"])
                except Exception:
                    pass
            event = EventNode(
                title=result["title"] if isinstance(result, dict) else getattr(result, "title"),
                description=result["description"] if isinstance(result, dict) else getattr(result, "description"),
                time=time_value,
                actors=result.get("actors", []) if isinstance(result, dict) else getattr(result, "actors", []),
                tags=result.get("tags", []) if isinstance(result, dict) else getattr(result, "tags", []),
                status=EventStatus(result["status"] if isinstance(result, dict) else getattr(result, "status")),
                confidence=result["confidence"] if isinstance(result, dict) else getattr(result, "confidence"),
                evidence_ids=[evidence.id]
            )
        
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
                data = json.loads(content)
                
                # 如果 LLM 返回了嵌套结构 {"EventNode": {...}}，提取内层
                if "EventNode" in data and isinstance(data["EventNode"], dict):
                    data = data["EventNode"]
                
                # 手动构造 EventNode
                time_value = None
                if data.get("time"):
                    from datetime import datetime
                    try:
                        time_value = datetime.fromisoformat(data["time"])
                    except Exception:
                        pass
                
                event = EventNode(
                    title=data.get("title", "未知事件"),
                    description=data.get("description", ""),
                    time=time_value,
                    actors=data.get("actors", []),
                    tags=data.get("tags", []),
                    status=EventStatus(data.get("status", "confirmed")),
                    confidence=data.get("confidence", 0.5),
                    evidence_ids=[evidence.id]
                )
                return event
            except Exception as e2:
                print(f"[ERROR] Fallback parsing also failed: {e2}")
                import traceback
                traceback.print_exc()
        
        return None
