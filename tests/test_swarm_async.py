"""
Swarm Async 回归测试
测试所有 Swarm agent 的异步化功能
"""

import inspect


class TestDirectorAsync:
    """DirectorAgent 异步化测试"""

    def test_create_outline_is_coroutine_function(self):
        """测试 create_outline 是协程函数"""
        from src.agents.swarm.director import DirectorAgent

        director = DirectorAgent()

        # 应该是协程函数
        assert inspect.iscoroutinefunction(director.create_outline)


class TestWriterAsync:
    """WriterAgent 异步化测试"""

    def test_write_section_is_coroutine_function(self):
        """测试 write_section 是协程函数"""
        from src.agents.swarm.writer import WriterAgent

        writer = WriterAgent()

        # 应该是协程函数
        assert inspect.iscoroutinefunction(writer.write_section)


class TestCriticAsync:
    """CriticAgent 异步化测试"""

    def test_verify_section_is_coroutine_function(self):
        """测试 verify_section 是协程函数"""
        from src.agents.swarm.critic import CriticAgent

        critic = CriticAgent()

        # 应该是协程函数
        assert inspect.iscoroutinefunction(critic.verify_section)


class TestAuditorAsync:
    """ConsistencyAuditor 异步化测试"""

    def test_check_consistency_is_coroutine_function(self):
        """测试 check_consistency 是协程函数"""
        from src.agents.swarm.auditor import ConsistencyAuditor

        auditor = ConsistencyAuditor()

        # 应该是协程函数
        assert inspect.iscoroutinefunction(auditor.check_consistency)


class TestSwarmNodesAsync:
    """Swarm graph 节点异步化测试"""

    def test_director_node_is_coroutine_function(self):
        """测试 director_node 是协程函数"""
        from src.agents.swarm.graph import director_node

        # 应该是协程函数
        assert inspect.iscoroutinefunction(director_node)

    def test_writer_node_is_coroutine_function(self):
        """测试 writer_node 是协程函数"""
        from src.agents.swarm.graph import writer_node

        # 应该是协程函数
        assert inspect.iscoroutinefunction(writer_node)

    def test_critic_node_is_coroutine_function(self):
        """测试 critic_node 是协程函数"""
        from src.agents.swarm.graph import critic_node

        # 应该是协程函数
        assert inspect.iscoroutinefunction(critic_node)

    def test_auditor_node_is_coroutine_function(self):
        """测试 auditor_node 是协程函数"""
        from src.agents.swarm.graph import auditor_node

        # 应该是协程函数
        assert inspect.iscoroutinefunction(auditor_node)


class TestSwarmAsyncIntegration:
    """集成测试：确保所有组件协同工作"""

    def test_all_swarm_components_are_async(self):
        """验证所有 Swarm 组件都已异步化"""
        from src.agents.swarm.director import DirectorAgent
        from src.agents.swarm.writer import WriterAgent
        from src.agents.swarm.critic import CriticAgent
        from src.agents.swarm.auditor import ConsistencyAuditor

        director = DirectorAgent()
        writer = WriterAgent()
        critic = CriticAgent()
        auditor = ConsistencyAuditor()

        # 所有关键方法都应该是异步的
        assert inspect.iscoroutinefunction(director.create_outline)
        assert inspect.iscoroutinefunction(writer.write_section)
        assert inspect.iscoroutinefunction(critic.verify_section)
        assert inspect.iscoroutinefunction(auditor.check_consistency)

    def test_swarm_graph_nodes_are_async(self):
        """验证所有 graph 节点都已异步化"""
        from src.agents.swarm import graph

        # 所有节点函数都应该是异步的
        assert inspect.iscoroutinefunction(graph.director_node)
        assert inspect.iscoroutinefunction(graph.writer_node)
        assert inspect.iscoroutinefunction(graph.critic_node)
        assert inspect.iscoroutinefunction(graph.auditor_node)
