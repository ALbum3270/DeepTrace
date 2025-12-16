import sys
sys.path.append('d:/AAA/DeepTrace')
from src.graph.workflow import route_from_supervisor
from src.graph.state import GraphState
from src.core.models.strategy import SearchStrategy

print('Testing...')
for strat in [SearchStrategy.GENERIC, SearchStrategy.WEIBO, SearchStrategy.XHS, SearchStrategy.MIXED, None]:
    state = GraphState(search_strategy=strat) if strat else GraphState()
    try:
        result = route_from_supervisor(state)
        print(strat, '->', result)
    except Exception as e:
        print('Error for', strat, e)
