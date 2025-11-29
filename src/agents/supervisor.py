from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from ..core.models.strategy import SearchStrategy
from ..llm.factory import init_llm

class SupervisorOutput(BaseModel):
    """Supervisor Agent 的输出结构"""
    strategy: SearchStrategy = Field(..., description="选择的检索策略")
    platforms: List[str] = Field(..., description="涉及的平台列表，如 ['generic'], ['weibo'], ['xhs']")
    reason: str = Field(default="", description="选择该策略的理由")

SUPERVISOR_SYSTEM_PROMPT = """你是一个智能检索路由助手 (Supervisor)。
你的任务是分析用户的查询意图，并选择最合适的检索策略。

可选策略 (SearchStrategy):
1. GENERIC: 通用搜索。适用于一般性新闻、事件发布、科普查询。
   - 例子: "OpenAI Sora 发布", "Python 教程", "美国大选最新消息"
2. WEIBO: 微博专项搜索。适用于查找公众舆论、热搜话题、网友评论。
   - 例子: "Sora 微博 评论", "黑神话悟空 微博热搜", "某明星 瓜"
3. XHS: 小红书专项搜索。适用于查找测评、生活经验、种草/避雷、详细教程。
   - 例子: "Sora 小红书 测评", "iPhone 16 避雷", "旅游攻略"
4. MIXED: 混合模式。适用于既需要官方信息，又需要社交媒体舆论的复杂查询。
   - 例子: "Sora 发布后的各方反应", "iPhone 16 参数及用户评价"

输出规则:
- 必须返回 JSON 格式。
- strategy 必须是上述枚举值之一。
- platforms 字段应包含涉及的具体平台标识 (generic, weibo, xhs)。
"""

async def supervise_query(query: str) -> SupervisorOutput:
    """
    分析查询并返回检索策略。
    """
    client = init_llm()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_SYSTEM_PROMPT),
        ("user", "User Query: {query}")
    ])
    
    try:
        structured_llm = client.with_structured_output(SupervisorOutput)
        chain = prompt | structured_llm
        result = await chain.ainvoke({"query": query})
        
        if result:
            return result
            
        # Fallback if None
        print("[WARN] Supervisor returned None, falling back to GENERIC")
        return SupervisorOutput(
            strategy=SearchStrategy.GENERIC,
            platforms=["generic"],
            reason="Fallback: LLM returned None"
        )
        
    except Exception as e:
        print(f"[ERROR] Supervisor failed: {e}, falling back to GENERIC")
        return SupervisorOutput(
            strategy=SearchStrategy.GENERIC,
            platforms=["generic"],
            reason=f"Fallback: Error occurred - {str(e)}"
        )
