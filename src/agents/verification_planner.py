from typing import List
from ..core.models.claim import Claim
from ..config.settings import settings
from ..llm.factory import init_json_llm
from .prompts import VERIFICATION_PLANNER_SYSTEM_PROMPT
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

async def generate_verification_queries_for_claim(claim: Claim) -> List[str]:
    """
    为单个声明生成验证查询。
    """
    llm = init_json_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", VERIFICATION_PLANNER_SYSTEM_PROMPT),
        ("user", "{input}")
    ])
    
    try:
        chain = prompt | llm | JsonOutputParser()
        result = await chain.ainvoke({"input": f"待验证声明：{claim.content}\n\n请生成验证查询。"})
        return result.get("queries", [])
    except Exception as e:
        print(f"[Verification] Query gen failed for '{claim.content[:20]}...': {e}")
        # Fallback queries
        return [f'"{claim.content}" 真实性', f'"{claim.content}" 辟谣', f'"{claim.content}" 官方']

async def plan_verification(claims: List[Claim]) -> List[str]:
    """
    选择「重要且低可信」的声明，生成针对性的验证查询。
    触发条件：
      - importance >= settings.CLAIM_IMPORTANCE_THRESHOLD
      - credibility_score < settings.VERIFICATION_CRED_THRESHOLD
      - status == "unverified"
    """
    verification_queries: List[str] = []
    
    print(f"[Verification] Checking {len(claims)} claims for verification needed...")
    
    for claim in claims:
        # Check thresholds
        is_important = claim.importance >= settings.CLAIM_IMPORTANCE_THRESHOLD
        is_low_cred = claim.credibility_score < settings.VERIFICATION_CRED_THRESHOLD
        is_unverified = claim.status == "unverified"
        
        if is_important and is_low_cred and is_unverified:
            print(f"[Verification] Triggering verification for: {claim.content[:30]}... (Imp={claim.importance}, Cred={claim.credibility_score})")
            
            # Generate queries
            qs = await generate_verification_queries_for_claim(claim)
            claim.verification_queries = qs
            verification_queries.extend(qs)
            
            # Update status to avoid re-verification in same loop (though graph state is immutable-ish, 
            # we modify the object in place here which is risky if state is deep copied. 
            # Ideally we should return updated claims too, but workflow handles state updates.
            # actually, we need to update the claim objects in the state to mark them as 'verification_pending' or similar?
            # For now, we just generate queries. The DFS loop will fetch evidence. 
            # The next extraction phase will extract new claims or update existing ones?
            # Actually Phase 9 logic says: [Verification_Planner] -> [DFS_Verify_Fetch] -> [Extract] -> [Update_Claims].
            # We need a node to update claims? 
            # Or just let the Planner generate queries and the Fetch Node execute them.
            # The 'status' update should happen somewhere. 
            # Let's set it to 'checking' if we could, but here we just return queries.
            pass
            
    print(f"[Verification] Generated {len(verification_queries)} queries.")
    return verification_queries
