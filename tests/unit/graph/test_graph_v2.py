
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from src.graph.graph_v2 import route_supervisor, enter_worker, exit_worker
from src.graph.state_v2 import GlobalState, WorkerState

def test_route_supervisor():
    """Verify conditional edge routing."""
    
    # 1. Final Answer -> Finalizer
    state_final = {"messages": [AIMessage(content="Done", tool_calls=[
        {"name": "FinalAnswer", "args": {}, "id": "1"}
    ])]}
    assert route_supervisor(state_final) == "finalizer"
    
    # 2. Conduct Research -> Worker
    state_worker = {"messages": [AIMessage(content="Thinking", tool_calls=[
        {"name": "ConductResearch", "args": {"topic": "foo"}, "id": "2"}
    ])]}
    assert route_supervisor(state_worker) == "worker"

    # 3. Resolve Conflict -> Debater
    state_debater = {"messages": [AIMessage(content="Conflict!", tool_calls=[
        {"name": "ResolveConflict", "args": {"topic": "bar"}, "id": "3"}
    ])]}
    assert route_supervisor(state_debater) == "debater"
    
    # 4. No Tool Call -> Finalizer (Fallback)
    state_empty = {"messages": [AIMessage(content="Just chatting")]}
    assert route_supervisor(state_empty) == "finalizer"

def test_enter_worker_adapter():
    """Verify GlobalState -> WorkerState transformation."""
    state: GlobalState = {
        "messages": [AIMessage(content="Go", tool_calls=[
            {"name": "ConductResearch", "args": {"topic": "AI Safety"}, "id": "1"}
        ])],
        "research_notes": [],
        "required_tokens": []
    }
    
    worker_input = enter_worker(state)
    assert worker_input["topic"] == "AI Safety"
    assert worker_input["messages"] == []
    assert worker_input["research_notes"] == ""

def test_exit_worker_adapter():
    """Verify WorkerState -> GlobalState transformation."""
    worker_output: WorkerState = {
        "research_notes": "AI is safe.",
        "topic": "AI Safety",
        "messages": [],
        "timeline": [{"date": "2024-01-01", "title": "t", "description": "d", "source": "s"}],
        "conflict_candidates": [],
        "required_tokens": []
    }
    
    global_update = exit_worker(worker_output)
    assert global_update["research_notes"] == ["AI is safe."]
    assert global_update["timeline"] == worker_output["timeline"]
