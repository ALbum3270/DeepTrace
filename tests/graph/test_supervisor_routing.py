import pytest

# Skip entire module: route_from_supervisor was removed in V2 refactor
pytestmark = pytest.mark.skip(reason="route_from_supervisor removed in V2 refactor; tests obsolete")

from src.graph.state import GraphState
from src.core.models.strategy import SearchStrategy
# from src.graph.workflow import route_from_supervisor  # Removed in V2

def route_from_supervisor(state):
    """Stub for legacy tests."""
    return "fetch"

def test_route_generic():
    state = GraphState(search_strategy=SearchStrategy.GENERIC)
    assert route_from_supervisor(state) == "fetch"

def test_route_weibo():
    state = GraphState(search_strategy=SearchStrategy.WEIBO)
    assert route_from_supervisor(state) == "weibo_fetch"

def test_route_xhs():
    state = GraphState(search_strategy=SearchStrategy.XHS)
    assert route_from_supervisor(state) == "xhs_fetch"

def test_route_mixed():
    state = GraphState(search_strategy=SearchStrategy.MIXED)
    assert route_from_supervisor(state) == "mixed_entry"

def test_route_fallback():
    state = GraphState() # No strategy
    assert route_from_supervisor(state) == "fetch"

if __name__ == "__main__":
    try:
        test_route_generic()
        print("test_route_generic passed")
        test_route_weibo()
        print("test_route_weibo passed")
        test_route_xhs()
        print("test_route_xhs passed")
        test_route_mixed()
        print("test_route_mixed passed")
        test_route_fallback()
        print("test_route_fallback passed")
        print("All tests passed!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
