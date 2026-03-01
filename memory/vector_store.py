"""
memory/vector_store.py — ChromaDB-based vector store.
Handles upsert, query, and delete for emails, documents, meeting notes.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional
from config import get_settings

settings = get_settings()


class VectorStore:
    """Thin wrapper around ChromaDB for the assistant's memory."""

    COLLECTIONS = ["emails", "documents", "meeting_notes", "style_samples"]

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # Pre-create collections
        for name in self.COLLECTIONS:
            self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )

    def _col(self, collection: str):
        return self.client.get_or_create_collection(collection)

    def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: Optional[dict] = None,
    ):
        """Add or update a document in the vector store."""
        self.client.get_or_create_collection(collection).upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def query(
        self,
        collection: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Semantic search with optional metadata filter.
        Returns list of {id, text, metadata, distance}.
        """
        col = self._col(collection)
        kwargs = dict(query_texts=[query_text], n_results=min(n_results, col.count() or 1))
        if where:
            kwargs["where"] = where
        try:
            result = col.query(**kwargs)
            output = []
            for i, doc_id in enumerate(result["ids"][0]):
                output.append({
                    "id": doc_id,
                    "text": result["documents"][0][i],
                    "metadata": result["metadatas"][0][i] if result["metadatas"] else {},
                    "distance": result["distances"][0][i] if result.get("distances") else None,
                })
            return output
        except Exception:
            return []

    def delete(self, collection: str, doc_id: str):
        self._col(collection).delete(ids=[doc_id])

    def count(self, collection: str) -> int:
        return self._col(collection).count()


# Singleton
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
