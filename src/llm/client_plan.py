"""
LLM Client 模块规划
"""
from typing import Optional
from pydantic import BaseModel

class LLMConfig(BaseModel):
    """LLM 配置"""
    api_key: str
    base_url: str
    model_name: str
    temperature: float = 0.0

class LLMClient:
    """
    统一的大模型客户端封装。
    
    职责：
    1. 管理 API Key 和 Base URL 配置
    2. 提供统一的 chat 接口
    3. (未来) 支持结构化输出 (Structured Output) / Function Calling
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        # 如果 config 为空，尝试从环境变量读取
        pass

    async def one_shot(self, prompt: str, system_prompt: str = "") -> str:
        """
        简单的一次性问答。
        """
        pass
        
    async def structured_predict(self, prompt: str, response_model: BaseModel) -> BaseModel:
        """
        要求 LLM 返回符合 Pydantic 模型的数据（用于提取事件节点）。
        使用 LangChain 的 with_structured_output 或底层 API 的 json_object 模式。
        """
        pass
