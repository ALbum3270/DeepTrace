"""
Worker Subgraph for DeepTrace V2.
Encapsulates the investigation workflow: Fetch -> Extract -> Compress.
"""

from langgraph.graph import StateGraph, START, END
from src.graph.state_v2 import WorkerState
from src.graph.nodes.worker_nodes import fetch_node_v2, extract_node_v2
from src.graph.nodes.compressor import compress_node


def build_worker_subgraph():
    """Compiles the Worker Subgraph."""
    workflow = StateGraph(WorkerState)

    # 1. Add Nodes
    workflow.add_node("fetch", fetch_node_v2)
    workflow.add_node("extract", extract_node_v2)
    workflow.add_node("compress", compress_node)

    # 2. Add Edges (Linear Pipeline)
    workflow.add_edge(START, "fetch")
    workflow.add_edge("fetch", "extract")
    workflow.add_edge("extract", "compress")
    workflow.add_edge("compress", END)

    # 3. Compile
    return workflow.compile()


# Singleton instance for easy import
worker_app = build_worker_subgraph()
