import sys
sys.path.append('d:/AAA/DeepTrace')
from src.graph.workflow import route_from_supervisor
from src.graph.state import GraphState
from src.core.models.strategy import SearchStrategy
print('import ok')
state = GraphState(search_strategy=SearchStrategy.GENERIC)
print('result:', route_from_supervisor(state))
