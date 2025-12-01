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
        # 在没有 Key 的情况下（比如测试环境），可以抛出警告或返回 Mock
        # 这里为了简单，如果没 Key 可能会报错，但在 CLI 运行时会显式检查
        pass

    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.model_name,
        temperature=temperature,
        request_timeout=timeout,
        # 显式指定 openai_api_key 参数，防止 langchain 自动读取环境变量有时不一致
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
    )
