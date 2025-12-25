"""
Helper for emitting think_tool plans before actions.
"""

import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from src.core.tools.thinking import think_tool
from src.core.utils.llm_safety import safe_ainvoke

logger = logging.getLogger(__name__)


async def emit_think_plan(
    llm,
    model_name: Optional[str],
    task: str,
    context: Optional[str] = None,
) -> Optional[str]:
    """
    Ask the model to call think_tool with a short plan, then log the result.
    """
    if not hasattr(llm, "bind_tools"):
        return None

    system_prompt = (
        "You are planning your next action. Call think_tool with a concise plan."
    )
    user_prompt = f"Task: {task}"
    if context:
        user_prompt += f"\nContext: {context}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    planner = llm.bind_tools([think_tool])
    response = await safe_ainvoke(planner, messages, model_name=model_name)

    reflection = None
    if hasattr(response, "tool_calls") and response.tool_calls:
        reflection = response.tool_calls[0].get("args", {}).get("reflection")
    elif getattr(response, "content", None):
        reflection = response.content.strip()

    if not reflection:
        return None

    try:
        result = await think_tool.ainvoke({"reflection": reflection})
    except Exception:
        result = f"THINK: {reflection}"

    logger.info(result)
    return result
