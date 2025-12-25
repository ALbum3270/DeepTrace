"""
Context Compressor Node for DeepTrace V2.
Responsible for squeezing the 'juice' (Facts/Citations) out of the 'pulp' (Raw Search Results).
"""

from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from src.config.settings import settings
from src.graph.state_v2 import WorkerState
from src.core.prompts.v2 import (
    COMPRESS_RESEARCH_SYSTEM_PROMPT,
    COMPRESS_RESEARCH_SIMPLE_HUMAN_MESSAGE,
)
from src.core.utils.llm_safety import safe_ainvoke

# Simple heuristic threshold to avoid unnecessary LLM calls when content is small
COMPRESSION_CHAR_THRESHOLD = 12000

async def compress_node(state: WorkerState, config: RunnableConfig):
    """
    Compresses the worker's message history into a concise note.

    Why: To return high-density information to the Supervisor without polluting
    global context with pages of raw HTML or search logs.
    """
    messages = state["messages"]

    # If there's no real content (e.g. just tool calls without results), skip
    if not messages:
        return {"research_notes": "No research performed."}

    # Consolidate history content
    history_content = "\n---\n".join([m.content for m in messages])

    # If content is below threshold, return as-is to save tokens
    if len(history_content) <= COMPRESSION_CHAR_THRESHOLD:
        return {"research_notes": history_content or "No research performed."}

    # Configuration (Dynamic Model Selection)
    # Default to settings.model_name or gpt-4o
    configurable = config.get("configurable", {})
    model_name = configurable.get("summarization_model", settings.model_name or "gpt-4o")

    # Initialize Model with Retry
    # Robust initialization for Custom Endpoints
    if settings.openai_base_url and "openai.com" not in settings.openai_base_url:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=0
        ).with_retry(stop_after_attempt=3)
    else:
        llm = init_chat_model(model=model_name, temperature=0).with_retry(
            stop_after_attempt=3
        )

    # Prepare Prompt
    date_str = datetime.now().strftime("%Y-%m-%d")
    system_msg = COMPRESS_RESEARCH_SYSTEM_PROMPT.format(date=date_str)

    # Input Messages: System + User (with Content)
    # We consolidate worker history to avoid "System -> AI -> User" role errors
    
    final_user_content = f"""
Here is the raw research data found:
{history_content}

{COMPRESS_RESEARCH_SIMPLE_HUMAN_MESSAGE}
"""
    prompt = [
        SystemMessage(content=system_msg),
        HumanMessage(content=final_user_content),
    ]

    # Execute
    response = await safe_ainvoke(llm, prompt, model_name=model_name)

    # Return as 'research_notes' (which updates the specific key in WorkerState)
    return {"research_notes": response.content}
