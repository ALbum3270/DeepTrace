"""
Event Extractor Agent: 负责从证据中提取事件节点。
"""
import json
from typing import Optional
from openai import AsyncOpenAI
from ..core.models.evidence import Evidence
from ..core.models.events import EventNode, EventStatus
from ..config.settings import settings
from .prompts import EVENT_EXTRACTOR_SYSTEM_PROMPT


async def extract_event_from_evidence(evidence: Evidence) -> Optional[EventNode]:
    """
    使用 LLM 从证据中提取事件节点（使用Function Calling）。
    
    Args:
        evidence: 证据对象
        
    Returns:
        EventNode 对象，如果提取失败返回 None
    """
    # 初始化 Qwen API 客户端
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    
    # 定义 EventNode 的 JSON Schema（用于 Function Calling）
    event_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "事件的简短标题，如'首个负面反馈出现'"
            },
            "description": {
                "type": "string",
                "description": "事件的详细描述"
            },
            "time": {
                "type": "string",
                "description": "事件发生时间（ISO格式），如果无法确定则为null",
                "nullable": True
            },
            "actors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "参与主体列表（人、机构、品牌）"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "事件标签，如 origin/explosion/brand_response"
            },
            "status": {
                "type": "string",
                "enum": ["confirmed", "inferred", "hypothesis"],
                "description": "事件状态：confirmed（确认发生）、inferred（推测）、hypothesis（假设）"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "置信度（0.0 ~ 1.0）"
            }
        },
        "required": ["title", "description", "status", "confidence"]
    }
    
    # 构造 Function Calling 的 tools 参数
    tools = [{
        "type": "function",
        "function": {
            "name": "extract_event",
            "description": "从证据文本中提取事件节点的结构化信息",
            "parameters": event_schema
        }
    }]
    
    # 构造消息
    user_message = f"""Evidence Content: {evidence.content}
Publish Time: {evidence.publish_time}
Source: {evidence.source.value}

请分析以上证据，提取其中描述的关键事件。"""
    
    try:
        # 调用 Qwen API（使用 Function Calling）
        response = await client.chat.completions.create(
            model=settings.model_name,
            messages=[
                {"role": "system", "content": EVENT_EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "extract_event"}}
        )
        
        # 解析 Function Call 结果
        message = response.choices[0].message
        if not message.tool_calls:
            print("[WARN] LLM did not return tool_calls")
            return None
        
        tool_call = message.tool_calls[0]
        arguments = json.loads(tool_call.function.arguments)
        
        # 解析时间
        time_value = None
        if arguments.get("time"):
            from datetime import datetime
            try:
                time_value = datetime.fromisoformat(arguments["time"])
            except:
                pass
        
        # 构造 EventNode
        event = EventNode(
            title=arguments["title"],
            description=arguments["description"],
            time=time_value,
            actors=arguments.get("actors", []),
            tags=arguments.get("tags", []),
            status=EventStatus(arguments["status"]),
            confidence=arguments["confidence"],
            evidence_ids=[evidence.id]
        )
        
        return event
        
    except Exception as e:
        print(f"[ERROR] Event extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None
