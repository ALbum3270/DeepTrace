"""
Writer Agent (Content Generator).
Role: Write specific report sections based on the Director's plan.
Features:
- Deep Thinking (Qwen) enabled.
- Hard Constraint: Causal Word Ban (Contract 1).
- Hard Constraint: Immutable Citations (Contract 2).
"""
import logging
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ...llm.factory import init_llm
from .state import SwarmState, SectionPlan
from ...core.models.evidence import Evidence
from ...core.models.claim import Claim
from ...core.models.events import EventNode

logger = logging.getLogger(__name__)

# Contract 1: Causal Word Ban List
CAUSAL_BAN_LIST = [
    "caused", "led to", "resulted in", "triggered", "driven by", 
    "due to", "because of", "responsible for", "attributed to"
]

class WriterAgent:
    """
    The Writer generates the markdown content for a single section.
    """
    
    def __init__(self):
        # Enable Deep Thinking for Writer
        self.llm = init_llm(temperature=0.7, enable_thinking=True) 
        self.parser = StrOutputParser()
        
    def write_section(self, section: SectionPlan, state: SwarmState) -> str:
        """
        Generates markdown for the given section.
        """
        # 1. Filter Context
        # Only include events/claims assigned to this section
        related_events = [e for e in state["events"] if e.id in section.assigned_event_ids]
        related_claims = [c for c in state["claims"] if c.id in section.assigned_claim_ids]
        disputed_claims = [c for c in state["claims"] if c.id in section.disputed_claim_ids]
        
        # Gather evidences linked to these events/claims for context
        # Ideally, we should pass Span/Evidence text directly.
        # For now, pass relevant Evidence objects full text (truncated?)
        # Let's assume state["evidences"] relates to the whole report, 
        # so we filter those relevant to claims/events or just pass all if small.
        # Optimization: Pass all for now (context window usually large enough in modern models)
        evidence_context = self._format_evidence(state["evidences"])
        
        # 2. Build Prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_content(section, related_events, related_claims, disputed_claims, evidence_context)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
        
        # 3. Invoke
        chain = prompt | self.llm | self.parser
        content = chain.invoke({})
        
        # 4. Post-Check (Contract 1)
        # We can implement a retry loop here if banned words are found.
        # For now, just log warning. The Critic will catch this later.
        self._check_causal_ban(content)
        
        return content

    def _format_evidence(self, evidences: List[Evidence]) -> str:
        # Format: [Ev{id}] {content}...
        lines = []
        for ev in evidences:
            lines.append(f"--- Evidence ID: {ev.id} ---\n{ev.content[:800]}...\n")
        return "\n".join(lines)

    def _check_causal_ban(self, text: str):
        lower_text = text.lower()
        violations = [word for word in CAUSAL_BAN_LIST if word in lower_text]
        if violations:
            logger.warning(f"Contract 1 Violation: Found banned causal words: {violations}")

    def _build_user_content(self, section: SectionPlan, events: List[EventNode], claims: List[Claim], disputed: List[Claim], evidence_text: str) -> str:
        events_str = "\n".join([f"- {e.time}: {e.title} (ID:{e.id})" for e in events])
        claims_str = "\n".join([f"- [VERIFIED] {c.content} (ID:{c.id})" for c in claims])
        disputed_str = "\n".join([f"- [DISPUTED] {c.content} (ID:{c.id})" for c in disputed])
        
        return f"""
Section Request:
Title: {section.title}
Description: {section.description}
Conflict Policy: {section.conflict_policy}

Assigned Events:
{events_str}

Assigned Verified Claims:
{claims_str}

Disputed/Conflicting Claims (Handle with care):
{disputed_str}

Available Evidence Context:
{evidence_text}

Task: Write the full content for this section in Markdown.
"""

    def _get_system_prompt(self) -> str:
        ban_list_str = ", ".join(f'"{w}"' for w in CAUSAL_BAN_LIST)
        return f"""You are the **Citadel Writer**, an elite investigative journalist AI.
Your goal is to write a rigorous, objective section of a report based on provided evidence.

**CORE CONTRACTS (Immutable Rules)**:
1.  **Causal Word Ban (Contract 1)**: You are STRICTLY FORBIDDEN from using high-certainty causal language unless writing a conclusion explicitly supported by a 'Confirmed' claim.
    -   **BANNED**: {ban_list_str}
    -   **USE INSTEAD**: "followed by", "coincided with", "preceded", "associated with", "linked to".
    -   *Reason*: Correlation != Causation. We must avoid hallucinated causality.

2.  **Citation Protocol (Contract 2)**: Every factual statement MUST be followed by a citation.
    -   Format: `[Ev{{id}}]` (e.g., `[Ev123]`) or specific span `[Ev123#c1@abc]`.
    -   Do not invent citations.

3.  **Conflict Handling**:
    -   If `Conflict Policy` is 'present_both', you must neutrally describe the conflict: "Source A states X [Ev1], while Source B states Y [Ev2]."
    -   Do NOT force a conclusion if claims are Disputed.

**Style Guide**:
-   Tone: Clinical, detached, high-precision (like a NTSB accident report).
-   No fluff, no dramatic adjectives ("shocking", "devastating").
-   Focus on timeline and sequence.

**Output**: Return ONLY the Markdown content for the section.
"""
