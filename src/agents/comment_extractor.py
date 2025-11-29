from typing import List, Optional
from uuid import uuid4
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from ..core.models.evidence import Evidence
from ..core.models.comments import Comment
from ..llm.factory import init_llm
from .prompts import COMMENT_EXTRACTOR_SYSTEM_PROMPT

class CommentExtractionResult(BaseModel):
    comments: List[dict] = Field(default_factory=list)

async def extract_comments_from_article(evidence: Evidence) -> List[Comment]:
    """
    使用 LLM 从文章正文中提取评论、引语和观点。
    """
    # 如果没有正文，直接返回空
    content_to_analyze = evidence.full_content or evidence.content
    if not content_to_analyze or len(content_to_analyze) < 50:
        return []

    # 初始化 LLM
    llm = init_llm()
    parser = JsonOutputParser(pydantic_object=CommentExtractionResult)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", COMMENT_EXTRACTOR_SYSTEM_PROMPT),
        ("user", "{text}")
    ])
    
    chain = prompt | llm | parser
    
    try:
        # 截断过长的文本，防止 Token 溢出 (保留前 6000 字符)
        truncated_text = content_to_analyze[:6000]
        
        result = await chain.ainvoke({"text": truncated_text})
        
        raw_comments = result.get("comments", [])
        extracted_comments = []
        
        for raw in raw_comments:
            if not raw.get("content"):
                continue
                
            comment = Comment(
                id=str(uuid4()),
                content=raw["content"],
                author=raw.get("author", "Unknown"),
                role=raw.get("role", "public_opinion"), # 默认 public_opinion
                evidence_id=evidence.id,
                source_url=evidence.url,
                publish_time=None # 暂时留空，后续可尝试解析
            )
            extracted_comments.append(comment)
            
        return extracted_comments
        
    except Exception as e:
        print(f"[WARN] Comment extraction failed for {evidence.url}: {e}")
        return []
