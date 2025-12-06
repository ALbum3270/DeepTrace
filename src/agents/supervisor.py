from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from ..core.models.strategy import SearchStrategy
from ..core.models.plan import WeiboCommentDepth
from ..llm.factory import init_llm

class SupervisorOutput(BaseModel):
    """Supervisor Agent 的输出结构"""
    strategy: SearchStrategy = Field(..., description="选择的检索策略")
    platforms: List[str] = Field(..., description="涉及的平台列表，如 ['generic'], ['weibo'], ['xhs']")
    reason: str = Field(default="", description="选择该策略的理由")
    weibo_comment_depth: WeiboCommentDepth = Field(default_factory=WeiboCommentDepth, description="微博评论抓取深度配置")
    evidence_depth: Literal["quick", "balanced", "deep"] = Field(default="balanced", description="证据抓取深度: quick/balanced/deep")

SUPERVISOR_SYSTEM_PROMPT = """你是一个智能检索路由助手 (Supervisor)。
你的任务是分析用户的查询意图，并选择最合适的检索策略和抓取深度。

可选策略 (SearchStrategy):
1. GENERIC: 通用搜索。适用于一般性新闻、事件发布、科普查询。
   - 例子: "OpenAI Sora 发布", "Python 教程", "美国大选最新消息"
2. WEIBO: 微博专项搜索。适用于查找公众舆论、热搜话题、网友评论。
   - 例子: "Sora 微博 评论", "黑神话悟空 微博热搜", "某明星 瓜"
3. XHS: 小红书专项搜索。适用于查找测评、生活经验、种草/避雷、详细教程。
   - 例子: "Sora 小红书 测评", "iPhone 16 避雷", "旅游攻略"
4. MIXED: 混合模式。适用于既需要官方信息，又需要社交媒体舆论的复杂查询。
   - 例子: "Sora 发布后的各方反应", "iPhone 16 参数及用户评价"

证据抓取深度 (evidence_depth):
- quick: 快速模式 (5条结果, 3条深度抓取)。适用于简单问题、快速验证。
- balanced: 平衡模式 (10条结果, 5条深度抓取)。适用于一般调查 (默认)。
- deep: 深度模式 (15条结果, 8条深度抓取)。适用于复杂事件、深度挖掘、争议话题。

微博评论深度 (WeiboCommentDepth):
- mode="shallow": 仅抓取首页热评 (默认)。适用于一般热点。
- mode="deep": 深度抓取 (自动翻页)。适用于极具争议、需要分析不同观点的话题。
- mode="skip": 不抓取评论。
- suggested_max_comments: 建议抓取的数量 (仅作为 hint)，例如 50, 200。

输出规则:
- 必须返回 JSON 格式。
- strategy 必须是上述枚举值之一。
- platforms 字段应包含涉及的具体平台标识 (generic, weibo, xhs)。
- evidence_depth 根据查询复杂度选择 quick/balanced/deep。
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
            reason="Fallback: LLM returned None",
            evidence_depth="balanced"
        )
        
    except Exception as e:
        print(f"[ERROR] Supervisor failed: {e}, falling back to GENERIC")
        return SupervisorOutput(
            strategy=SearchStrategy.GENERIC,
            platforms=["generic"],
            reason=f"Fallback: Error occurred - {str(e)}",
            evidence_depth="balanced"
        )

