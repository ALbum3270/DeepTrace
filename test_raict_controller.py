
import pytest
from src.core.models.task import BreadthTask, DepthTask
from src.config.settings import settings
from src.graph.nodes.controller import route_raict

# Mock Settings
settings.MAX_LAYERS = 2
settings.MAX_BREADTH_STEPS_PER_LAYER = 2
settings.MAX_DEPTH_STEPS_PER_LAYER = 2

def test_controller_safety_fuse():
    """Test max layer termination"""
    state = {"current_layer": 2} # >= MAX_LAYERS
    assert route_raict(state) == "reporter"

def test_breadth_priority():
    """Test breadth task priority in current layer"""
    t1 = BreadthTask(layer=0, query="q1")
    state = {
        "current_layer": 0,
        "breadth_pool": [t1],
        "current_layer_breadth_steps": 0
    }
    assert route_raict(state) == "breadth_node"
    
    # Test step limit
    state["current_layer_breadth_steps"] = 2
    # Should fall through to depth or next
    assert route_raict(state) == "reporter" # No depth tasks, no next layer tasks

def test_depth_priority():
    """Test depth task priority after breadth exhausted"""
    t1 = DepthTask(layer=0, claim_id="c1")
    state = {
        "current_layer": 0,
        "breadth_pool": [],
        "depth_pool": [t1],
        "current_layer_depth_steps": 0
    }
    assert route_raict(state) == "depth_node"

def test_layer_promotion():
    """Test promotion to next layer"""
    t_next = BreadthTask(layer=1, query="q2")
    state = {
        "current_layer": 0,
        "breadth_pool": [t_next], 
        "depth_pool": [],
        "current_layer_breadth_steps": 2, # exhausted
        "current_layer_depth_steps": 2    # exhausted
    }
    assert route_raict(state) == "promote_layer"

def test_finish_no_future_tasks():
    """Test finish when current layer done and no future tasks"""
    state = {
        "current_layer": 0,
        "breadth_pool": [], 
        "depth_pool": [],
        "current_layer_breadth_steps": 2,
        "current_layer_depth_steps": 2
    }
    assert route_raict(state) == "reporter"

if __name__ == "__main__":
    # Manually run if not using pytest runner
    try:
        test_controller_safety_fuse()
        test_breadth_priority()
        test_depth_priority()
        test_layer_promotion()
        test_finish_no_future_tasks()
        print("✅ All Controller Tests Passed!")
    except AssertionError as e:
        print(f"❌ Test Failed")
        raise e
