"""
JARVIS Memory System
Persistent vector memory using ChromaDB.
Stores conversation history + facts, retrieves by semantic similarity.
"""

import time
import uuid
from typing import Optional
from core.config import Config


class MemoryStore:
    """
    Vector-based persistent memory.
    Uses ChromaDB + sentence-transformers for embeddings.
    Falls back to simple sqlite if chromadb is unavailable.
    """

    def __init__(self, config: Config):
        self.config = config
        self._client = None
        self._collection = None
        self._embedder = None
        self._fallback_entries = []

        self._init()

    def _init(self):
        try:
            self._init_chroma()
        except ImportError:
            print("[Memory] ChromaDB not found, using in-memory fallback")
            self._fallback_entries = []

    def _init_chroma(self):
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer

        db_path = str(self.config.get_memory_path())
        self._client = chromadb.PersistentClient(path=db_path)
        self._collection = self._client.get_or_create_collection(
            name=self.config.memory.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = SentenceTransformer(self.config.memory.embedding_model)
        print(f"[Memory] ChromaDB ready at {db_path} | {self._collection.count()} entries")

    # ------------------------------------------------------------------ #
    #  Core operations
    # ------------------------------------------------------------------ #

    def add(self, role: str, content: str, metadata: Optional[dict] = None):
        """Store a message in memory."""
        doc_id = str(uuid.uuid4())
        meta = {
            "role": role,
            "timestamp": time.time(),
            "ts_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if metadata:
            meta.update(metadata)

        if self._collection is not None:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[meta],
            )
        else:
            self._fallback_entries.append({"id": doc_id, "content": content, "meta": meta})

    def search(self, query: str, k: int = 5, role_filter: Optional[str] = None) -> list[str]:
        """
        Retrieve semantically similar memories.
        Returns list of content strings.
        """
        if self._collection is not None:
            where = {"role": role_filter} if role_filter else None
            results = self._collection.query(
                query_texts=[query],
                n_results=min(k, max(1, self._collection.count())),
                where=where,
            )
            docs = results.get("documents", [[]])[0]
            return docs
        else:
            # Naive substring fallback
            q = query.lower()
            matches = [
                e["content"] for e in self._fallback_entries
                if q in e["content"].lower()
            ]
            return matches[:k]

    def get_recent(self, n: int = 20) -> list[dict]:
        """Get the N most recent entries sorted by timestamp."""
        if self._collection is not None:
            results = self._collection.get(
                include=["documents", "metadatas"],
                limit=n,
            )
            entries = []
            for doc, meta in zip(results["documents"], results["metadatas"]):
                entries.append({"content": doc, **meta})
            entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return entries[:n]
        else:
            return sorted(
                [{"content": e["content"], **e["meta"]} for e in self._fallback_entries],
                key=lambda x: x.get("timestamp", 0),
                reverse=True,
            )[:n]

    def add_fact(self, fact: str):
        """Store a named fact (long-term knowledge)."""
        self.add(role="fact", content=fact, metadata={"type": "fact"})

    def delete_all(self):
        """Wipe all memory."""
        if self._collection is not None:
            self._client.delete_collection(self.config.memory.collection_name)
            self._init_chroma()
        else:
            self._fallback_entries.clear()
        print("[Memory] Memory wiped.")

    def count(self) -> int:
        if self._collection is not None:
            return self._collection.count()
        return len(self._fallback_entries)
