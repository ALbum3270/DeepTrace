"""
Layer 3: Swarm Graph Controller.
Integrates Director, Writer, and Critic into a coherent workflow.
Enforces Loop Budgets (Circuit Breaker).
"""
import logging
from typing import Literal, Dict, Any, List

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import SwarmState, SectionPlan, ReportOutline
from .director import DirectorAgent
from .writer import WriterAgent
from .critic import CriticAgent, CritiqueResult

logger = logging.getLogger(__name__)

# Config
MAX_REVISION_LOOPS_PER_SECTION = 4

# Initialize Agents
director = DirectorAgent()
writer = WriterAgent()
critic = CriticAgent()

def director_node(state: SwarmState) -> Dict[str, Any]:
    """
    Node: Director
    Action: Generate Outline
    """
    logger.info("--- Director Node: Generating Outline ---")
    outline = director.create_outline(state)
    
    # Initialize implementation state
    return {
        "outline": outline,
        "current_section_idx": 0,
        "draft_sections": {},
        "revision_count": 0,
        "global_revision_count": 0,
        "final_report": ""
    }

def writer_node(state: SwarmState) -> Dict[str, Any]:
    """
    Node: Writer
    Action: Draft content for current section
    """
    idx = state["current_section_idx"]
    outline = state["outline"]
    
    # Check if we are done
    if not outline or idx >= len(outline.sections):
         return {} # Should ideally transition to END before this

    section = outline.sections[idx]
    logger.info(f"--- Writer Node: Drafting Section {idx+1}/{len(outline.sections)}: {section.title} ---")
    
    # Call Writer
    content = writer.write_section(section, state)
    
    # Update draft in state
    drafts = state["draft_sections"].copy()
    drafts[section.id] = content
    
    return {
        "draft_sections": drafts,
        "critique_feedback": None # Clear previous feedback
    }

def critic_node(state: SwarmState) -> Dict[str, Any]:
    """
    Node: Critic
    Action: Verify current draft
    """
    idx = state["current_section_idx"]
    outline = state["outline"]
    section = outline.sections[idx]
    draft = state["draft_sections"].get(section.id, "")
    
    # Ideally we pass relevant evidence only. For now passing all.
    # TODO: Filter evidence by section.assigned_event_ids
    evidences_str = str(state["evidences"]) 
    
    logger.info(f"--- Critic Node: Verifying Section {section.id} ---")
    result: CritiqueResult = critic.verify_section(draft, section, evidences_str)
    
    logger.info(f"Critic Result: Score={result.score}, NLI={result.nli_state}, R={result.revision_needed}")
    
    return {
        "critique_feedback": result.feedback if result.revision_needed else None,
        "revision_count": state["revision_count"] + 1 if result.revision_needed else 0
        # If passed, reset revision_count for next section (in router)
    }

def should_continue(state: SwarmState) -> Literal["writer_node", "next_section", "finalize"]:
    """
    Edge Logic: Router
    Decides between Re-write, Next Section, or Finish.
    """
    feedback = state.get("critique_feedback")
    rev_count = state.get("revision_count", 0)
    idx = state.get("current_section_idx", 0)
    outline = state.get("outline")
    
    # Case 1: Needs Revision
    if feedback:
        if rev_count < MAX_REVISION_LOOPS_PER_SECTION:
            logger.info(f"Routing: REVISION needed (Attempt {rev_count+1})")
            return "writer_node"
        else:
            logger.warning(f"Routing: MAX REVISIONS ({MAX_REVISION_LOOPS_PER_SECTION}) reached. Forcing progress.")
            # Fallthrough to Next Section (Circuit Breaker)
            pass

    # Case 2: Passed or Forced Progress -> Move to Next Section
    next_idx = idx + 1
    if outline and next_idx < len(outline.sections):
        logger.info(f"Routing: Section {idx} Done -> Next Section {next_idx}")
        # Need to update index here? No, conditional edge shouldn't update state directly usually,
        # but LangGraph allows it via nodes. 
        # We need a 'sections_manager' node to increment index, or do it in Critic/Writer?
        # Better: Have a 'next_section_node' to handle index increment.
        return "next_section"
    
    # Case 3: All Sections Done
    logger.info("Routing: All Sections Done -> Finalize")
    return "finalize"

def next_section_node(state: SwarmState) -> Dict[str, Any]:
    """
    Node: Increment Section Index and reset counters
    """
    return {
        "current_section_idx": state["current_section_idx"] + 1,
        "revision_count": 0,
        "critique_feedback": None
    }

def finalize_node(state: SwarmState) -> Dict[str, Any]:
    """
    Node: Assemble Final Report
    """
    logger.info("--- Finalizing Report ---")
    outline = state["outline"]
    drafts = state["draft_sections"]
    
    if not outline:
        return {"final_report": "Error: No outline generated."}
        
    parts = [f"# {outline.title}\n\n## Introduction\n{outline.introduction}\n"]
    for sec in outline.sections:
        content = drafts.get(sec.id, "(Section content missing)")
        parts.append(f"## {sec.title}\n{content}\n")
    
    parts.append(f"## Conclusion\n{outline.conclusion}")
    full_report = "\n".join(parts)
    
    return {"final_report": full_report}

def create_swarm_graph():
    """Build the LangGraph"""
    builder = StateGraph(SwarmState)
    
    builder.add_node("director", director_node)
    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)
    builder.add_node("next_section_manager", next_section_node)
    builder.add_node("finalizer", finalize_node)
    
    # Flow
    builder.add_edge(START, "director")
    builder.add_edge("director", "writer")
    builder.add_edge("writer", "critic")
    
    builder.add_conditional_edges(
        "critic",
        should_continue,
        {
            "writer_node": "writer",
            "next_section": "next_section_manager",
            "finalize": "finalizer"
        }
    )
    
    builder.add_edge("next_section_manager", "writer")
    builder.add_edge("finalizer", END)
    
    return builder.compile()
