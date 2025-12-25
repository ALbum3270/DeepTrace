"""
LLM Safety Utilities for DeepTrace.
Ported from Open Deep Research (ODR) to prevent token overflow crashes.
"""

from typing import List, Optional, Union
from langchain_core.messages import AIMessage, BaseMessage

# Define MessageLike protocol/type alias if not available
MessageLikeRepresentation = Union[BaseMessage, dict]

# Model Token Limits (Snapshot from ODR)
MODEL_TOKEN_LIMITS = {
    "openai:gpt-4o-mini": 128000,
    "openai:gpt-4o": 128000,
    "openai:o4-mini": 200000,
    "openai:o3-mini": 200000,
    "openai:o3": 200000,
    "openai:o3-pro": 200000,
    "openai:o1-pro": 200000,
    "openai:Qwen/Qwen2.5-Coder-32B-Instruct": 32768,
    "anthropic:claude-opus-4": 200000,
    "anthropic:claude-sonnet-4": 200000,
    "anthropic:claude-3-7-sonnet": 200000,
    "anthropic:claude-3-5-sonnet": 200000,
    "anthropic:claude-3-5-haiku": 200000,
    "google:gemini-1.5-pro": 2097152,
    "google:gemini-1.5-flash": 1048576,
    "google:gemini-pro": 32768,
}


def get_model_token_limit(model_string: str) -> Optional[int]:
    """Look up the token limit for a specific model."""
    for model_key, token_limit in MODEL_TOKEN_LIMITS.items():
        if model_key in model_string:
            return token_limit
    return None


def is_token_limit_exceeded(exception: Exception, model_name: str = None) -> bool:
    """Determine if an exception indicates a token/context limit was exceeded."""
    error_str = str(exception).lower()

    # Step 1: Determine provider from model name if available
    provider = None
    if model_name:
        model_str = str(model_name).lower()
        if model_str.startswith("openai:"):
            provider = "openai"
        elif model_str.startswith("anthropic:"):
            provider = "anthropic"
        elif model_str.startswith("gemini:") or model_str.startswith("google:"):
            provider = "gemini"

    # Step 2: Check provider-specific token limit patterns
    if provider == "openai":
        return _check_openai_token_limit(exception, error_str)
    elif provider == "anthropic":
        return _check_anthropic_token_limit(exception, error_str)
    elif provider == "gemini":
        return _check_gemini_token_limit(exception, error_str)

    # Step 3: If provider unknown, check all providers
    return (
        _check_openai_token_limit(exception, error_str)
        or _check_anthropic_token_limit(exception, error_str)
        or _check_gemini_token_limit(exception, error_str)
    )


def _check_openai_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates OpenAI token limit exceeded."""
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, "__module__", "")

    is_openai_exception = (
        "openai" in exception_type.lower() or "openai" in module_name.lower()
    )

    # Check for typical OpenAI token limit error types
    is_request_error = class_name in [
        "BadRequestError",
        "InvalidRequestError",
        "APIError",
    ]

    if is_openai_exception or is_request_error:
        token_keywords = ["token", "context", "length", "maximum context", "reduce"]
        if any(keyword in error_str for keyword in token_keywords):
            return True

    # Check for specific OpenAI error codes
    if hasattr(exception, "code"):
        error_code = getattr(exception, "code", "")
        if error_code == "context_length_exceeded":
            return True
        # Sometimes code is inside 'body' which is a dict
        if hasattr(exception, "body") and isinstance(exception.body, dict):
            if exception.body.get("code") == "context_length_exceeded":
                return True

    return False


def _check_anthropic_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates Anthropic token limit exceeded."""
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, "__module__", "")

    is_anthropic_exception = (
        "anthropic" in exception_type.lower() or "anthropic" in module_name.lower()
    )

    is_bad_request = class_name == "BadRequestError"

    if (is_anthropic_exception and is_bad_request) or "anthropic" in error_str:
        if "prompt is too long" in error_str:
            return True
        if "maximum context length" in error_str:
            return True

    return False


def _check_gemini_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates Google/Gemini token limit exceeded."""
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, "__module__", "")

    is_google_exception = (
        "google" in exception_type.lower() or "google" in module_name.lower()
    )

    is_resource_exhausted = class_name in [
        "ResourceExhausted",
        "GoogleGenerativeAIFetchError",
    ]

    if is_google_exception and is_resource_exhausted:
        return True

    if "resourceexhausted" in exception_type.lower():
        return True
    if "429" in error_str and "resource exhausted" in error_str:
        return True

    return False


def remove_up_to_last_ai_message(
    messages: List[MessageLikeRepresentation],
) -> List[MessageLikeRepresentation]:
    """Truncate message history by removing up to the last AI message."""
    # Search backwards through messages to find the last AI message
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        # Check if it's an AIMessage object or a dict with role='assistant'
        is_ai = isinstance(msg, AIMessage)
        if not is_ai and isinstance(msg, dict):
            is_ai = msg.get("role") == "assistant"

        if is_ai:
            # Return everything up to (but not including) the last AI message
            # effectively dropping the last user query and the last AI response (if any) that caused trouble?
            # ODR logic: returns messages[:i]. So it keeps everything BEFORE the last AI message.
            # This usually means dropping the most recent turn.
            return messages[:i]

    # No AI messages found, return original list (cannot truncate safely)
    return messages


def _drop_oldest_non_system(
    messages: List[MessageLikeRepresentation],
) -> List[MessageLikeRepresentation]:
    """Drop the oldest non-system message as a fallback truncation strategy."""
    for i, msg in enumerate(messages):
        role = None
        if isinstance(msg, BaseMessage):
            role = msg.type
        elif isinstance(msg, dict):
            role = msg.get("role")
        if role != "system":
            return messages[i + 1 :]
    return messages[1:] if len(messages) > 1 else messages


async def safe_ainvoke(
    runnable,
    messages: List[MessageLikeRepresentation],
    model_name: Optional[str] = None,
    max_retries: int = 3,
):
    """
    Invoke an LLM with token-limit retries using recursive truncation.
    """
    if not hasattr(runnable, "ainvoke"):
        raise TypeError("safe_ainvoke expects a runnable with .ainvoke()")

    current_messages = list(messages)
    last_error: Optional[Exception] = None

    for _ in range(max_retries):
        try:
            return await runnable.ainvoke(current_messages)
        except Exception as e:  # pragma: no cover - behavior validated in higher-level tests
            last_error = e
            if not is_token_limit_exceeded(e, model_name):
                raise
            truncated = remove_up_to_last_ai_message(current_messages)
            if truncated == current_messages or not truncated:
                truncated = _drop_oldest_non_system(current_messages)
            if truncated == current_messages or not truncated:
                break
            current_messages = truncated

    if last_error:
        raise last_error
    raise RuntimeError("safe_ainvoke failed without exception.")
