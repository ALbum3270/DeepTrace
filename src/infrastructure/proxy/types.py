from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ProviderNameEnum(Enum):
    KUAI_DAILI_PROVIDER: str = "kuaidaili"
    WANDOU_HTTP_PROVIDER: str = "wandouhttp"

class IpInfoModel(BaseModel):
    """Unified IP model"""
    ip: str = Field(title="ip")
    port: int = Field(title="端口")
    user: str = Field(title="IP代理认证的用户名")
    protocol: str = Field(default="https://", title="代理IP的协议")
    password: str = Field(title="IP代理认证用户的密码")
    expired_time_ts: Optional[int] = Field(title="IP 过期时间")
