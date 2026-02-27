"""
RAG retriever - Chroma vector DB cho K8s command examples.
"""
import json
import os
from pathlib import Path

from config import CHROMA_PATH, RAG_TOP_K, RAG_ENABLED

_COLLECTION_NAME = "k8s_commands"
_client = None


def _get_client():
    global _client
    if _client is None:
        import chromadb
        from chromadb.config import Settings
        Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_embedding_function():
    from chromadb.utils import embedding_functions
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def _get_collection():
    client = _get_client()
    ef = _get_embedding_function()
    try:
        coll = client.get_collection(name=_COLLECTION_NAME, embedding_function=ef)
    except Exception:
        coll = client.create_collection(
            name=_COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        _seed_collection(coll)
    return coll


def _seed_collection(coll):
    """Load seed examples from data/examples.json"""
    examples_path = Path(__file__).parent.parent / "data" / "examples.json"
    if not examples_path.exists():
        return
    with open(examples_path, encoding="utf-8") as f:
        examples = json.load(f)
    if not examples:
        return
    ids = []
    documents = []
    metadatas = []
    for i, ex in enumerate(examples):
        ids.append(f"seed_{i}")
        documents.append(ex["command"])
        metadatas.append({"intent": json.dumps(ex["intent"])})
    coll.add(ids=ids, documents=documents, metadatas=metadatas)


def get_retriever():
    if not RAG_ENABLED:
        return None
    try:
        return _get_collection()
    except Exception:
        return None


def retrieve_examples(query: str, top_k: int | None = None) -> list[dict]:
    """Retrieve similar command examples for RAG context."""
    coll = get_retriever()
    if coll is None:
        return []
    k = top_k or RAG_TOP_K
    try:
        n = coll.count()
        if n == 0:
            return []
        results = coll.query(query_texts=[query], n_results=min(k, n))
        if not results or not results["documents"] or not results["documents"][0]:
            return []
        out = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            intent = json.loads(meta.get("intent", "{}"))
            out.append({"command": doc, "intent": intent})
        return out
    except Exception:
        return []


def add_example(command: str, intent: dict) -> bool:
    """Add new example to vector DB (for learning from feedback)."""
    coll = get_retriever()
    if coll is None:
        return False
    try:
        import uuid
        coll.add(
            ids=[str(uuid.uuid4())],
            documents=[command],
            metadatas=[{"intent": json.dumps(intent)}],
        )
        return True
    except Exception:
        return False
