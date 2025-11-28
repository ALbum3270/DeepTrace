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
    # 初始化统一的 LLM 客户端
    client = init_llm()

    # 定义 EventNode 的 JSON Schema（用于 Function Calling）
    event_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "事件的简短标题，如'首个负面反馈出现'"},
            "description": {"type": "string", "description": "事件的详细描述"},
            "time": {"type": "string", "description": "事件发生时间（ISO格式），如果无法确定则为null", "nullable": True},
            "actors": {"type": "array", "items": {"type": "string"}, "description": "参与主体列表（人、机构、品牌）"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "事件标签，如 origin/explosion/brand_response"},
            "status": {"type": "string", "enum": ["confirmed", "inferred", "hypothesis"], "description": "事件状态：confirmed（确认发生）、inferred（推测）、hypothesis（假设）"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "置信度（0.0 ~ 1.0）"}
        },
        "required": ["title", "description", "status", "confidence"]
    }

    # 构造系统+用户消息的 Prompt
    user_message = f"""Evidence Content: {evidence.content}\nPublish Time: {evidence.publish_time}\nSource: {evidence.source.value}\n\n请分析以上证据，提取其中描述的关键事件。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", EVENT_EXTRACTOR_SYSTEM_PROMPT),
        ("user", user_message)
    ])

    try:
        # 将 LLM 包装为结构化输出模型
        structured_llm = client.with_structured_output(event_schema)
        # 组合 Prompt 与 LLM，得到 RunnableSequence
        chain = prompt | structured_llm
        # 调用链式执行，传入证据信息
        result = await chain.ainvoke({
            "content": evidence.content,
            "publish_time": str(evidence.publish_time),
            "source": evidence.source.value
        })

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
        
        # 确保 evidence_ids 被正确设置（针对直接返回 EventNode 的情况）
        if event and not event.evidence_ids:
            event.evidence_ids = [evidence.id]
            
        return event
    except Exception as e:
        print(f"[ERROR] Event extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None
