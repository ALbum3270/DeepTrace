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
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
    
    # 项目配置
    PROJECT_NAME = "DeepTrace"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

settings = Settings()
