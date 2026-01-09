"""
Clarification Node for DeepTrace V2.
Checks the initial query and refines it when ambiguous.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
try:
    from langchain.chat_models import init_chat_model  # type: ignore
except ImportError:
    from langchain_openai import ChatOpenAI  # type: ignore
    def init_chat_model(model: str, temperature=0, model_provider=None, **kwargs):
        from src.config.settings import settings
        return ChatOpenAI(
            model=model,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=temperature,
        )

from src.config.settings import settings
from src.graph.state_v2 import GlobalState
from src.core.prompts.v2 import CLARIFY_SYSTEM_PROMPT
from src.core.models.v2_structures import ClarificationResult
from src.core.utils.llm_safety import safe_ainvoke
from src.core.utils.topic_filter import extract_tokens


async def _get_clarification_result(query: str, config: RunnableConfig) -> ClarificationResult:
    configurable = config.get("configurable", {}) if config else {}
    model_name = configurable.get("clarify_model", settings.model_name or "gpt-4o")

    if settings.openai_base_url and "openai.com" not in settings.openai_base_url:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=0,
        )
    else:
        llm = init_chat_model(model=model_name, temperature=0)

    parser = PydanticOutputParser(pydantic_object=ClarificationResult)
    prompt = [
        SystemMessage(content=CLARIFY_SYSTEM_PROMPT + "\n\n" + parser.get_format_instructions()),
        HumanMessage(content=f"User Query: {query}"),
    ]

    response = await safe_ainvoke(llm, prompt, model_name=model_name)
    return parser.parse(response.content)


async def interactive_clarify(query: str, config: RunnableConfig) -> tuple[str, list[str], list[str]]:
    """
    Show research direction options to user. Default uses original query.
    Returns (clarified_objective, required_tokens, log_entries).
    """
    import sys
    
    if not query:
        return query, extract_tokens(query), []

    log_entries: list[str] = []
    
    try:
        result = await _get_clarification_result(query, config)
    except Exception as e:
        log_entries.append(f"Clarification skipped: {e}")
        return query, extract_tokens(query), log_entries

    # Show research directions if available
    if result.research_directions:
        print("\n" + "="*60)
        print(f"📝 您的查询: {query}")
        print("="*60)
        print("\n🔍 可选研究方向:")
        for idx, direction in enumerate(result.research_directions[:3]):
            label = chr(ord('A') + idx)  # A, B, C
            print(f"   [{label}] {direction}")
        print(f"\n   [Enter] 使用原始查询: {query}")
        print("="*60)
        
        log_entries.append(f"Research directions offered: {'; '.join(result.research_directions[:3])}")
        
        # Get user choice
        user_input = ""
        if sys.stdin and sys.stdin.isatty():
            user_input = input("\n请选择 [A/B/C] 或直接回车: ").strip().upper()
        
        # Determine final objective
        if user_input in ['A', 'B', 'C']:
            idx = ord(user_input) - ord('A')
            if idx < len(result.research_directions):
                clarified_objective = result.research_directions[idx]
                log_entries.append(f"User selected option {user_input}")
            else:
                clarified_objective = query
        else:
            # Default: use original query
            clarified_objective = query
            log_entries.append("User chose original query (default)")
    else:
        clarified_objective = query

    required_tokens = extract_tokens(clarified_objective)
    if not required_tokens:
        required_tokens = extract_tokens(query)
    
    return clarified_objective, required_tokens, log_entries


async def _check_intent_drift(original: str, proposal: str, model_name: str = None) -> bool:
    """
    Lightweight guardrail: return True if proposal drifts away from the original intent.
    Uses a small model to semantically compare subject/version changes.
    """
    if not proposal or proposal.strip().lower() == original.strip().lower():
        return False

    model = model_name or "gpt-4o-mini"
    prompt = f"""
Compare these two queries:
1) User Query: "{original}"
2) Optimized Query: "{proposal}"
Does the Optimized Query change the specific subject or product version of the User Query?
Answer only YES or NO.
"""
    llm = init_chat_model(model=model, temperature=0)
    resp = await safe_ainvoke(llm, [HumanMessage(content=prompt)], model_name=model)
    return "yes" in resp.content.lower()


async def clarify_node(state: GlobalState, config: RunnableConfig):
    """
    Refine the user query and emit a confirmation message into the log.
    """
    if state.get("clarification_done"):
        # Already clarified (e.g., by interactive_clarify); preserve existing tokens
        return {
            "clarification_done": True,
            "required_tokens": state.get("required_tokens") or [],
        }

    query = state.get("original_query") or state.get("objective") or ""
    if not query:
        return {"clarification_done": True}

    try:
        configurable = config.get("configurable", {})
        guard_model = configurable.get("guard_model", "gpt-4o-mini")
        result = await _get_clarification_result(query, config)

        # Hard guardrail: keep original objective unless (a) no clarification is requested AND
        # (b) clarified text preserves key tokens. Otherwise, require user confirmation.
        clarified_objective = query
        log_entries = []
        required_tokens = extract_tokens(query)

        if result.needs_clarification and result.questions:
            log_entries.append(
                "Clarification requires user confirmation; objective kept unchanged. Questions: "
                + "; ".join(result.questions)
            )
        elif result.needs_clarification:
            log_entries.append("Clarification requires user confirmation; objective kept unchanged.")

        if result.confirmation_message:
            log_entries.append(result.confirmation_message)

        lower_original = query.lower()
        proposal = (result.clarified_objective or query).lower()

        orig_key_hits = set(required_tokens)
        proposal_key_hits = set(extract_tokens(proposal))

        if result.needs_clarification:
            log_entries.append("Clarification pending user input; objective kept unchanged.")
        else:
            candidate = result.clarified_objective or query
            drift = False
            try:
                drift = await _check_intent_drift(query, candidate, model_name=guard_model)
            except Exception:
                drift = False  # fallback to existing guards

            missing_tokens = [t for t in required_tokens if t not in candidate.lower()]

            if not required_tokens:
                # Strict: no tokens detected, do not allow any modification.
                log_entries.append("No topic tokens detected; objective kept unchanged to avoid drift.")
            elif orig_key_hits:
                # Accept only if every original key token is preserved AND no new conflicting key is introduced.
                preserves_all = orig_key_hits.issubset(proposal_key_hits)
                introduces_new = bool(proposal_key_hits - orig_key_hits)
                if preserves_all and not introduces_new and not drift and not missing_tokens:
                    clarified_objective = candidate
                    required_tokens = list(orig_key_hits)
                else:
                    log_entries.append(
                        "Clarification rejected to prevent topic drift away from the original model target."
                    )
            else:
                # No orig tokens but required_tokens exists (from fallback): keep original to avoid drift.
                log_entries.append("Clarification rejected to prevent topic drift away from the original model target.")

        return {
            "objective": clarified_objective,
            "research_brief": f"Research goal: {clarified_objective}",
            "investigation_log": log_entries,
            "required_tokens": required_tokens,
        }
    except Exception:
        return {
            "objective": query,
            "research_brief": f"Research goal: {query}",
            "investigation_log": ["Clarification skipped due to parse failure."],
            "required_tokens": extract_tokens(query),
        }
