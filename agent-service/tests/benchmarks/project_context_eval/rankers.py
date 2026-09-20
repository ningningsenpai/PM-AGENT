"""A0～A3 检索策略及可复现评分实现。"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.input_context.normalization import create_default_normalization_service
from app.input_context.normalization.preprocessing import TextNormalizer
from app.input_context.normalization.query import QueryNormalization, QueryNormalizer
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlanner
from app.input_context.retrieval.policy import DEFAULT_RETRIEVAL_POLICY
from app.input_context.retrieval.ranking import RetrievalRanker
from app.input_context.retrieval.schemas import RetrievalQuery
from app.llm.structured import StructuredJsonGenerator, StructuredOutputValidationError
from app.llm.telemetry import capture_calls
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    path: str
    title: str
    content: str
    heading: str
    kind: str
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RankedDocument:
    path: str
    score: float
    explanation: dict[str, float | int | str]


def tokenize(text: str) -> tuple[str, ...]:
    lowered = text.casefold()
    ascii_terms = re.findall(r"[a-z0-9_.$#:/-]{2,}", lowered)
    chinese_sequences = re.findall(r"[\u3400-\u9fff]+", lowered)
    chinese_terms: list[str] = []
    for sequence in chinese_sequences:
        chinese_terms.extend(sequence)
        chinese_terms.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
        chinese_terms.extend(sequence[index : index + 3] for index in range(len(sequence) - 2))
    return tuple(ascii_terms + chinese_terms)


def build_corpus(files: dict[str, str]) -> list[CorpusDocument]:
    documents = []
    for path, content in sorted(files.items()):
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        heading = next((line.lstrip("# /") for line in lines if line.startswith("#")), "")
        suffix = PurePosixPath(path).suffix.lower().lstrip(".") or "text"
        documents.append(
            CorpusDocument(
                path=path,
                title=PurePosixPath(path).name,
                content=content,
                heading=heading,
                kind=suffix,
                tokens=tokenize(content),
            )
        )
    return documents


def rank_a0(
    query: str,
    corpus: list[CorpusDocument],
    limit: int = 10,
    *,
    variant: str = "full",
) -> list[RankedDocument]:
    """复用生产归一化、规划和字段评分规则的离线适配器。"""
    normalizer = QueryNormalizer(create_default_normalization_service())
    normalization = normalizer.normalize(query, project_id=0)
    if variant == "no_query_normalization":
        normalization = QueryNormalization(
            raw_text=query,
            cleaned_text=TextNormalizer().normalize_for_matching(query),
            result=None,
        )
    plan = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY).build(
        RetrievalQuery(query=query, limit=min(limit, 8), evidence_level="source"),
        normalization,
    )
    ranker = RetrievalRanker()
    candidates = []
    for index, document in enumerate(corpus):
        candidate = RetrievalCandidate(
            source_type="file_detail",
            source_id=f"offline-{index}",
            title=document.title,
            summary=document.heading or document.content[:240],
            high_fields=[document.path, document.title, document.heading],
            medium_fields=[document.content],
            low_fields=[document.kind],
            logical_path=document.path,
        )
        candidate.score = ranker.score(candidate, plan)
        if variant == "no_phrase_bonus" and candidate.score_breakdown:
            candidate.score = round(
                candidate.score - candidate.score_breakdown.exact_phrase,
                4,
            )
        if variant == "no_field_weights" and candidate.score_breakdown:
            breakdown = candidate.score_breakdown
            candidate.score = round(
                breakdown.high_fields / 6
                + breakdown.medium_fields / 3
                + breakdown.low_fields
                + breakdown.term_source_weight / 3
                + breakdown.exact_phrase
                + breakdown.importance,
                4,
            )
        if candidate.score > 0:
            candidates.append(candidate)
    ranked = ranker.sort(candidates)[:limit]
    return [
        RankedDocument(
            path=item.logical_path or "",
            score=item.score,
            explanation=(
                item.score_breakdown.__dict__
                if hasattr(item.score_breakdown, "__dict__")
                else {name: getattr(item.score_breakdown, name) for name in item.score_breakdown.__slots__}
            ) if item.score_breakdown else {},
        )
        for item in ranked
    ]


class BM25F:
    """无外部依赖的 BM25F，字段权重与长度归一化显式固定。"""

    FIELD_WEIGHTS: ClassVar[dict[str, float]] = {
        "path": 3.0,
        "title": 3.0,
        "heading": 2.0,
        "content": 1.0,
    }

    def __init__(
        self,
        corpus: list[CorpusDocument],
        *,
        k1: float = 1.2,
        b: float = 0.75,
        field_weights: dict[str, float] | None = None,
    ):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.field_weights = field_weights or self.FIELD_WEIGHTS
        self.fields = {
            document.path: {
                "path": tokenize(document.path),
                "title": tokenize(document.title),
                "heading": tokenize(document.heading),
                "content": document.tokens,
            }
            for document in corpus
        }
        self.average_lengths = {
            field: max(1.0, sum(len(values[field]) for values in self.fields.values()) / max(1, len(corpus)))
            for field in self.field_weights
        }
        self.document_frequency: Counter[str] = Counter()
        for values in self.fields.values():
            terms = set().union(*(set(values[field]) for field in self.field_weights))
            self.document_frequency.update(terms)

    def rank(self, query: str, limit: int = 10) -> list[RankedDocument]:
        terms = Counter(tokenize(query))
        scores: list[RankedDocument] = []
        size = len(self.corpus)
        for document in self.corpus:
            field_values = self.fields[document.path]
            field_counters = {field: Counter(values) for field, values in field_values.items()}
            score = 0.0
            matched = 0
            for term, query_frequency in terms.items():
                frequency = 0.0
                for field, weight in self.field_weights.items():
                    length = len(field_values[field])
                    normalization = 1 - self.b + self.b * length / self.average_lengths[field]
                    frequency += weight * field_counters[field][term] / normalization
                if frequency <= 0:
                    continue
                matched += 1
                df = self.document_frequency[term]
                idf = math.log(1 + (size - df + 0.5) / (df + 0.5))
                score += query_frequency * idf * (frequency * (self.k1 + 1)) / (frequency + self.k1)
            if score > 0:
                scores.append(
                    RankedDocument(
                        path=document.path,
                        score=round(score, 6),
                        explanation={"matchedTerms": matched, "queryTerms": len(terms)},
                    )
                )
        return sorted(scores, key=lambda item: (-item.score, item.path))[:limit]


def reciprocal_rank_fusion(
    rankings: list[list[RankedDocument]],
    *,
    limit: int = 10,
    k: int = 60,
) -> list[RankedDocument]:
    scores: defaultdict[str, float] = defaultdict(float)
    sources: defaultdict[str, list[str]] = defaultdict(list)
    for source_index, ranking in enumerate(rankings):
        for rank, item in enumerate(ranking, 1):
            scores[item.path] += 1 / (k + rank)
            sources[item.path].append(f"r{source_index + 1}:{rank}")
    return [
        RankedDocument(path=path, score=round(score, 8), explanation={"ranks": ",".join(sources[path])})
        for path, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


class RerankItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    relevance: int = Field(ge=0, le=3)
    reason: str = Field(min_length=1, max_length=200)


class RerankOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RerankItem] = Field(max_length=10)


def normalize_rerank_json(raw: str) -> str:
    """只剥离条目中的冗余字段，不替模型补造排序结果。"""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return raw
    normalized_items = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            return raw
        normalized_items.append(
            {
                key: item[key]
                for key in ("path", "relevance", "reason")
                if key in item
            }
        )
    return json.dumps({"items": normalized_items}, ensure_ascii=False)


async def rank_a3(
    query: str,
    corpus: list[CorpusDocument],
    candidates: list[RankedDocument],
    generator: StructuredJsonGenerator,
    *,
    limit: int = 10,
    events: list[dict] | None = None,
) -> tuple[list[RankedDocument], list[dict]]:
    document_map = {item.path: item for item in corpus}
    blocks = []
    for item in candidates[:10]:
        document = document_map[item.path]
        sanitized = sanitize_sensitive_content(document.content[:5000]).text
        blocks.append(f"路径：{item.path}\n内容：\n{sanitized}")
    prompt = (
        "你是项目文件检索重排器。根据问题对候选文件按相关性评分："
        "3=直接且充分证据，2=重要补充证据，1=弱相关，0=无关。"
        "只能返回给定路径，每个路径恰好一次。"
        "顶层必须且只能包含 items；items 每项必须且只能包含 path、relevance、reason。"
        "输出示例：{\"items\":[{\"path\":\"候选中的原路径\","
        "\"relevance\":3,\"reason\":\"与问题直接相关\"}]}。"
        f"必须满足以下 JSON Schema：{RerankOutput.model_json_schema()}。\n\n"
        f"问题：{query}\n\n候选：\n" + "\n\n---\n\n".join(blocks)
    )
    captured_events = events if events is not None else []
    with capture_calls(captured_events):
        for attempt in range(2):
            try:
                output = await generator.generate(
                    prompt,
                    RerankOutput,
                    normalize_json=normalize_rerank_json,
                )
                break
            except StructuredOutputValidationError:
                if attempt:
                    raise
                prompt += (
                    "\n\n上次输出字段不符合约定。请只输出一个 items 对象，"
                    "不得输出 type、paths 或以文件路径作为对象键；每个候选路径恰好出现一次。"
                )
    allowed = {item.path for item in candidates[:10]}
    received = {item.path for item in output.items}
    if received != allowed or len(output.items) != len(allowed):
        raise ValueError("A3 重排输出路径集合与输入候选不一致")
    prior_rank = {item.path: rank for rank, item in enumerate(candidates, 1)}
    ranked = sorted(output.items, key=lambda item: (-item.relevance, prior_rank[item.path], item.path))
    return (
        [
            RankedDocument(
                path=item.path,
                score=float(item.relevance),
                explanation={"reason": item.reason, "priorRank": prior_rank[item.path]},
            )
            for item in ranked[:limit]
        ],
        captured_events,
    )
