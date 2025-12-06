import logging
from typing import Literal, Dict, Any

from ...config.settings import settings
from ...graph.state import GraphState

logger = logging.getLogger(__name__)

def route_raict(state: GraphState) -> Literal["breadth_node", "depth_node", "promote_layer", "reporter"]:
    """
    RAICT Lite Controller Router
    决定下一步行动：
    1. 本层广度优先
    2. 本层深度其次
    3. 进入下一层
    4. 结束 -> 报告
    """
    current_layer = state.get("current_layer", 0)
    
    # 0. Safety Fuse
    if current_layer >= settings.MAX_LAYERS:
        logger.info(f"Hit Max Layers ({settings.MAX_LAYERS}), going to Reporter.")
        return "reporter"
        
    breadth_pool = state.get("breadth_pool", [])
    depth_pool = state.get("depth_pool", [])
    
    # Filter tasks for current layer (or all future tasks? usually per layer)
    # The pools usually accumulate. We need to check tasks belonging to current layer.
    current_breadth = [t for t in breadth_pool if t.layer == current_layer]
    current_depth = [t for t in depth_pool if t.layer == current_layer]
    
    # 1. Breadth Priority
    breadth_steps = state.get("current_layer_breadth_steps", 0)
    if current_breadth and breadth_steps < settings.MAX_BREADTH_STEPS_PER_LAYER:
        logger.info(f"Layer {current_layer}: Routing to Breadth ({breadth_steps}/{settings.MAX_BREADTH_STEPS_PER_LAYER})")
        return "breadth_node"
        
    # 2. Depth Priority
    depth_steps = state.get("current_layer_depth_steps", 0)
    if current_depth and depth_steps < settings.MAX_DEPTH_STEPS_PER_LAYER:
        logger.info(f"Layer {current_layer}: Routing to Depth ({depth_steps}/{settings.MAX_DEPTH_STEPS_PER_LAYER})")
        return "depth_node"
        
    # 3. Check Next Layer
    future_breadth = [t for t in breadth_pool if t.layer > current_layer]
    future_depth = [t for t in depth_pool if t.layer > current_layer]
    
    if future_breadth or future_depth:
        if current_layer + 1 < settings.MAX_LAYERS:
            logger.info(f"Layer {current_layer} exhausted. Promoting to Layer {current_layer + 1}.")
            return "promote_layer"
            
    # 4. Finish
    logger.info("No more tasks or layers execution exhausted. Going to Reporter.")
    return "reporter"


def promote_layer_node(state: GraphState) -> Dict[str, Any]:
    """
    晋升层级节点：
    - Layer + 1
    - 重置步数计数器
    """
    new_layer = state.get("current_layer", 0) + 1
    logger.info(f"Promoting to Layer {new_layer}")
    
    return {
        "current_layer": new_layer,
        "current_layer_breadth_steps": 0,
        "current_layer_depth_steps": 0
    }
