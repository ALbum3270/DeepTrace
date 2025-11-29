from enum import Enum

class SearchStrategy(str, Enum):
    """
    检索策略枚举，用于控制图的路由分支。
    """
    GENERIC = "GENERIC"  # 通用搜索 (SerpAPI)
    WEIBO = "WEIBO"      # 微博专项
    XHS = "XHS"          # 小红书专项
    MIXED = "MIXED"      # 混合/并行模式
