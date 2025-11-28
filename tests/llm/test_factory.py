"""
测试 LLM Factory
"""
import os
from unittest.mock import patch
from importlib import reload

from src.llm.factory import init_llm
from langchain_openai import ChatOpenAI

class TestLLMFactory:
    """测试 LLM 工厂"""

    def test_init_llm_defaults(self):
        """测试默认初始化"""
        # 使用 patch.dict 修改 os.environ
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test-key",
            "OPENAI_BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "gpt-test-model",
        }):
            # 重新加载 settings 以获取新环境变量
            import src.config.settings as settings_mod
            reload(settings_mod)
            # 重新加载 factory 以使用新的 settings 实例
            import src.llm.factory as factory_mod
            reload(factory_mod)

            llm = factory_mod.init_llm()
            assert isinstance(llm, ChatOpenAI)
            assert llm.temperature == 0.0
            assert llm.model_name == "gpt-test-model"
            assert llm.openai_api_key.get_secret_value() == "sk-test-key"

    def test_init_llm_custom_temp(self):
        """测试自定义温度"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            import src.config.settings as settings_mod
            reload(settings_mod)
            import src.llm.factory as factory_mod
            reload(factory_mod)
            llm = factory_mod.init_llm(temperature=0.7)
            assert llm.temperature == 0.7
