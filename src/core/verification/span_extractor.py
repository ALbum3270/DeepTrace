"""
Span Extractor Module.
Splits evidence content into immutable chunks with hash IDs.
"""
import re
import hashlib
from typing import List
from ..models.evidence import Evidence
from ..models.span import EvidenceSpan

class SpanExtractor:
    """
    Extracts citation-ready spans from Evidence.
    """
    
    def extract_spans(self, evidence: Evidence) -> List[EvidenceSpan]:
        """
        Splits evidence content into granular spans.
        ID Format: [Ev{id}#c{index}@{hash}]
        """
        text = evidence.content
        if not text:
            return []
            
        # 1. Split into chunks (Sentences or logical blocks)
        # Regex split by .!? followed by space or newline
        # Also clean up whitespace
        chunks = re.split(r'(?<=[.!?])\s+', text)
        
        spans = []
        index = 0
        current_pos = 0
        
        for chunk in chunks:
            clean_chunk = chunk.strip()
            if len(clean_chunk) < 5: # Skip very short noise
                continue
                
            # 2. Compute Hash (Immutable Identity)
            # Use SHA256 of normalized text (lower case, no whitespace)
            normalized = re.sub(r'\s+', '', clean_chunk).lower()
            full_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
            short_hash = full_hash[:6] # First 6 chars
            
            # 3. Create Span Object
            span = EvidenceSpan(
                evidence_id=evidence.id,
                chunk_index=index,
                content=clean_chunk,
                content_hash=short_hash,
                start_char=current_pos, # Approx pos
                end_char=current_pos + len(clean_chunk)
            )
            spans.append(span)
            
            index += 1
            current_pos += len(chunk) + 1 # Update pos
            
        return spans
