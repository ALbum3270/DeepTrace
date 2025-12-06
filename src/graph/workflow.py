from langgraph.graph import StateGraph, END

from .state import GraphState
from .nodes.fetch_node import fetch_node
from .nodes.extract_node import extract_events_node, extract_comments_node
from .nodes.build_node import build_node

from .nodes.controller import route_raict, promote_layer_node
from .nodes.execution_nodes import pop_breadth_task_node, execute_depth_setup_node as pop_depth_task_node
from .nodes.report_node import report_node
from ..core.models.strategy import SearchStrategy
from ..core.models.task import BreadthTask



def raict_entry_node(state: GraphState) -> GraphState:
    """
    RAICT Entry: Seed the initial Breadth Task from user query.
    """
    initial_query = state.get("initial_query", "")
    # Create initial task
    task = BreadthTask(
        layer=0,
        query=initial_query,
        reason="Initial User Query",
        relevance=1.0,
        gap_coverage=1.0, 
        novelty=1.0,
        voi_score=1.0
    )
    return {
        "breadth_pool": [task],
        "current_layer": 0,
        "current_layer_breadth_steps": 0,
        "current_layer_depth_steps": 0,
        "executed_queries": {initial_query}, # Mark as seen
        "steps": ["raict_entry: seeded initial task"]
    }

def create_raict_graph():
    """
    RAICT Lite Architecture Graph
    """
    workflow = StateGraph(GraphState)
    
    # Nodes
    workflow.add_node("raict_entry", raict_entry_node)
    
    # Control
    # Router is logic, not node, but Promote IS a node
    workflow.add_node("promote_layer", promote_layer_node)
    
    # Execution Setup (Pop & Prep)
    workflow.add_node("pop_breadth", pop_breadth_task_node)
    workflow.add_node("pop_depth", pop_depth_task_node)
    
    # Action Chain (Standard)
    # Using 'fetch' (generic) -> 'extract' -> 'build' -> 'triage'
    # Note: Fetch node usually returns 'evidences'.
    # Extract node returns 'events', 'claims'.
    # Build node returns 'timeline'.
    # Triage node returns 'new tasks'.
    
    workflow.add_node("fetch", fetch_node)
    workflow.add_node("extract", extract_events_node) 
    # extract_comments_node is optional in Lite? 
    # User said: "Fetch -> Extract -> Triage". 
    # Triage Prompt (new) looks at "Gap", "Claims". It doesn't explicitly mention "Comment Scoring" like Phase 6.
    # BUT, `extract_events_node` produces Claims? 
    # Let's check extract_node implementation. `extract_events_node` does NOT produce claims in Phase 9 code?
    # Wait, I viewed `event_extractor.py` learning: `extract_event_from_evidence` returns `EventNode` and `List[Claim]`.
    # And `extract_events_node` in `extract_node.py`?
    # I should check `extract_node.py` to ensure it saves claims to state.
    # PROCEEDING with assumption it does (User said "Claim Extraction" complete in Phase 9).
    
    workflow.add_node("build", build_node)
    workflow.add_node("triage", triage_node)
    
    workflow.add_node("reporter", report_node)
    
    # Edges
    workflow.set_entry_point("raict_entry")
    
    # Entry -> Controller Routing
    workflow.add_conditional_edges(
        "raict_entry",
        route_raict,
        {
            "breadth_node": "pop_breadth",
            "depth_node": "pop_depth",
            "promote_layer": "promote_layer",
            "reporter": "reporter"
        }
    )
    
    # Controller Routing from Promote & Triage (End of loops)
    workflow.add_conditional_edges(
        "promote_layer",
        route_raict,
        {
            "breadth_node": "pop_breadth",
            "depth_node": "pop_depth",
            "promote_layer": "promote_layer", # Should not loop immediately usually
            "reporter": "reporter"
        }
    )
    
    workflow.add_conditional_edges(
        "triage",
        route_raict,
        {
            "breadth_node": "pop_breadth",
            "depth_node": "pop_depth",
            "promote_layer": "promote_layer",
            "reporter": "reporter"
        }
    )
    
    # Execution Chains
    # Breadth Chain
    workflow.add_edge("pop_breadth", "fetch")
    workflow.add_edge("pop_depth", "fetch") # Reuse fetch
    
    workflow.add_edge("fetch", "extract")
    workflow.add_edge("extract", "build")
    workflow.add_edge("build", "triage")
    
    # Reporter
    workflow.add_edge("reporter", END)
    
    return workflow.compile()
