"""
Debater Tool for DeepTrace V2.
Resolves conflicts in research findings using an LLM Judge.
"""

from typing import List
try:
    from langchain.chat_models import init_chat_model  # type: ignore
except ImportError:
    from langchain_openai import ChatOpenAI  # type: ignore
    from src.config.settings import settings
    def init_chat_model(model: str, temperature=0, model_provider=None, **kwargs):
        return ChatOpenAI(
            model=model,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=temperature,
        )
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from src.config.settings import settings
from src.core.models_v2 import ResolveConflict
from src.core.prompts.v2 import (
    DEBATER_SYSTEM_PROMPT,
    DEBATER_AGENT_PROMPT,
    DEBATER_AGGREGATOR_PROMPT,
    DEBATER_AGGREGATOR_SYSTEM_PROMPT,
    DEBATER_ROLE_SYSTEM_PROMPT,
)
from src.core.utils.llm_safety import safe_ainvoke

# Default Model for Debater (Needs high reasoning capability)
DEFAULT_DEBATER_MODEL = settings.model_name or "gpt-4o"

def _extract_consensus_marker(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    if "answer:" in lowered:
        try:
            answer_part = lowered.split("answer:", 1)[1]
            answer = answer_part.split(".", 1)[0].strip()
            if answer:
                return answer
        except Exception:
            pass
    winner_tokens = [
        ("claim 1", ["claim 1", "claim one", "claim a"]),
        ("claim 2", ["claim 2", "claim two", "claim b"]),
        ("claim 3", ["claim 3", "claim three", "claim c"]),
    ]
    for label, tokens in winner_tokens:
        if any(tok in lowered for tok in tokens) and any(
            key in lowered for key in ["true", "wins", "most likely", "more likely", "correct"]
        ):
            return label
    return ""


@tool("ResolveConflict", args_schema=ResolveConflict)
async def debater_tool(
    topic: str,
    claims: List[str],
    source_ids: List[str],
    config: RunnableConfig = None
) -> str:
    """
    Adjudicates a conflict between two or more claims.
    Returns a verdict explaining which claim is most likely true based on source credibility and recency.
    """
    
    # 1. Config
    configurable = config.get("configurable", {}) if config else {}
    model_name = configurable.get("debater_model", DEFAULT_DEBATER_MODEL)
    
    # 2. Prepare Context
    claims_text = "\n".join([f"- Claim {i+1}: {claim} (Source: {source_ids[i] if i < len(source_ids) else 'Unknown'})" 
                             for i, claim in enumerate(claims)])
    
    user_msg = f"""
Topic: {topic}

Conflicting Claims:
{claims_text}

Please analyze and provide a verdict.
"""

    # 3. Call LLM
    if settings.openai_base_url and "openai.com" not in settings.openai_base_url:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=0
        )
    else:
        llm = init_chat_model(model=model_name, model_provider="openai")

    # 4. Iterative Debate (Scientist <-> Philosopher loop)
    debate_rounds = configurable.get("debate_rounds", 2)
    debate_history: List[str] = []
    roles = ["Scientist", "Philosopher"]

    for _ in range(debate_rounds):
        round_markers = []
        for role_name in roles:
            history_block = ""
            if debate_history:
                history_block = (
                    "The following reponses are from other agents as additional information.\n"
                    + "\n".join(debate_history)
                    + "\n"
                )
            role_prompt = DEBATER_AGENT_PROMPT.format(
                query=topic,
                document=claims_text,
                history_block=history_block,
            )
            role_messages = [
                SystemMessage(content=DEBATER_ROLE_SYSTEM_PROMPT.format(role=role_name)),
                HumanMessage(content=role_prompt),
            ]
            try:
                role_response = await safe_ainvoke(llm, role_messages, model_name=model_name)
                content = role_response.content.strip()
                debate_history.append(f"{role_name}: {content}")
                round_markers.append(_extract_consensus_marker(content))
            except Exception as e:
                debate_history.append(f"{role_name}: Debate step failed: {str(e)}")
                round_markers.append("")
        if len(round_markers) == len(roles):
            non_empty = [m for m in round_markers if m]
            if non_empty and len(set(non_empty)) == 1:
                break

    joined = "\n".join(debate_history)
    judge_prompt = DEBATER_AGGREGATOR_PROMPT.format(query=topic, responses=joined)
    judge_messages = [
        SystemMessage(content=DEBATER_AGGREGATOR_SYSTEM_PROMPT),
        HumanMessage(content=judge_prompt),
    ]

    try:
        response = await safe_ainvoke(llm, judge_messages, model_name=model_name)
        return response.content
    except Exception as e:
        return f"Debate failed: {str(e)}"
