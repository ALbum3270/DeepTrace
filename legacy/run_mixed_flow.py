import asyncio
import os
import logging
from dotenv import load_dotenv

# Ensure env is loaded before importing graph
load_dotenv()
# Force backend to mindspider for Weibo
os.environ["WEIBO_BACKEND"] = "mindspider"

from src.graph.workflow import create_graph
from src.core.models.strategy import SearchStrategy
from src.core.models.plan import WeiboCommentDepth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_mixed_flow():
    logger.info("Initializing DeepTrace Graph (Mixed Strategy)...")
    app = create_graph()
    
    query = "DeepSeek"
    logger.info(f"Starting workflow with query: '{query}' (Strategy: MIXED)...")
    
    initial_state = {
        "initial_query": query,
        "search_strategy": SearchStrategy.MIXED, # Force Mixed Strategy
        # We can still hint deep mode for Weibo part
        "weibo_comment_depth": WeiboCommentDepth(mode="deep", suggested_max_comments=200),
        "max_loops": 3, 
        "messages": [],
        "evidences": [],
        "retrieval_plan": None,
    }
    
    try:
        # Run the graph
        final_state = await app.ainvoke(initial_state)
        
        logger.info("Workflow completed.")
        
        evidences = final_state.get("evidences", [])
        steps = final_state.get("steps", [])
        print("\n" + "="*50)
        print("Execution Steps:")
        for step in steps:
            print(f" - {step}")
        print("="*50)
        
        print(f"Final Report for '{query}':")
        print(f"Total Evidence Collected: {len(evidences)}")
        print("="*50)
        
        for i, ev in enumerate(evidences, 1):
            print(f"\n[{i}] {ev.title}")
            print(f"Source: {ev.source_type} ({ev.metadata.get('platform', 'unknown')})")
            print(f"URL: {ev.url}")
            print(f"Snippet: {ev.content[:100]}...")
            if ev.comments:
                print(f"Comments ({len(ev.comments)}):")
                for c in ev.comments[:3]: # Show top 3
                    print(f"  - [{c.author}]: {c.content[:50]}...")
            else:
                print("Comments: None")
            print("-" * 30)
            
        comments = final_state.get("comments", [])
        print("\n" + "="*50)
        print(f"Total Global Comments: {len(comments)}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(run_mixed_flow())
