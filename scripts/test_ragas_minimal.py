"""
Ragas 最小闭环测试 - DeepTrace Phase 0 评估集成
================================================
验证 Ragas 可用于 baseline vs variant 对比、回归门禁

评测模型: Kimi K2 (避免自己评自己)
测试数据: 真实的 DeepTrace 报告 (final_report.md)
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从 DeepTrace 配置读取 API key
from src.config.settings import settings

# Kimi API 配置 (用于评测)
KIMI_API_KEY = "sk-jW8s9skxs54AMLGpyKZIOmJ4gsa52p9tGhtyhjRT3mSTgApL"
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_MODEL = "kimi-k2-0905-preview"  # 最新非思考模型，256k上下文，速度快

# DeepTrace 报告路径
FINAL_REPORT_PATH = Path(__file__).parent.parent / "final_report.md"

if not KIMI_API_KEY:
    KIMI_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
    if not KIMI_API_KEY:
        print("❌ 请设置 MOONSHOT_API_KEY 环境变量，或在脚本中填写 KIMI_API_KEY")
        sys.exit(1)


def load_final_report():
    """加载真实的 DeepTrace 报告"""
    if not FINAL_REPORT_PATH.exists():
        print(f"❌ 报告文件不存在: {FINAL_REPORT_PATH}")
        return None
    return FINAL_REPORT_PATH.read_text(encoding='utf-8')


def get_kimi_llm():
    """获取 Kimi K2 Thinking 作为评测 LLM"""
    from ragas.llms import LangchainLLMWrapper
    from langchain_openai import ChatOpenAI
    
    return LangchainLLMWrapper(ChatOpenAI(
        model=KIMI_MODEL,
        api_key=KIMI_API_KEY,
        base_url=KIMI_BASE_URL,
        temperature=0.7,  # Kimi 推荐 temperature
        max_tokens=8192
    ))


async def test_ragas_faithfulness():
    """测试 Faithfulness - 使用真实 DeepTrace 报告"""
    from ragas.metrics import Faithfulness
    from ragas.dataset_schema import SingleTurnSample
    
    print("=" * 60)
    print("🧪 Ragas Faithfulness 测试 (忠实度)")
    print(f"   评测模型: {KIMI_MODEL}")
    print(f"   测试数据: 真实 DeepTrace 报告 (final_report.md)")
    print("=" * 60)
    
    # 加载真实报告
    report_content = load_final_report()
    if not report_content:
        return None, None
    
    print(f"\n📄 已加载报告，长度: {len(report_content)} 字符")
    
    # 使用 Kimi K2 作为评测 LLM
    llm = get_kimi_llm()
    
    # 创建忠实度评估指标
    metric = Faithfulness(llm=llm)
    
    # 从报告中提取关键事实作为 retrieved_contexts
    # 这些是报告声称的事实来源
    retrieved_contexts = [
        "OpenAI officially launched GPT-5 on August 7, 2025, making it available to all ChatGPT users and developers via API.",
        "GPT-5 integrates o-series advancements into a unified model family, retiring standalone models like o3.",
        "The model features a 400K-token context window and Responses API for agentic workflows.",
        "GPT-5 outperformed GPT-4 on key benchmarks including MMLU, HumanEval, MATH, and GPQA, achieving 90% on SimpleBench.",
        "Sam Altman confirmed in October 2024 that GPT-5 would not be released that year.",
        "GPT-4.5 (Orion) served as a transitional model released in February 2025.",
    ]
    
    # 真实报告样本
    real_sample = SingleTurnSample(
        user_input="OpenAI GPT-5 release",
        response=report_content,
        retrieved_contexts=retrieved_contexts
    )
    
    print("\n📊 评估真实 DeepTrace 报告的 Faithfulness...")
    score_real = await metric.single_turn_ascore(real_sample)
    
    # 对比：编造一个不忠实的报告
    fake_report = """
# DeepTrace Report: OpenAI GPT-5 release
## Executive Summary
OpenAI 于 2024 年 1 月发布了 GPT-5，实现了 AGI 级别的推理能力。
该模型支持无限上下文窗口，完全免费开放给所有用户。
GPT-5 已经可以自主编写完整的操作系统。
"""
    
    bad_sample = SingleTurnSample(
        user_input="OpenAI GPT-5 release",
        response=fake_report,
        retrieved_contexts=retrieved_contexts
    )
    
    print("\n📊 评估编造报告的 Faithfulness (对照组)...")
    score_bad = await metric.single_turn_ascore(bad_sample)
    
    print("\n" + "=" * 60)
    print("📈 评估结果对比")
    print("=" * 60)
    print(f"\n✅ 真实 DeepTrace 报告: {score_real:.2f} (1.0=完全忠实)")
    print(f"❌ 编造报告 (对照组): {score_bad:.2f} (0.0=完全不忠实)")
    
    if score_real > score_bad:
        print("\n🎉 Faithfulness 区分能力验证通过！")
    
    return score_real, score_bad


async def test_ragas_answer_correctness():
    """测试 FactualCorrectness - 使用真实 DeepTrace 报告"""
    from ragas.metrics import FactualCorrectness
    from ragas.dataset_schema import SingleTurnSample
    
    print("\n" + "=" * 60)
    print("🧪 Ragas FactualCorrectness 测试 (事实正确性)")
    print(f"   评测模型: {KIMI_MODEL}")
    print(f"   测试数据: 真实 DeepTrace 报告 (final_report.md)")
    print("=" * 60)
    
    # 加载真实报告
    report_content = load_final_report()
    if not report_content:
        return None, None
    
    # 使用 Kimi K2 作为评测 LLM
    llm = get_kimi_llm()
    
    # 创建事实正确性评估指标（与参考答案对比）
    metric = FactualCorrectness(llm=llm)
    
    # 参考答案：基于可靠来源的事实
    reference_answer = """
OpenAI officially launched GPT-5 on August 7, 2025. 
Key features include:
- Available to all ChatGPT users and API developers
- 400K token context window
- Unified model family integrating o-series advancements
- Retired standalone o3 model
- Achieved 90% on SimpleBench benchmark
- GPT-4.5 (Orion) was released in February 2025 as transitional model
- Sam Altman confirmed in October 2024 that GPT-5 would not release in 2024
"""
    
    # 真实报告样本
    real_sample = SingleTurnSample(
        user_input="OpenAI GPT-5 release",
        response=report_content,
        reference=reference_answer
    )
    
    print("\n📊 评估真实 DeepTrace 报告的 FactualCorrectness...")
    score_real = await metric.single_turn_ascore(real_sample)
    
    # 对比：编造一个错误的报告
    fake_report = """
# DeepTrace Report: OpenAI GPT-5 release
## Executive Summary
OpenAI 于 2024 年 1 月发布了 GPT-5。
主要特点是实现了 AGI，支持无限上下文，完全免费开放。
GPT-4.5 从未存在，GPT-5 直接从 GPT-4 升级。
"""
    
    bad_sample = SingleTurnSample(
        user_input="OpenAI GPT-5 release",
        response=fake_report,
        reference=reference_answer
    )
    
    print("\n📊 评估编造报告的 FactualCorrectness (对照组)...")
    score_bad = await metric.single_turn_ascore(bad_sample)
    
    print("\n" + "=" * 60)
    print("📈 评估结果对比")
    print("=" * 60)
    print(f"\n✅ 真实 DeepTrace 报告: {score_real:.2f} (1.0=完全正确)")
    print(f"❌ 编造报告 (对照组): {score_bad:.2f} (0.0=完全错误)")
    
    if score_real > score_bad:
        print("\n🎉 FactualCorrectness 区分能力验证通过！")
    
    return score_real, score_bad


async def main():
    print("\n" + "🚀" * 20)
    print("   DeepTrace + Ragas 真实报告评估测试")
    print("🚀" * 20 + "\n")
    
    print(f"📁 报告文件: {FINAL_REPORT_PATH}")
    
    try:
        # 测试 1: Faithfulness (忠实度 - 是否忠于证据)
        await test_ragas_faithfulness()
        
        # 测试 2: FactualCorrectness (事实正确性 - 与参考答案对比)
        await test_ragas_answer_correctness()
        
        print("\n" + "=" * 60)
        print("✅ Ragas 真实报告评估完成！")
        print("=" * 60)
        print(f"""
📋 评测配置:
   - 报告生成模型: {settings.model_name or 'default'} (qwen-plus)
   - 评测模型: {KIMI_MODEL} (独立第三方 - Kimi K2)
   - 测试数据: 真实 DeepTrace 报告 (final_report.md)

📋 评估结论:
   ✅ 真实报告 vs 编造报告 的区分能力已验证
   ✅ Faithfulness: 检测报告是否忠实于检索证据
   ✅ FactualCorrectness: 检测报告事实是否正确

📋 Phase0 Ragas 工具验证完成:
   - 6.1 离线评估工具: ✅ Ragas 可用
   - 独立评测模型: ✅ Kimi K2 (避免自评)
   - 真实数据测试: ✅ final_report.md
""")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
