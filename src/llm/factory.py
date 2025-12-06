"""
LLM 工厂模块：提供 LangChain ChatModel 实例。
"""
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from ..config.settings import settings


def init_llm(temperature: float = 0.0, timeout: int = 120) -> BaseChatModel:
    """
    初始化并返回一个配置好的 ChatOpenAI 实例。
    
    Args:
        temperature: 采样温度 (0.0 - 1.0)
        timeout: 请求超时时间 (秒)，默认 120s
        
    Returns:
        BaseChatModel: LangChain 聊天模型实例
    """
    if not settings.openai_api_key:
        pass

    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.model_name,
        temperature=temperature,
        request_timeout=timeout,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
    )


def init_json_llm(temperature: float = 0.0, timeout: int = 120) -> BaseChatModel:
    """
    初始化并返回一个启用 JSON Mode 的 ChatOpenAI 实例。
    适用于 Qwen/DashScope API，确保输出是合法 JSON。
    
    注意：使用此 LLM 时，prompt 中必须包含 "json" 关键词和 JSON 示例。
    
    Args:
        temperature: 采样温度 (0.0 - 1.0)
        timeout: 请求超时时间 (秒)，默认 120s
        
    Returns:
        BaseChatModel: LangChain 聊天模型实例（启用 JSON Mode）
    """
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.model_name,
        temperature=temperature,
        request_timeout=timeout,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

