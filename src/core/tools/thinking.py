"""
Think Tool for DeepTrace.
Captures explicit planning steps before actions.
"""

from pydantic import BaseModel, Field
from langchain_core.tools import tool


class ThinkInput(BaseModel):
    """Input schema for think_tool."""
    reflection: str = Field(description="Your plan or reasoning before taking actions.")


@tool("think_tool", args_schema=ThinkInput)
def think_tool(reflection: str) -> str:
    """
    Return the provided reflection. Used for traceability in logs.
    """
    return f"THINK: {reflection}"
