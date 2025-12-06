
import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

# Ensure safe import
sys.path.append(os.getcwd())

from datetime import datetime
from src.graph.workflow import create_raict_graph
from src.graph.state import GraphState
from src.config.settings import settings
from src.core.storage import StorageManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
# Reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)

async def main():
    load_dotenv()
    
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = input("Enter query (e.g., 'Latest OpenAI news'): ") or "OpenAI latest news"
    
    # Initialize State
    initial_state: GraphState = {
        "initial_query": query,
        "current_query": query, # Will be overwritten by controller/pop but useful for entry
        
        # Init empty collections
        "evidences": [],
        "events": [],
        "claims": [],
        "comments": [],
        "executed_queries": set(),
        "verified_claim_ids": set(),
        "seen_queries": set(),
        "steps": [],
        
        # Init Pools (Though raict_entry does this)
        "breadth_pool": [],
        "depth_pool": [],
        
        # Init Counters
        "current_layer": 0,
        "current_layer_breadth_steps": 0,
        "current_layer_depth_steps": 0,
        
        # Config (Optional overrides)
        "max_loops": 100 # Safety hard limit for recursion
    }
    
    print(f"🚀 Starting RAICT Lite Investigation for: {query}")
    print(f"   Max Layers: {settings.MAX_LAYERS}")
    
    app = create_raict_graph()
    
    # Increase recursion limit because of the loop nature
    config = {"recursion_limit": 100}
    
    # Create Storage Manager
    storage = StorageManager()
    run_dir = storage.start_run(query)
    print(f"📁 Run Directory created: {run_dir}")
    
    start_time = datetime.now()
    
    try:
        final_state = await app.ainvoke(initial_state, config=config)
        end_time = datetime.now()
        
        print("\n\n✅ Investigation Complete!")
        print("-" * 50)
        
        # Save Results
        if "timeline" in final_state and final_state["timeline"]:
            print(f"Timeline Events: {len(final_state['timeline'].events)}")
            print(final_state["timeline"].to_markdown())
            storage.save_timeline(run_dir, final_state["timeline"])
        
        if "evidences" in final_state:
            storage.save_evidences(run_dir, final_state["evidences"])
            
        print("-" * 50)
        
        # Print Final Report
        if "final_report" in final_state:
            print("📝 Final Report:")
            print(final_state["final_report"])
            
            # Save to file using StorageManager
            storage.save_report(run_dir, final_state["final_report"])
            print(f"\n💾 Report saved to {run_dir / 'report.md'}")
        
        # Save Meta
        storage.save_meta(
            run_dir,
            topic=query,
            start_time=start_time,
            end_time=end_time,
            model=settings.model_name,
            config={"max_layers": settings.MAX_LAYERS, "recursion_limit": 100},
            stats={
                "events_count": len(final_state.get("events", [])),
                "claims_count": len(final_state.get("claims", [])),
                "evidences_count": len(final_state.get("evidences", []))
            }
        )
            
    except Exception as e:
        print(f"\n❌ Execution Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
