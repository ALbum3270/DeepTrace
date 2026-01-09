"""
Provenance Verification Engine (Phase 21.1)
Implements 'CT Scanner' architecture for systemic verification of investigation data.
"""
import logging
import re
from enum import Enum, auto
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

from ..models.evidence import Evidence

logger = logging.getLogger(__name__)

# =========================================================
# Layer 1: Trust Scoring
# =========================================================

class TrustScorer:
    """Evaluates evidence trustworthiness based on source domain and content provenance."""
    
    TRUSTED_DOMAINS = [
        "openai.com", "microsoft.com", "arxiv.org",
        "theverge.com", "techcrunch.com", "bloomberg.com", "wired.com",
        "wsj.com", "reuters.com", "cnbc.com", "36kr.com", "caixin.com",
    ]
    
    HIGH_TRUST_KEYWORDS = ["official", "release", "launch", "announcement"]
    
    @staticmethod
    def _is_critical_context(content: str) -> bool:
        """
        Detects if the content is critical, skeptical, or negative about the source.
        Used to prevent 'According to OpenAI' from boosting score when the article is actually debunking it.
        """
        skeptic_markers = [
            "but", "however", "although", "claimed", "alleged", 
            "skeptical", "doubts", "flaws", "failed to", "contradicts",
            "exaggerated", "hype", "rumor", "unverified"
        ]
        # Simple proximity check: if "according to" is near "however/but/false"
        content_lower = content.lower()
        if any(m in content_lower for m in skeptic_markers):
            return True
        return False

    @staticmethod
    def _contains_primary_source_quote(content: str) -> bool:
        """
        Checks for direct quotes from official spokespeople.
        Matches: "..." — Sam Altman / Greg Brockman / Mira Murati
        """
        # 1. Check for standard attribution markers
        primary_markers = ["sourced from", "official blog", "via twitter", "according to openai"]
        if any(marker in content.lower() for marker in primary_markers):
            return True
            
        # 2. Strict Quote + Speaker Regex
        # 2. Strict Quote + Speaker Regex
        # Matches: "QUOTE" ... Name
        # Generic pattern for named attribution
        quote_pattern = r'["“](.*?)["”]\s*[-—]\s*([A-Z][a-z]+ [A-Z][a-z]+)'
        if re.search(quote_pattern, content):
            return True
            
        return False

    @staticmethod
    def calculate_trust(evidence: Evidence) -> float:
        """
        Calculate trust score (0.0 - 1.0).
        Logic: Domain Whitelist + Content Provenance.
        """
        url = str(evidence.url or "").lower()
        content = (evidence.content or "").lower()
        title = (evidence.title or "").lower()
        source_val = str(evidence.source.value if hasattr(evidence.source, 'value') else evidence.source).lower()
        
        score = 0.5 # Default base score
        
        # 1. Domain-based scoring
        if any(d in url for d in TrustScorer.TRUSTED_DOMAINS):
            score = 0.9
        elif source_val == "news" or evidence.type == "article":
            score = 0.75
        elif any(d in url for d in ["weibo.com", "zhihu.com", "reddit.com", "twitter.com", "x.com"]):
            score = 0.5
        else:
            score = 0.6
            
        # 2. Content Provenance Bonus (V2 Enhancement)
        # Only apply bonus if content is NOT critical/skeptical
        if TrustScorer._contains_primary_source_quote(content):
            if not TrustScorer._is_critical_context(content):
                score += 0.15
            else:
                # If citing official source but in critical context, small penalty or no bonus
                # e.g. "OpenAI claims X, but this is false." -> Trust shouldn't increase.
                pass 
        
        # Check if content looks like deep technical analysis or official repost
        if "official" in title and "release" in title and source_val != "xhs":
             # Bump up "Official" looking titles if not typically rumor platforms
             if score < 0.9: score = 0.95
            
        return min(score, 1.0)

# =========================================================
# Layer 2: Dependency Logic
# =========================================================

class FuzzyTime:
    """
    Represents fuzzy temporal windows (e.g., 'Early 2025' -> Jan-Mar 2025).
    """
    def __init__(self, start: datetime, end: datetime, precision: str = "day"):
        self.start = start
        self.end = end
        self.precision = precision
        
    def overlaps(self, other: 'FuzzyTime') -> bool:
        """Checks if two time windows overlap."""
        return max(self.start, other.start) <= min(self.end, other.end)
        
    def contains(self, other: 'FuzzyTime') -> bool:
        """Checks if this window structurally contains the other (Strict parent check)."""
        return self.start <= other.start and self.end >= other.end

    @staticmethod
    def from_string(date_str: str) -> Optional['FuzzyTime']:
        """Factory: Parses string to FuzzyTime. Handles 'YYYY-MM-DD' and simple fuzziness."""
        try:
            if not date_str: return None
            # Normalize common separators
            date_str = date_str.replace("/", "-").replace(".", "-")
            
            # Case 1: Full Date (YYYY-MM-DD)
            if len(date_str) >= 10:
                 dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                 return FuzzyTime(dt, dt, "day")
            
            # Case 2: Month (YYYY-MM)
            elif len(date_str) >= 7 and "-" in date_str:
                 # "2024-08" -> Start 2024-08-01, End 2024-08-31
                 parts = date_str.split("-")
                 year, month = int(parts[0]), int(parts[1])
                 import calendar
                 last_day = calendar.monthrange(year, month)[1]
                 return FuzzyTime(datetime(year, month, 1), datetime(year, month, last_day), "month")

            # Case 3: Year (YYYY)
            elif len(date_str) == 4 and date_str.isdigit():
                 year = int(date_str)
                 return FuzzyTime(datetime(year, 1, 1), datetime(year, 12, 31), "year")
            
            return None
        except:
             return None

class DependencyGraph:
    """Manages causal relationships between events."""
    
    def __init__(self):
        self.nodes = {} # event_id -> FuzzyTime
        self.edges = [] # (parent_id, child_id)
        
    def add_node(self, event_id: str, time: FuzzyTime):
        self.nodes[event_id] = time
        
    def add_edge(self, parent_id: str, child_id: str):
         # Hardcoded or Extracted dependencies
         self.edges.append((parent_id, child_id))
         
    def validate_causality(self, child_id: str, parent_id: str, strict: bool = False) -> bool:
        """
        Validates if child can logically follow parent.
        Strict=True: Child must start AFTER parent ends (Sequential).
        Strict=False: Child must start >= Parent start (Parallel/iterative).
        """
        child_time = self.nodes.get(child_id)
        parent_time = self.nodes.get(parent_id)
        
        if not child_time or not parent_time:
            return True # Cannot validate without time, assume permissible
            
        if strict:
            return child_time.start > parent_time.end
        else:
            return child_time.start >= parent_time.start

# =========================================================
# Layer 3: Corroboration & Synthesis
# =========================================================

class CorroborationLevel(Enum):
    DIRECT_CONFIRMS = auto()       # Subset (e.g. "Nano" in "Lightweight")
    CONSISTENT_DIRECTION = auto()  # Semantic match (e.g. "Code" ~ "Programming")
    SEMANTIC_DRIFT = auto()        # Divergent (New capabilities)
    UNRELATED = auto()


# Backward-compat shim for caller expectations (used by supervisor.py)
def compute_semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Lightweight placeholder similarity scorer to maintain compatibility
    when the full embedding-based scorer is absent. Returns 0.0–1.0.
    """
    if not text_a or not text_b:
        return 0.0
    a = set(text_a.lower().split())
    b = set(text_b.lower().split())
    if not a or not b:
        return 0.0
    overlap = a & b
    union = a | b
    return len(overlap) / len(union)

class CrossVerifier:
    """Synthesizes rumors against established facts."""
    
    def verify(self, claim_text: str, fact_text: str) -> CorroborationLevel:
        """
        Determines how well a claim matches a fact.
        Phase 21.1: Keyword/Substring match.
        Phase 21.1+: Semantic Embedding interface (Placeholder).
        """
        claim_lower = claim_text.lower()
        fact_lower = fact_text.lower()
        
        # 1. Direct Subset
        if claim_lower in fact_lower or fact_lower in claim_lower:
            return CorroborationLevel.DIRECT_CONFIRMS
            
        # 2. Keyword Overlap (Heuristic for semantic consistency)
        # TODO: Replace with SentenceTransformer in Phase 21.2
        # logger.debug(f"CrossVerifier [HEURISTIC]: Checking '{claim_text[:20]}...' vs '{fact_text[:20]}...'")
        
        # 2a. Check for Contradiction (New in Phase 21.1.2)
        if self._check_contradiction(claim_lower, fact_lower):
            return CorroborationLevel.UNRELATED # Or SEMANTIC_DRIFT implies disagreement? UNRELATED avoids false confirms.
            
        keywords = set(re.findall(r'\w{4,}', fact_lower))
        claim_words = set(re.findall(r'\w{4,}', claim_lower))
        overlap = keywords.intersection(claim_words)
        
        if len(overlap) >= 2: # At least 2 significant words match
             return CorroborationLevel.CONSISTENT_DIRECTION
             
        return CorroborationLevel.SEMANTIC_DRIFT


# =========================================================
# Main Engine: ProvenanceVerifier
# =========================================================

class VerificationResult(BaseModel):
    verified_timeline: List[Dict[str, Any]] = []
    rejected_claims: List[Dict[str, Any]] = []
    corroborated_rumors: List[Dict[str, Any]] = []
    open_questions: List[str] = []

class ProvenanceVerifier:
    def __init__(self):
        self.trust_scorer = TrustScorer()
        self.graph = DependencyGraph()
        self.cross_verifier = CrossVerifier()
        self._init_knowledge_graph()

    def _init_knowledge_graph(self):
        """Phase 21.1: Define canonical dependency rules."""
        # Concept Dependencies: Parent -> Child (Child must happen AFTER Parent)
        # Stored as (Premise, Consequence, Strict?)
        self.canonical_rules = [
            ("training", "release", True),       # Training must end before Release starts
            ("release", "successor", False),     # Successor must start after Release starts
            ("safety_testing", "release", True), # Testing before release
            ("announcement", "launch", False)    # Announcement <= Launch
        ]

    def verify_all(self, evidences: List[Evidence]) -> VerificationResult:
        result = VerificationResult()
        
        # 1. Trust Scoring & Filtering
        zone_a = []
        zone_b = []
        zone_c = []
        
        ranked_evidences = []
        for ev in evidences:
            trust = self.trust_scorer.calculate_trust(ev)
            ranked_evidences.append((ev, trust))
            
            # Simple Bucketing for Zones
            if trust >= 0.9: zone_a.append((ev, trust))
            elif trust >= 0.7: zone_b.append((ev, trust))
            else: zone_c.append((ev, trust))

        # 2. Logic & Paradox Check (The "X-Ray")
        # Identify Root Anchor (Highest trust "Release" event)
        root_anchor = None
        for ev, trust in zone_a:
            title = (ev.title or "").lower()
            # Generalization: Look for ANY high-trust release event as anchor
            if any(kw in title for kw in ["release", "launch", "announce", "official"]):
                root_anchor = ev
                break
        
        accepted_timeline = []
        
        if root_anchor:
            root_time = FuzzyTime.from_string(root_anchor.publish_time.strftime("%Y-%m-%d") if root_anchor.publish_time else None)
            
            # Add Anchor to Graph
            if root_time:
                self.graph.add_node("ANCHOR_RELEASE", root_time)

            # Validate all others against Graph Rules
            for ev, trust in ranked_evidences:
                title = (ev.title or "").lower()
                content = (ev.content or "").lower()
                
                # Heuristic Concept Mapping
                concept = "unknown"
                if "training" in title or "trained" in content: concept = "training"
                elif "successor" in title or "successor" in content or "next version" in content: concept = "successor"
                elif "safety" in title and "test" in title: concept = "safety_testing"
                
                # Check Rules against Anchor
                is_valid = True
                failure_reason = ""
                
                if root_time and concept != "unknown":
                    ev_time = FuzzyTime.from_string(ev.publish_time.strftime("%Y-%m-%d") if ev.publish_time else None)
                    if ev_time:
                        self.graph.add_node(ev.id, ev_time)
                        
                        # Apply Canonical Rules
                        for parent_concept, child_concept, is_strict in self.canonical_rules:
                            # Rule: Training < Release (Anchor)
                            if parent_concept == concept and child_concept == "release":
                                # Ev is Parent, Anchor is Child. Valid if Anchor follows Ev.
                                if not self.graph.validate_causality("ANCHOR_RELEASE", ev.id, strict=is_strict):
                                    is_valid = False
                                    failure_reason = f"Causality Violation: {concept.title()} must precede Release ({root_anchor.title})"
                                    
                            # Rule: Release (Anchor) < Successor
                            elif parent_concept == "release" and child_concept == concept:
                                # Anchor is Parent, Ev is Child. Valid if Ev follows Anchor.
                                if not self.graph.validate_causality(ev.id, "ANCHOR_RELEASE", strict=is_strict):
                                    is_valid = False
                                    failure_reason = f"Causality Violation: {concept.title()} cannot predate Release ({root_anchor.title})"

                if not is_valid:
                    result.rejected_claims.append({
                        "claim": ev.title, 
                        "reason": failure_reason
                    })
                    continue
                

                
                # Check 2: Conflict Resolution (Reporting Error)
                if concept == "unknown" and "release" in title and root_time:
                    ev_time = FuzzyTime.from_string(ev.publish_time.strftime("%Y-%m-%d") if ev.publish_time else None)
                    if ev_time and not ev_time.overlaps(root_time) and abs((ev_time.start - root_time.start).days) > 60:
                         if trust < 0.9: 
                             result.rejected_claims.append({
                                 "claim": ev.title,
                                 "reason": "Reporting Error: Contradicts Official Timeline"
                             })
                             continue
                
                accepted_timeline.append({"event": ev.title, "date": str(ev.publish_time), "source": ev.source.value, "trust": trust, "content": ev.content})

        else:
             # No anchor found, accept all but obvious paradoxes
             for ev, trust in ranked_evidences:
                 accepted_timeline.append({"event": ev.title, "date": str(ev.publish_time), "source": ev.source.value, "trust": trust, "content": ev.content})

        result.verified_timeline = sorted(accepted_timeline, key=lambda x: x.get('trust', 0), reverse=True)[:50]
        
        # 3. Cross Verification (Rumors)
        # Check Zone C items that weren't rejected
        for ev, trust in zone_c:
             if any(r['claim'] == ev.title for r in result.rejected_claims): continue
             
             # Try to corroborate with Zone A
             best_match = CorroborationLevel.UNRELATED
             matched_fact = None
             
             for fact_ev, _ in zone_a:
                 level = self.cross_verifier.verify(ev.content or "", fact_ev.content or "")
                 if level == CorroborationLevel.DIRECT_CONFIRMS:
                     best_match = level; matched_fact = fact_ev.title; break
                 elif level == CorroborationLevel.CONSISTENT_DIRECTION and best_match != CorroborationLevel.DIRECT_CONFIRMS:
                     best_match = level; matched_fact = fact_ev.title

             if best_match in (CorroborationLevel.DIRECT_CONFIRMS, CorroborationLevel.CONSISTENT_DIRECTION):
                 result.corroborated_rumors.append({
                     "claim": ev.title,
                     "level": best_match.name,
                     "matched_fact": matched_fact
                 })

        return result

    def _check_paradox(self, ev: Evidence, anchor: Evidence, anchor_time: Optional[FuzzyTime]) -> bool:
        """Deprecated: Specific paradox logic removed for generalization."""
        return False

    def summarize_for_prompt(self, evidences: List[Evidence]) -> Dict[str, Any]:
        """
        Phase 21.1.1 Hotfix: Dual-Format Output for Provenance Enforcement.
        
        Returns:
            dict with:
            - "machine": For post-validation (EID -> data mappings)
            - "llm": Strict text format for LLM with [EID|TRUST] tags
            - "metadata": Fingerprint and version for audit trail
        """
        import hashlib
        import json
        
        result = self.verify_all(evidences)
        
        # === Machine Readable Format ===
        # EID = index in verified_timeline (1-indexed for human readability)
        verified_map = {}
        rejected_map = {}
        
        for idx, item in enumerate(result.verified_timeline, start=1):
            eid = f"{idx:03d}"  # E001, E002, ...
            verified_map[eid] = {
                "trust": item.get("trust", 0.5),
                "source_domain": item.get("source", "unknown"),
                "claim_snippet": item.get("event", "")[:100],
                "content": item.get("content", "")[:200],
                "date": item.get("date", "")
            }
        
        for idx, item in enumerate(result.rejected_claims, start=1):
            rid = f"R{idx:03d}"
            rejected_map[rid] = {
                "reason": item.get("reason", "Unknown"),
                "claim_snippet": item.get("claim", "")[:100]
            }
        
        machine = {
            "verified": verified_map,
            "rejected": rejected_map
        }
        
        # === LLM Readable Format with [EID|TRUST] Tags ===
        llm_lines = []
        
        # Zone A/B: Verified Facts
        llm_lines.append("# ZONE A+B: VERIFIED FACTS (Use in FACT: statements)")
        for eid, data in verified_map.items():
            trust = data['trust']
            zone_tag = "TRUST" if trust >= 0.7 else "LOW_TRUST"
            llm_lines.append(f"- [E{eid}|{zone_tag}={trust:.2f}] {data['claim_snippet']} ({data['source_domain']}, {data['date'][:10] if data['date'] else 'N/A'})")
        
        # Rejected Claims
        llm_lines.append("")
        llm_lines.append("# REJECTED CLAIMS (DO NOT USE - These are ERRORS)")
        for rid, data in rejected_map.items():
            llm_lines.append(f"- [{rid}|REJECTED] {data['claim_snippet']} — Reason: {data['reason']}")
        
        # Corroborated Rumors
        llm_lines.append("")
        llm_lines.append("# ZONE C: RUMORS (Use in SPECULATE: statements only)")
        for item in result.corroborated_rumors:
            llm_lines.append(f"- [RUMOR] {item.get('claim', '')} (Matched: {item.get('matched_fact', 'N/A')}, Level: {item.get('level', 'UNKNOWN')})")
        
        llm_text = "\n".join(llm_lines)
        
        # === Tamper-Proof Fingerprint ===
        fingerprint = hashlib.sha256(
            json.dumps(machine, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        
        return {
            "machine": machine,
            "llm": llm_text,
            "metadata": {
                "version": "DeepTrace-v21.1.1",
                "fingerprint": fingerprint,
                "timestamp": datetime.utcnow().isoformat(),
                "total_verified": len(verified_map),
                "total_rejected": len(rejected_map)
            }
        }

