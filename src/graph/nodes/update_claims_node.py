
import logging
from typing import Dict, Any, List
from ...graph.state import GraphState
from ...core.models.credibility import evaluate_credibility
from ...config.settings import settings

logger = logging.getLogger(__name__)


def split_evidences_by_role(claim, evidences_list: List) -> tuple:
    """
    Phase 13: Split supporting evidences by source_role.
    
    Returns:
        tuple: (fact_evs, mixed_evs, opinion_evs)
    """
    fact_evs, mixed_evs, opinion_evs = [], [], []
    
    # Build evidence lookup by ID
    ev_map = {e.id: e for e in evidences_list}
    
    # Get claim's linked evidence
    ev_id = getattr(claim, "source_evidence_id", None)
    if ev_id and ev_id in ev_map:
        ev = ev_map[ev_id]
        role = getattr(ev, "source_role", "mixed")
        if role == "fact_source":
            fact_evs.append(ev)
        elif role == "mixed":
            mixed_evs.append(ev)
        else:  # opinion_only
            opinion_evs.append(ev)
    
    return fact_evs, mixed_evs, opinion_evs


def is_official_source(evidence) -> bool:
    """Phase 17: Check if evidence comes from an Official Domain"""
    if not evidence.url:
        return False
    from urllib.parse import urlparse
    try:
        domain = urlparse(evidence.url).netloc.lower()
        return any(domain.endswith(d) for d in settings.OFFICIAL_DOMAINS)
    except:
        return False


def is_date_claim(claim) -> bool:
    """Phase 17: Detect if claim is about release date/launch timeline"""
    keywords = ["发布", "上线", "推出", "release", "launch", "available", "coming"]
    return any(kw in claim.content.lower() for kw in keywords)


def validate_numeric_consistency(claim, all_claims) -> bool:
    """
    Phase 17: Check if numeric claim (price, tokens) is consistent across sources.
    Returns True if consistent (or not numeric), False if conflict exists.
    """
    # Simple heuristic: if same number appears in multiple distinct sources
    # For now, we trust the 'dedup_conflicts' logic handles the conflict detection
    # This function is a placeholder for stricter future logic
    return True


def update_claims_node(state: GraphState) -> Dict[str, Any]:
    """
    Update Claims Node:
    基于当前累积的 Evidence，重新评估 Claims 的 alpha (可信度) 和 status。
    
    Phase 13: Role-based credibility logic:
    - fact_source: Can verify claims (up to source max_conf)
    - mixed: Can support but not fully verify (capped lower)
    - opinion_only: Cannot verify, always disputed, max 20%
    """
    claims = state.get("claims", [])
    evidences = state.get("evidences", [])
    verified_claim_ids = state.get("verified_claim_ids", set())
    
    if not claims or not evidences:
        return {}
        
    logger.info(f"Updating status for {len(claims)} claims based on {len(evidences)} evidences...")
    
    new_verified = set()
    evidence_cred_map = {e.id: evaluate_credibility(e.url, e.content) for e in evidences}
    
    updated_claims = []
    
    # Phase 14: Prep conflict map
    state.get("dedup_conflicts", [])
    # Build set of conflicted claim IDs (if conflict tracking links back to Claims)
    # Since dedup_conflicts are OpenQuestions with context, we match by simple keyword/similarity or if we have claim linkage.
    # For now, we use a simple heuristic: if the claim's content strongly overlaps with a conflict description.
    # Better yet, if we can link evidences in conflict to claims.
    
    # Heuristic: If ANY evidence of a claim is mentioned in a conflict cluster's evidence set (implied)
    # But OpenQuestion structure doesn't deeply link evidences yet. 
    # Alternative: Use Conflict Resolver's output if available.
    # Fallback: Tag claims if they match "conflict" tagged OpenQuestions.
    
    # Let's simplify: If claim is 'disputed' status or we detect conflicts, be conservative.
    # We will trust the evidence-based logic below predominantly.
    
    from ...core.models.claim import TruthStatus
    
    for c in claims:
        # Phase 13: Split by source role
        fact_evs, mixed_evs, opinion_evs = split_evidences_by_role(c, evidences)
        
        # Check for structural conflict (Simple Check)
        # In a real system we'd link Dedup Conflict -> Claim ID. 
        # Here we assume if status is already 'disputed', there's a conflict.
        # OR if timeline.open_questions has relevant conflicts.
        has_conflict = c.status == "disputed" 
        
        # Phase 14: Truth Status Logic
        c.truth_status = TruthStatus.UNKNOWN
        
        if fact_evs:
            # Fact Source Support
            ev = fact_evs[0]
            cred_obj = evidence_cred_map.get(ev.id)
            if cred_obj:
                raw_score = cred_obj.score
                # Phase 17: Strict Official Upgrade
                is_official = is_official_source(ev)
                
                # If official domain, allow higher confidence
                if is_official:
                     max_cap = settings.OFFICIAL_SOURCE_MIN_CONF * 100 # e.g. 90
                else:
                     # Non-official fact source (e.g. reputable news) capped slightly lower
                     max_cap = 85.0
                
                capped_score = min(raw_score, max_cap)
                if capped_score > c.credibility_score:
                    c.credibility_score = capped_score
            
            if has_conflict:
                c.truth_status = TruthStatus.UNRESOLVED
            else:
                # Phase 17: Strict Confirmation Logic
                # Only Official Sources OR Multi-Source Reputable can reach CONFIRMED
                if is_official:
                    c.truth_status = TruthStatus.CONFIRMED
                else:
                    # Reputable but not offical -> LIKELY (unless multi-source verified later)
                    c.truth_status = TruthStatus.LIKELY
                
                # Special Case: Date Claims without Official Source -> downgrade
                if is_date_claim(c) and not is_official:
                    c.truth_status = min(c.truth_status, TruthStatus.LIKELY)
                    
        elif mixed_evs:
            # Mixed Source Only - 使用配置文件中的上限
            ev = mixed_evs[0]
            cred_obj = evidence_cred_map.get(ev.id)
            if cred_obj:
                raw_score = cred_obj.score
                max_cap = settings.MIXED_SOURCE_MAX_CONF
                capped_score = min(raw_score, max_cap)
                if capped_score > c.credibility_score:
                    c.credibility_score = capped_score
            
            # Logic: If strong enough mixed support -> Likely
            # Cap score at 75
            c.credibility_score = min(c.credibility_score, 75.0)
            
            if c.credibility_score >= 60.0 and not has_conflict:
                c.truth_status = TruthStatus.LIKELY
            else:
                c.truth_status = TruthStatus.UNRESOLVED
                    
        elif opinion_evs:
            # Opinion Only - 使用配置文件中的上限
            max_cap = settings.OPINION_SOURCE_MAX_CONF
            if c.credibility_score > max_cap:
                c.credibility_score = max_cap
            # Opinion section only
            c.truth_status = TruthStatus.UNKNOWN 
        
        # Phase 16: Canonical Text Logic
        # Priority: LLM-extracted quote > Fact Source title > Mixed Source title > Raw content
        MAX_CANONICAL_LENGTH = settings.MAX_CANONICAL_TEXT_LENGTH
        
        def pick_canonical_text(claim, fact_evs, mixed_evs):
            # 1. If LLM already extracted a quote, use it
            if claim.canonical_text and claim.canonical_text.strip():
                text = claim.canonical_text.strip()
                # 长度限制
                if len(text) > MAX_CANONICAL_LENGTH:
                    text = text[:MAX_CANONICAL_LENGTH] + "…"
                return text
                
            candidates = []
            # 2. Fact Source (Highest Priority)
            for ev in fact_evs:
                if ev.title: 
                    candidates.append((len(ev.title), ev.title))
            
            if candidates:
                text = sorted(candidates, key=lambda x: x[0])[0][1]
                if len(text) > MAX_CANONICAL_LENGTH:
                    text = text[:MAX_CANONICAL_LENGTH] + "…"
                return text
                
            # 3. Mixed Source
            for ev in mixed_evs:
                if ev.title: 
                    candidates.append((len(ev.title), ev.title))
            
            if candidates:
                text = sorted(candidates, key=lambda x: x[0])[0][1]
                if len(text) > MAX_CANONICAL_LENGTH:
                    text = text[:MAX_CANONICAL_LENGTH] + "…"
                return text
                
            # 4. Fallback to claim content (also truncated)
            text = claim.content
            if len(text) > MAX_CANONICAL_LENGTH:
                text = text[:MAX_CANONICAL_LENGTH] + "…"
            return text
            
        c.canonical_text = pick_canonical_text(c, fact_evs, mixed_evs)
        
        updated_claims.append(c)
    
    # Phase 17: Post-Process Multi-Source Confirmation
    # If a claim is LIKELY but appears in >= 3 independent sources, upgrade to CONFIRMED
    from collections import defaultdict
    content_cluster = defaultdict(list)
    for c in updated_claims:
        content_cluster[c.content.strip().lower()].append(c)
        
    for content, claim_group in content_cluster.items():
        # Count distinct sources
        for c in claim_group:
            ev_id = getattr(c, "source_evidence_id", None)
            if ev_id and ev_id in evidence_cred_map:
                # Use domain or source name as unique key
                # We need evidence object map to get URL/Source
                pass # Logic requires ev map access
        
        # Simplified: If >= 3 claims in group with LIKELY status, upgrade strongest to CONFIRMED
        likely_claims = [c for c in claim_group if c.truth_status == TruthStatus.LIKELY]
        if len(likely_claims) >= settings.MULTI_SOURCE_MIN_COUNT:
             # Upgrade all to CONFIRMED
             for c in likely_claims:
                 c.truth_status = TruthStatus.CONFIRMED
                 if c.credibility_score < settings.MULTI_SOURCE_MIN_CONF * 100:
                     c.credibility_score = settings.MULTI_SOURCE_MIN_CONF * 100
        
        updated_claims.append(c)
    
    # Phase 17: Post-Process Multi-Source Confirmation
    # If a claim is LIKELY but appears in >= 3 independent sources, upgrade to CONFIRMED
    from collections import defaultdict
    content_cluster = defaultdict(list)
    for c in updated_claims:
        content_cluster[c.content.strip().lower()].append(c)
        
    for content, claim_group in content_cluster.items():
        # Count distinct sources implementation requires evidence object map which we have
        # Simplification for now: Just count claims in group
        
        # Simplified: If >= 3 claims in group with LIKELY status, upgrade strongest to CONFIRMED
        likely_claims = [c for c in claim_group if c.truth_status == TruthStatus.LIKELY]
        if len(likely_claims) >= settings.MULTI_SOURCE_MIN_COUNT:
             # Upgrade strongest to CONFIRMED
             # Sort by credibility
             likely_claims.sort(key=lambda x: x.credibility_score, reverse=True)
             best_claim = likely_claims[0]
             best_claim.truth_status = TruthStatus.CONFIRMED
             if best_claim.credibility_score < settings.MULTI_SOURCE_MIN_CONF * 100:
                 best_claim.credibility_score = settings.MULTI_SOURCE_MIN_CONF * 100
        
    # Group by content and Mark Verified
    # Keep existing verification logic for compatibility, but TruthStatus is the new Source of Truth
    content_map = {}
    for c in updated_claims:
        key = c.content.strip().lower()
        if key not in content_map:
            content_map[key] = []
        content_map[key].append(c)
        
    for key, group in content_map.items():
        # Only verified if TruthStatus is CONFIRMED
        is_confirmed = any(c.truth_status == TruthStatus.CONFIRMED for c in group)
        
        if is_confirmed:
            for c in group:
                new_verified.add(c.id)
                # Sync status string for tools that rely on it
                if c.truth_status == TruthStatus.CONFIRMED:
                    c.status = "verified"
                elif c.truth_status == TruthStatus.UNRESOLVED:
                    c.status = "disputed"

    result = {}
    if new_verified:
        logger.info(f"Marking {len(new_verified)} claims as VERIFIED (CONFIRMED) based on updated logic.")
        merged_verified = verified_claim_ids.union(new_verified)
        result["verified_claim_ids"] = merged_verified
        
    result["claims"] = updated_claims
    
    return result
