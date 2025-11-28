"""
Event Extractor Agent: 负责从证据中提取事件节点。
"""
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from ..core.models.evidence import Evidence
from ..core.models.events import EventNode
from ..llm.factory import init_llm
from .prompts import EVENT_EXTRACTOR_SYSTEM_PROMPT


async def extract_event_from_evidence(evidence: Evidence) -> Optional[EventNode]:
    """
    使用 LLM 从证据中提取事件节点。
    
    Args:
        evidence: 证据对象
        
    Returns:
        EventNode 对象，如果提取失败返回 None
    """
    llm = init_llm(temperature=0.0)
    
    # 使用 with_structured_output 强制输出 EventNode 结构
    # 注意：这需要模型支持 Function Calling (如 GPT-4o, DeepSeek V2.5)
    structured_llm = llm.with_structured_output(EventNode)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", EVENT_EXTRACTOR_SYSTEM_PROMPT),
        ("human", "Evidence Content: {content}\nPublish Time: {publish_time}\nSource: {source}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = await chain.ainvoke({
            "content": evidence.content,
            "publish_time": str(evidence.publish_time),
            "source": evidence.source.value
        })
        
        # 补充 evidence_id 关联
        if result:
            result.evidence_ids = [evidence.id]
            
        return result
    except Exception as e:
        # 生产环境应该记录日志
        print(f"Error extracting event: {e}")
        return None
