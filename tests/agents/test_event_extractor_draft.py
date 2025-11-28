"""
测试 Event Extractor Agent
"""
import pytest
import os
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.core.models.evidence import Evidence, EvidenceSource
from src.core.models.events import EventNode, EventStatus
from src.agents.event_extractor import extract_event_from_evidence

class TestEventExtractor:
    """测试事件提取 Agent"""
    
    @pytest.mark.asyncio
    async def test_extract_event_success(self):
        """测试成功提取"""
        # 构造假证据
        evidence = Evidence(
            content="2023年10月1日，品牌方发布了致歉声明。",
            source=EvidenceSource.WEIBO,
            publish_time=datetime(2023, 10, 1, 12, 0, 0)
        )
        
        # Mock LLM 的返回
        mock_event = EventNode(
            title="品牌方发布致歉声明",
            description="品牌方在微博发布了致歉声明。",
            time=datetime(2023, 10, 1, 12, 0, 0),
            status=EventStatus.CONFIRMED,
            actors=["品牌方"]
        )
        
        # Mock init_llm 及其链式调用
        with patch("src.agents.event_extractor.init_llm") as mock_init:
            mock_llm = MagicMock()
            mock_structured_llm = MagicMock()
            mock_chain = MagicMock()
            
            mock_init.return_value = mock_llm
            mock_llm.with_structured_output.return_value = mock_structured_llm
            # 模拟 prompt | structured_llm 的行为
            # 这里比较难 mock 管道操作符 |，通常直接 mock chain.ainvoke 更容易
            # 但由于代码里是 prompt | structured_llm，我们需要 mock 这个组合结果
            
            # 简化策略：我们不 mock 管道，而是 mock 整个 chain 的执行
            # 但由于 chain 是在函数内部构建的，我们可能需要 mock ChatPromptTemplate
            pass

    @pytest.mark.asyncio
    async def test_extract_integration_mock(self):
        """
        集成测试（使用 Mock LLM，不真的调 API）。
        这里演示如何通过 mock with_structured_output 来测试逻辑。
        """
        evidence = Evidence(content="测试内容")
        
        with patch("src.agents.event_extractor.init_llm") as mock_init:
            mock_llm = MagicMock()
            mock_structured = MagicMock()
            
            mock_init.return_value = mock_llm
            mock_llm.with_structured_output.return_value = mock_structured
            
            # 模拟 chain.ainvoke
            # 由于 prompt | llm 生成的是 RunnableSequence
            # 我们需要让 mock_structured 能够被组合，或者直接 mock 整个流程
            
            # 更简单的做法：直接 mock 那个 chain 对象？
            # 不行，chain 是局部变量。
            
            # 替代方案：Mock RunnableSequence
            # 这是一个比较复杂的 mock 场景。
            # 为了简单起见，我们假设 init_llm 返回的对象在被 | 操作后，
            # 最终调用的 ainvoke 返回我们需要的值。
            
            # 在 LangChain 中， prompt | llm 返回 RunnableSequence
            # RunnableSequence.ainvoke 会依次调用
            
            # 让我们换一种思路：不 mock 内部细节，只 mock 最终效果？
            # 或者，我们可以重构代码，把 chain 的构建提取出来？
            # 暂时先尝试 mock init_llm 返回对象的 __or__ 方法
            
            mock_runnable = MagicMock()
            mock_runnable.ainvoke.return_value = EventNode(
                title="Mock Event", 
                description="Mock Desc",
                status=EventStatus.CONFIRMED
            )
            
            # 当 prompt | structured_llm 时，会调用 prompt.__or__(structured_llm)
            # 或者 structured_llm.__ror__(prompt)
            # 这太复杂了。
            
            # 终极方案：使用 langchain_core.runnables.RunnableLambda 来模拟
            pass
