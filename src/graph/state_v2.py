"""
V2 State Definitions for DeepTrace.
Split into GlobalState (Supervisor) and WorkerState (Investigator) to support isolation and parallelism.
"""

from typing import TypedDict, List, Annotated
import operator
from langchain_core.messages import BaseMessage


class WorkerState(TypedDict):
    """
    State for the Worker Subgraph (The Investigator).
    Isolated from the global state to allow parallel execution.
    """

    # Input: The specific topic assigned by Supervisor
    topic: str

    # Internal: Messages exchanged during research (Tool calls, Search results)
    # This list grows during the worker's loop but is COMPRESSED into 'notes' at the end.
    messages: Annotated[List[BaseMessage], operator.add]

    # Output: Compressed knowledge returned to Supervisor
    # This replaces the raw 'messages' to save tokens in the Global State.
    research_notes: str

    # Output: timeline entries extracted by the worker
    timeline: Annotated[List[dict], operator.add]

    # Output: conflict candidates detected in worker extraction
    conflict_candidates: Annotated[List[dict], operator.add]

    # Output: evidences with full_content for Phase1 sidecar
    evidences: Annotated[List[dict], operator.add]

    # Required topic tokens to keep the worker on-topic
    required_tokens: List[str]


class GlobalState(TypedDict):
    """
    State for the Global Graph (The Orchestrator).
    Tracks the overall progress, user interaction, and aggregated knowledge.
    """

    # Input: Original User Query
    original_query: str

    # Tracking: Run/session identifier (for artifact naming)
    run_id: str
    # Metadata: optional archive path for the run record
    run_record_path: str
    # Snapshot of enabled policies/config (for audit)
    enabled_policies_snapshot: dict

    # Derived: Research objective (can be refined by clarification node)
    objective: str

    # Clarification flow control (skip clarify node if already handled)
    clarification_done: bool

    # Guardrail: Tokens that must be present for on-topic content (e.g., ["gpt-5"])
    required_tokens: List[str]

    # Planning: Research Brief generated in Phase 2
    research_brief: str

    # Execution: Conversation history of the Supervisor
    # Contains: User messages, Supervisor thoughts, and Tools outputs (which contain the Worker's research_notes)
    messages: Annotated[List[BaseMessage], operator.add]

    # Knowledge: The Consolidated Truth (Timeline & Facts)
    # In Phase 3, the 'Debater' will curate this list.
    timeline: Annotated[List[dict], operator.add]
    investigation_log: Annotated[List[str], operator.add]

    # Aggregated Research: Notes from Worker executions
    research_notes: Annotated[List[str], operator.add]

    # Aggregated conflict candidates from workers (pruned/merged in nodes)
    conflict_candidates: List[dict]

    # Aggregated evidences with full_content (for Phase1 sidecar)
    evidences: Annotated[List[dict], operator.add]

    # Cache of processed conflict candidate IDs (to avoid re-trigger loops)
    conflict_candidate_cache: List[str]

    # Conflict tracking: Debater verdicts and dispute metadata
    conflicts: Annotated[List[dict], operator.add]

    # Phase 0 structured artifacts (optional; populated by finalizer pipeline)
    facts_index: dict
    structured_report: dict
    report_citations: Annotated[List[dict], operator.add]
    gate_report: dict

    # Output: Final markdown report
    final_report: str

    # Tracking: Executed tool calls for semantic deduplication
    executed_tools: Annotated[List[dict], operator.add]
