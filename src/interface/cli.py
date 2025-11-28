import argparse
import sys
import asyncio
from typing import List

from ..fetchers import MockFetcher, FetchQuery
from ..agents.event_extractor import extract_event_from_evidence
from ..agents import build_timeline
from ..core.models.events import EventNode

async def run_analysis(query: str):
    """
    运行完整的事件链分析流程。
    
    Args:
        query: 事件查询关键词
    """
    print(f"🔍 正在分析事件: {query}")
    print("=" * 60)
    
    # Step 1: 使用 MockFetcher 获取证据
    print("\n[Step 1/4] 检索证据...")
    fetcher = MockFetcher()
    fetch_query = FetchQuery(keywords=query, limit=5)
    evidences = await fetcher.fetch(fetch_query)
    print(f"✅ 找到 {len(evidences)} 条证据")
    
    if not evidences:
        print("⚠️  未找到相关证据，程序退出")
        return
    
    # Step 2: 从证据中提取事件节点
    print("\n[Step 2/4] 使用 LLM 提取事件节点...")
    events: List[EventNode] = []
    for idx, evidence in enumerate(evidences, 1):
        print(f"  处理证据 {idx}/{len(evidences)}...")
        event = await extract_event_from_evidence(evidence)
        if event:
            events.append(event)
            print(f"    ✅ 提取到事件: {event.title}")
        else:
            print(f"    ⚠️  该证据未能提取事件")
    
    if not events:
        print("\n⚠️  未能从证据中提取任何事件")
        return
    
    print(f"\n✅ 成功提取 {len(events)} 个事件节点")
    
    # Step 3: 构建时间线
    print("\n[Step 3/4] 构建时间线...")
    timeline = build_timeline(events)
    timeline.title = f"事件链分析: {query}"
    timeline.summary = f"基于 {len(evidences)} 条证据提取的 {len(events)} 个事件节点"
    print("✅ 时间线构建完成")
    
    # Step 4: 输出 Markdown 报告
    print("\n[Step 4/4] 生成报告...")
    print("=" * 60)
    print(timeline.to_markdown())
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
        
    asyncio.run(run_analysis(args.query))

if __name__ == "__main__":
    main()
