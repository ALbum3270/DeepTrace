"""
配置管理模块。
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Settings:
    """全局配置类"""
    
    # LLM 配置
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o")
    
    # 项目配置
    project_name = "DeepTrace"
    debug = os.getenv("DEBUG", "False").lower() == "true"

settings = Settings()
