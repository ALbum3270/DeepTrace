import argparse
import sys
import asyncio
from ..graph.workflow import create_graph

async def run_analysis(query: str):
    """
    运行完整的事件链分析流程（基于 LangGraph）。
    
    Args:
        query: 事件查询关键词
    """
    print(f"🔍 正在分析事件: {query}")
    print("=" * 60)
    
    # 初始化图
    app = create_graph()
    
    # 初始化状态
    initial_state = {
        "initial_query": query,
        "current_query": query,
        "loop_step": 0,
        "max_loops": 3  # 允许最多 3 轮检索
    }
    
    # 执行图
    try:
        state = await app.ainvoke(initial_state)
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        return

    # 获取结果
    steps = state.get("steps", [])
    timeline = state.get("timeline")
    comment_scores = state.get("comment_scores", [])
    
    # 打印执行步骤
    print("\n[执行轨迹]")
    for step in steps:
        print(f"  👉 {step}")
        
    # 打印关键评论
    if comment_scores:
        print("\n[关键评论挖掘]")
        print("=" * 60)
        # 按总分降序排序，取前 5 条
        top_scores = sorted(comment_scores, key=lambda x: x.total_score, reverse=True)[:5]
        
        # 为了显示评论内容，我们需要从 evidences 中反查
        # 这里的实现略显低效，但在 MVP 规模下可接受
        evidences = state.get("evidences", [])
        comment_map = {}
        promoted_comment_ids = set()
        
        for ev in evidences:
            # 收集评论内容
            if ev.comments:
                for c in ev.comments:
                    comment_map[c.id] = c
            # 收集已晋升的评论ID
            if ev.metadata.get("origin") == "comment_promotion":
                promoted_comment_ids.add(ev.metadata.get("comment_id"))
                
        for i, score in enumerate(top_scores, 1):
            comment = comment_map.get(score.comment_id)
            if comment:
                is_promoted = score.comment_id in promoted_comment_ids
                promoted_mark = " ✨ [已晋升为证据]" if is_promoted else ""
                
                print(f"{i}. [{score.total_score:.2f}] {comment.author}: {comment.content}{promoted_mark}")
                print(f"   💡 分析: {score.rationale}")
                print(f"   🏷️  标签: {', '.join(score.tags) if score.tags else '无'}")
                print("-" * 40)
    
    # 打印最终报告
    print("\n[生成报告]")
    print("=" * 60)
    if timeline:
        print(timeline.to_markdown())
    else:
        print("⚠️  未能生成时间线报告")
    print("=" * 60)
    print("\n✅ 分析完成！")

def main():
    parser = argparse.ArgumentParser(
        description="DeepTrace Event Chain Investigator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python -m src.interface.cli --query "翻车"
  python -m src.interface.cli --query "产品质量问题"
        """
    )
    parser.add_argument(
        "--query", 
        type=str, 
        required=True, 
        help="事件查询关键词（如：'翻车'、'产品问题'）"
    )
    
    args = parser.parse_args()
    
    # Windows 兼容性处理
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # 强制设置 stdout 编码为 utf-8
        sys.stdout.reconfigure(encoding='utf-8')
        
    asyncio.run(run_analysis(args.query))

if __name__ == "__main__":
    main()
