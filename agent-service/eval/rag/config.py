"""RAG 检索测试通用配置。"""

from __future__ import annotations

import os
from pathlib import Path


def _load_env_file() -> None:
    candidate_files = [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for env_file in candidate_files:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
                continue
            key, value = stripped_line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

RAW_DIALOGUES_FILE = DATA_DIR / "rag_raw_dialogues_v1.csv"
QUESTIONS_FILE = DATA_DIR / "rag_questions_v1.csv"
GOLD_ANSWERS_FILE = DATA_DIR / "rag_gold_answers_v1.csv"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "pm_agent_rag_eval_v1")

DOUBAO_EMBEDDING_URL = os.getenv(
    "DOUBAO_EMBEDDING_URL",
    "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
)
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", os.getenv("ARK_API_KEY", ""))
DOUBAO_EMBEDDING_MODEL = os.getenv("DOUBAO_EMBEDDING_MODEL", "doubao-embedding-vision-251215")
DOUBAO_EMBEDDING_INSTRUCTIONS = os.getenv(
    "DOUBAO_EMBEDDING_INSTRUCTIONS",
    "Target_modality: text.\nInstruction: Represent the text for retrieval.\nQuery:",
)
DOUBAO_EMBEDDING_DIMENSIONS = int(os.getenv("DOUBAO_EMBEDDING_DIMENSIONS", "1024"))
DOUBAO_SPARSE_EMBEDDING_ENABLED = os.getenv("DOUBAO_SPARSE_EMBEDDING_ENABLED", "false").lower() == "true"

DEFAULT_VECTOR_SIZE = int(os.getenv("RAG_VECTOR_SIZE", "0"))
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
