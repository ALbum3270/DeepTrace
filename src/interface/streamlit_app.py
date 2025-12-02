import streamlit as st
import asyncio
import pandas as pd
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from datetime import datetime
from typing import Dict, Any

from src.graph.workflow import create_graph
from src.core.models.timeline import Timeline
from src.core.models.evidence import Evidence
from src.agents.report_writer import write_narrative_report

# --- Configuration ---
st.set_page_config(
    page_title="DeepTrace · 侦探式事件分析",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* Main header styling */
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 700;
        font-size: 2.5rem !important;
        margin-bottom: 1rem;
    }
    
    /* Subheader styling */
    h2, h3 {
        color: #667eea;
        font-weight: 600;
    }
    
    /* Card-like containers */
    .stExpander {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.05) 100%);
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    /* Dataframe styling */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)


# --- Logic ---
@st.cache_resource
def get_graph():
    """Cache the graph compilation to avoid recompiling on every rerun."""
    return create_graph()

async def run_analysis_async(query: str, max_loops: int, model_name: str):
    """Async wrapper for running the graph."""
    graph = get_graph()
    
    initial_state = {
        "initial_query": query,
        "current_query": query,
        "loop_step": 0,
        "max_loops": max_loops,
        # "model_name": model_name # Passed via config/env usually, but state can carry it if needed
    }
    
    # Run the graph
    final_state = await graph.ainvoke(initial_state)
    
    # Generate narrative report if not present (though workflow usually does it via reporter node if configured, 
    # but currently CLI does it manually. Let's do it manually here too for consistency with CLI)
    # Note: In a perfect world, this should be a node in the graph.
    if "narrative_report" not in final_state:
        timeline = final_state.get("timeline")
        evidences = final_state.get("evidences", [])
        if timeline and evidences:
            report = await write_narrative_report(query, timeline, evidences)
            final_state["narrative_report"] = report
            
    return final_state

def run_deeptrace_sync(query: str, max_loops: int, model_name: str):
    """Synchronous entry point for Streamlit."""
    return asyncio.run(run_analysis_async(query, max_loops, model_name))

# --- UI Components ---

def render_report_tab(state: Dict[str, Any]):
    st.header("📄 叙事性调查报告")
    
    report = state.get("narrative_report")
    if report:
        st.markdown(report)
    else:
        st.info("暂无叙事报告。可能分析尚未完成或未能生成有效时间线。")
        
    st.divider()
    st.subheader("结构化摘要")
    if state.get("timeline"):
        st.markdown(state["timeline"].to_markdown())

def render_timeline_tab(state: Dict[str, Any]):
    st.header("🕒 事件时间线")
    
    timeline = state.get("timeline")
    evidences = state.get("evidences", [])
    
    if not timeline or not timeline.events:
        st.info("暂无时间线数据。")
        return
    
    # Build evidence URL map for quick lookup
    evidence_url_map = {ev.id: ev.url for ev in evidences if ev.url}
        
    # Enhanced Card-based Timeline View
    for idx, ev in enumerate(timeline.events, 1):
        time_str = ev.time.strftime('%m月%d日 %H:%M') if ev.time else "时间未知"
        confidence_color = "#10b981" if ev.confidence > 0.8 else "#f59e0b" if ev.confidence > 0.5 else "#ef4444"
        
        # Get first evidence URL for the event (if available)
        primary_url = None
        if ev.evidence_ids:
            for eid in ev.evidence_ids:
                if eid in evidence_url_map:
                    primary_url = evidence_url_map[eid]
                    break
        
        # Build title with optional link
        if primary_url:
            title_html = f'<a href="{primary_url}" target="_blank" style="color: #2d3748; text-decoration: none; border-bottom: 2px solid #667eea;">{ev.title}</a>'
        else:
            title_html = ev.title
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.04) 100%);
            border-left: 4px solid #667eea;
            border-radius: 10px;
            padding: 1.8rem;
            margin-bottom: 1.8rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.12)';" 
           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 1px 3px rgba(0,0,0,0.08)';">
            
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                <div style="flex: 1;">
                    <div style="font-size: 0.85rem; color: #9ca3af; font-weight: 500; margin-bottom: 0.5rem;">
                        #{idx}
                    </div>
                    <h3 style="
                        font-size: 1.15rem;
                        font-weight: 700;
                        color: #1f2937;
                        margin: 0;
                        line-height: 1.5;
                    ">{title_html}</h3>
                    <div style="font-size: 0.88rem; color: #6b7280; margin-top: 0.4rem; font-weight: 500;">
                        📅 {time_str}
                    </div>
                </div>
                <div style="
                    background: {confidence_color};
                    color: white;
                    padding: 0.35rem 0.9rem;
                    border-radius: 20px;
                    font-size: 0.82rem;
                    font-weight: 700;
                    white-space: nowrap;
                    margin-left: 1rem;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    {ev.confidence:.0%}
                </div>
            </div>
            
            <div style="
                font-size: 1.02rem;
                color: #374151;
                line-height: 1.75;
                margin-bottom: 1rem;
            ">{ev.description}</div>
            
            <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.9rem; color: #6b7280;">
                {f'<div><strong>📰 来源:</strong> {ev.source}</div>' if ev.source else ''}
                {f'<div><strong>🔗 证据:</strong> {len(ev.evidence_ids)} 条</div>' if ev.evidence_ids else ''}
                <div><strong>📊 状态:</strong> {ev.status.value}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # 2. Mermaid View
    st.divider()
    st.subheader("📊 可视化时序图")
    mermaid_code = "timeline\n    title 事件发展脉络\n"
    for ev in timeline.events:
        date_str = ev.time.strftime('%Y-%m-%d') if ev.time else "未知时间"
        title_safe = ev.title.replace(":", " ").replace('"', "'")
        mermaid_code += f"    {date_str} : {title_safe}\n"
        
    st.markdown(f"```mermaid\n{mermaid_code}\n```")

def render_evidence_tab(state: Dict[str, Any]):
    st.header("📚 证据板")
    
    evidences = state.get("evidences", [])
    if not evidences:
        st.info("暂无证据。")
        return
        
    # Group by Platform/Source
    by_platform = {}
    for ev in evidences:
        # Use source_type or platform if available
        key = f"{ev.source_type} ({ev.source.value if hasattr(ev.source, 'value') else ev.source})"
        by_platform.setdefault(key, []).append(ev)
        
    for group, items in by_platform.items():
        with st.expander(f"📂 {group} · {len(items)} 条"):
            for ev in items:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{ev.title or '无标题'}**")
                    if ev.url:
                        st.markdown(f"🔗 [原文链接]({ev.url})")
                    st.caption(f"ID: {ev.id} | Time: {ev.publish_time}")
                    st.text(ev.content[:200] + "..." if len(ev.content) > 200 else ev.content)
                with col2:
                    if ev.metadata.get("origin") == "comment_promotion":
                        st.success("✨ 评论晋升")
                st.divider()

def render_debug_tab(state: Dict[str, Any]):
    st.header("🛠 调试信息")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("状态概览")
        strategy = state.get("search_strategy")
        st.json({
            "search_strategy": strategy.value if hasattr(strategy, 'value') else str(strategy),
            "loop_step": state.get("loop_step"),
            "evidence_count": len(state.get("evidences", [])),
            "event_count": len(state.get("timeline", Timeline(events=[])).events) if state.get("timeline") else 0
        })
        
    with col2:
        st.subheader("执行步骤")
        steps = state.get("steps", [])
        if steps:
            for step in steps:
                st.text(f"• {step}")
        else:
            st.text("无执行步骤记录")
        
    st.subheader("完整 State (精简)")
    # Create a simplified version of state that's JSON-serializable
    simplified_state = {
        "initial_query": state.get("initial_query"),
        "current_query": state.get("current_query"),
        "search_strategy": str(state.get("search_strategy")),
        "loop_step": state.get("loop_step"),
        "max_loops": state.get("max_loops"),
        "evidence_count": len(state.get("evidences", [])),
        "event_count": len(state.get("timeline", Timeline(events=[])).events) if state.get("timeline") else 0,
        "open_questions": len(state.get("timeline", Timeline(events=[])).open_questions) if state.get("timeline") else 0
    }
    st.json(simplified_state)

# --- Main App ---

def main():
    st.title("DeepTrace · 侦探式事件分析")
    st.markdown("输入一个事件或疑点，DeepTrace 将自动进行多轮检索、深挖评论并生成调查报告。")
    
    # Sidebar
    with st.sidebar:
        st.header("配置")
        max_loops = st.slider("最大深挖轮数", min_value=1, max_value=5, value=3)
        model_name = st.selectbox("模型选择", ["qwen-2.5-32b", "gpt-4o", "claude-3.5-sonnet"], index=0)
        st.info("当前默认使用 Qwen-2.5-32b (通过 API)。")
        
    # Input
    query = st.text_area("请输入事件描述 / 疑点问题", height=100, placeholder="例如：特斯拉 Robotaxi 发布会评价如何？")
    
    # Session State
    if "run_state" not in st.session_state:
        st.session_state.run_state = None
        
    # Action
    if st.button("🔍 开始侦探分析", type="primary"):
        if not query.strip():
            st.warning("请输入有效的问题。")
        else:
            with st.status("正在进行深度调查...", expanded=True) as status:
                st.write("正在初始化智能体...")
                try:
                    # Run Analysis
                    final_state = run_deeptrace_sync(query, max_loops, model_name)
                    st.session_state.run_state = final_state
                    status.update(label="分析完成！", state="complete", expanded=False)
                except Exception as e:
                    st.error(f"运行出错: {e}")
                    status.update(label="分析失败", state="error")
                    
    # Results
    if st.session_state.run_state:
        tabs = st.tabs(["📄 叙事报告", "🕒 时间线", "📚 证据板", "🛠 调试"])
        
        with tabs[0]:
            render_report_tab(st.session_state.run_state)
        with tabs[1]:
            render_timeline_tab(st.session_state.run_state)
        with tabs[2]:
            render_evidence_tab(st.session_state.run_state)
        with tabs[3]:
            render_debug_tab(st.session_state.run_state)

if __name__ == "__main__":
    main()
