"""输入召回的集中预算与请求级限制。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalPolicy:
    """集中保存与召回质量、成本和安全相关的固定边界。"""

    pre_retrieval_limit: int = 5
    max_query_chars: int = 2000
    max_result_limit: int = 8
    min_detail_candidates: int = 8
    max_detail_candidates: int = 16
    max_raw_files: int = 2
    max_raw_evidence_bytes: int = 12 * 1024
    max_unique_retrievals: int = 3

    def detail_candidate_limit(self, result_limit: int) -> int:
        return min(
            self.max_detail_candidates,
            max(self.min_detail_candidates, result_limit * 2),
        )


DEFAULT_RETRIEVAL_POLICY = RetrievalPolicy()
