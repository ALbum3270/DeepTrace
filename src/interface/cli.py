import argparse
import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..graph.workflow import create_graph
from ..core.storage import StorageManager
from ..core.models.timeline import Timeline
from ..core.models.evidence import Evidence
from ..core.models.comments import CommentScore
from ..core.models.strategy import SearchStrategy
from ..agents.report_writer import write_narrative_report

def _render_report(
    topic: str,
    timeline: Timeline,
    evidences: List[Evidence],
    comment_scores: List[CommentScore],
    stats: Dict[str, Any]
) -> str:
    """生成 Markdown 格式的最终报告"""
    
    # 1. 标题与元数据
    report = f"# DeepTrace 调查报告：{topic}\n\n"
    report += f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"- **证据数量**: {stats['evidence_count']}\n"
    report += f"- **事件数量**: {stats['event_count']}\n"
    report += f"- **检索轮次**: {stats['loops']}\n\n"
    
    # 2. 时间线
    report += "## 📅 事件时间线\n\n"
    if timeline and timeline.events:
        for event in timeline.events:
            time_str = event.time.strftime('%Y-%m-%d %H:%M') if event.time else "时间未知"
            report += f"### {time_str} - {event.title}\n"
            if event.source:
                report += f"- **来源**: {event.source}\n"
            report += f"- **摘要**: {event.description}\n"
            report += f"- **置信度**: {event.confidence:.2f} ({event.status.value})\n"
            if event.evidence_ids:
                report += "- **支持证据**:\n"
                # 简单查找证据来源
                related_evs = [e for e in evidences if e.id in event.evidence_ids]
                for rev in related_evs:
                    source_name = rev.source.value if hasattr(rev.source, 'value') else str(rev.source)
                    # 优先显示 URL 链接，如果没有 URL 则显示简短摘要
                    if rev.url:
                        # Markdown 链接格式：[来源](URL)
                        report += f"  - [{source_name}]({rev.url})\n"
                    else:
                        # 降级：显示内容摘要
                        content_preview = rev.content[:50] + "..." if len(rev.content) > 50 else rev.content
                        report += f"  - [{source_name}] {content_preview}\n"
            report += "\n"
    else:
        report += "（未生成有效时间线）\n\n"
        
    # 3. 关键评论
    if comment_scores:
        report += "## 💬 关键舆情线索\n\n"
        top_scores = sorted(comment_scores, key=lambda x: x.total_score, reverse=True)[:5]
        
        # 构建评论内容映射
        comment_map = {}
        promoted_comment_ids = set()
        for ev in evidences:
            if ev.comments:
                for c in ev.comments:
                    comment_map[c.id] = c
            if ev.metadata.get("origin") == "comment_promotion":
                promoted_comment_ids.add(ev.metadata.get("comment_id"))
        
        for i, score in enumerate(top_scores, 1):
            comment = comment_map.get(score.comment_id)
            if comment:
                is_promoted = score.comment_id in promoted_comment_ids
                mark = "✨ [已晋升为证据]" if is_promoted else ""
                report += f"### {i}. [{score.total_score:.2f}] {comment.author}\n"
                report += f"> {comment.content}\n\n"
                report += f"- **分析**: {score.rationale}\n"
                report += f"- **状态**: {mark}\n\n"

    # 4. 待解疑点
    if timeline and timeline.open_questions:
        report += "## ❓ 待解疑点 (Open Questions)\n\n"
        for q in timeline.open_questions:
            report += f"- **[{q.id}]** {q.question}\n"
    
    return report

async def run_analysis(query: str, strategy: Optional[str] = None, depth: Optional[str] = None):
    """
    运行完整的事件链分析流程（基于 LangGraph）。
    
    Args:
        query: 事件查询关键词
        strategy: 检索策略 (generic/weibo/xhs/mixed)
        depth: 证据抓取深度 (quick/balanced/deep)
    """
    print(f"🔍 正在分析事件: {query}")
    print("=" * 60)
    
    # 初始化存储管理器
    storage = StorageManager()
    start_time = datetime.now()
    run_dir = storage.start_run(query)
    print(f"[DeepTrace] Run directory created: {run_dir}")
    
    # 初始化图
    app = create_graph()
    
    # 初始化状态
    config = {
        "max_loops": 3,
        "model_name": "qwen-2.5-32b" # 示例配置
    }
    
    initial_state = {
        "initial_query": query,
        "current_query": query,
        "loop_step": 0,
        "max_loops": config["max_loops"]
    }
    
    # 如果指定了策略，预设到 initial_state
    if strategy:
        strategy_map = {
            "generic": SearchStrategy.GENERIC,
            "weibo": SearchStrategy.WEIBO,
            "xhs": SearchStrategy.XHS,
            "mixed": SearchStrategy.MIXED,
        }
        if strategy.lower() in strategy_map:
            initial_state["search_strategy"] = strategy_map[strategy.lower()]
            print(f"📌 策略已手动指定: {strategy.upper()}")
    
    # 如果指定了证据深度，预设到 initial_state
    if depth:
        if depth.lower() in ["quick", "balanced", "deep"]:
            initial_state["evidence_depth"] = depth.lower()
            print(f"📊 证据深度已手动指定: {depth.upper()}")
    
    # 执行图
    try:
        state = await app.ainvoke(initial_state, config={"recursion_limit": 100})
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        return

    # 获取结果
    steps = state.get("steps", [])
    timeline = state.get("timeline") or Timeline(events=[], open_questions=[])
    comment_scores = state.get("comment_scores", [])
    evidences = state.get("evidences", [])
    claims = state.get("claims", [])
    
    # 打印执行步骤
    print("\n[执行轨迹]")
    for step in steps:
        print(f"  👉 {step}")
        
    # 打印关键评论 (控制台简略版)
    if comment_scores:
        print("\n[关键评论挖掘]")
        print("=" * 60)
        top_scores = sorted(comment_scores, key=lambda x: x.total_score, reverse=True)[:5]
        # ... (此处省略控制台详细打印，主要依靠 Report)
        print(f"已识别 {len(comment_scores)} 条高价值评论，详情请见报告。")
    
    # 打印最终报告 (控制台简略版)
    print("\n[生成报告]")
    print("=" * 60)
    if timeline.events:
        print(timeline.to_markdown())
    else:
        print("⚠️  未能生成时间线报告")
    print("=" * 60)
    
    # --- 存储逻辑 ---
    end_time = datetime.now()
    stats = {
        "evidence_count": len(evidences),
        "event_count": len(timeline.events),
        "loops": state.get("loop_step", 0),
    }
    
    # 生成完整报告
    report_md = _render_report(query, timeline, evidences, comment_scores, stats)
    
    # 保存所有文件
    print(f"\n💾 正在保存结果到: {run_dir}")
    storage.save_meta(
        run_dir,
        topic=query,
        start_time=start_time,
        end_time=end_time,
        model=config["model_name"],
        config=config,
        stats=stats
    )
    if timeline:
        storage.save_timeline(run_dir, timeline)
    storage.save_evidences(run_dir, evidences)
    storage.save_report(run_dir, report_md)
    
    # 生成叙事性报告
    print(f"\n📝 正在生成叙事性调查报告...")
    narrative_report_md = await write_narrative_report(query, timeline, evidences, claims=claims)
    (run_dir / "narrative_report.md").write_text(narrative_report_md, encoding="utf-8")
    
    print(f"✅ 分析完成！")
    print(f"   - 结构化报告: {run_dir / 'report.md'}")
    print(f"   - 调查报告文章: {run_dir / 'narrative_report.md'}")

def main():
    parser = argparse.ArgumentParser(
        description="DeepTrace Event Chain Investigator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python -m src.interface.cli --query "翻车"
  python -m src.interface.cli --query "DeepSeek" --strategy mixed
  python -m src.interface.cli --query "iPhone测评" --strategy xhs
        """
    )
    parser.add_argument(
        "--query", 
        type=str, 
        required=True, 
        help="事件查询关键词（如：'翻车'、'产品问题'）"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["generic", "weibo", "xhs", "mixed"],
        default=None,
        help="检索策略: generic(通用搜索), weibo(微博专项), xhs(小红书专项), mixed(混合模式)。不指定则由AI自动决策。"
    )
    parser.add_argument(
        "--depth",
        type=str,
        choices=["quick", "balanced", "deep"],
        default=None,
        help="证据抓取深度: quick(5条结果), balanced(10条结果), deep(15条结果)。不指定则由AI自动决策。"
    )
    
    args = parser.parse_args()
    
    # Windows 兼容性处理
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # 强制设置 stdout 编码为 utf-8
        sys.stdout.reconfigure(encoding='utf-8')
        
    asyncio.run(run_analysis(args.query, args.strategy, args.depth))

if __name__ == "__main__":
    main()
