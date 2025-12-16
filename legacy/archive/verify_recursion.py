import asyncio
import os
import sys
import logging
from datetime import datetime

# Add current directory to path
sys.path.append(os.getcwd())

from src.core.models.timeline import Timeline, EventNode, OpenQuestion
from src.core.models.evidence import Evidence
from src.agents.retrieval_planner import plan_retrieval
from src.config.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO)

async def main():
    print("--- Verifying Recursion Safety & Context Enrichment ---")
    
    # 1. Mock Timeline
    timeline = Timeline(
        events=[
            EventNode(id="e1", title="DeepSeek 发布新模型", description="DeepSeek 发布了 R1 模型", time=datetime(2025, 1, 1)),
            EventNode(id="e2", title="引发讨论", description="引发关于开源闭源的讨论", time=datetime(2025, 1, 2))
        ],
        open_questions=[
            OpenQuestion(id="q1", question="DeepSeek 的训练数据来源是什么？", related_event_ids=["e1"])
        ]
    )
    
    # 2. Mock Evidence with Comment Insights
    ev1 = Evidence(
        url="http://weibo.com/1",
        title="DeepSeek 到底是不是套壳？",
        content="...",
        metadata={
            "comment_insights": {
                "top_opinion_clusters": [
                    {"summary": "质疑数据来源不明", "size": 50},
                    {"summary": "支持国产创新", "size": 30}
                ],
                "new_entities": ["某知名高校", "HuggingFace"],
                "controversy_signals": {"has_strong_disagreement": True}
            }
        }
    )
    
    # 3. Test Recursion Safety
    seen_queries = {"deepseek 训练数据", "deepseek 套壳"}
    print(f"Initial seen_queries: {seen_queries}")
    
    # We expect the planner to generate queries related to "某知名高校" or "HuggingFace" 
    # and NOT generate "DeepSeek 训练数据" (duplicate).
    
    plan = await plan_retrieval(timeline, [ev1], seen_queries)
    
    print("\n--- Planner Result ---")
    print(f"Thought Process: {plan.thought_process}")
    print(f"Generated Queries: {len(plan.queries)}")
    for q in plan.queries:
        print(f"- Query: {q.query} | Rationale: {q.rationale}")
        
        # Verify deduplication logic (manual check)
        norm_q = q.query.strip().lower()
        if norm_q in seen_queries:
            print(f"  [FAIL] Duplicate query generated: {q.query}")
        else:
            print("  [PASS] New query")

    # Verify limits
    if len(plan.queries) > settings.MAX_NEW_QUERIES_PER_ROUND:
         print(f"  [FAIL] Exceeded MAX_NEW_QUERIES_PER_ROUND ({settings.MAX_NEW_QUERIES_PER_ROUND})")
    else:
         print(f"  [PASS] Respects limit ({len(plan.queries)} <= {settings.MAX_NEW_QUERIES_PER_ROUND})")

if __name__ == "__main__":
    asyncio.run(main())
