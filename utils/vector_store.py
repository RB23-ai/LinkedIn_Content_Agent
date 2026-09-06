"""
utils/vector_store.py
----------------------
Company-isolated semantic storage using ChromaDB. Each workspace gets
its own COLLECTION (not just a metadata filter), so there is zero chance
of a query in workspace A leaking embeddings/content from workspace B --
even a buggy filter can't cross collections.
"""

import os
import chromadb
from chromadb.utils import embedding_functions


class VectorStore:
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
        os.makedirs(self.persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        # Local, free sentence-transformers embedding model -- no API key needed.
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

    def _collection_name(self, workspace_id: int) -> str:
        return f"workspace_{workspace_id}_posts"

    def _get_collection(self, workspace_id: int):
        return self.client.get_or_create_collection(
            name=self._collection_name(workspace_id),
            embedding_function=self.embed_fn,
        )

    def add_posts(self, workspace_id: int, posts: list[dict]):
        """
        posts: list of {"id": str, "text": str, "metadata": dict}
        `metadata` values must be str/int/float/bool (Chroma requirement).
        """
        if not posts:
            return
        collection = self._get_collection(workspace_id)
        collection.upsert(
            ids=[p["id"] for p in posts],
            documents=[p["text"] for p in posts],
            metadatas=[self._clean_metadata(p.get("metadata", {})) for p in posts],
        )

    @staticmethod
    def _clean_metadata(meta: dict) -> dict:
        # Chroma rejects None / nested dict values -- coerce to safe scalars.
        clean = {}
        for k, v in meta.items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                clean[k] = v
            else:
                clean[k] = str(v)
        return clean

    def query_similar(self, workspace_id: int, query_text: str, top_k: int = 5,
                       where: dict = None) -> list[dict]:
        collection = self._get_collection(workspace_id)
        count = collection.count()
        if count == 0:
            return []
        results = collection.query(
            query_texts=[query_text],
            n_results=min(top_k, count),
            where=where,
        )
        out = []
        for i in range(len(results["ids"][0])):
            out.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return out

    def get_top_competitor_posts(self, workspace_id: int, competitor_name: str = None,
                                  top_k: int = 5) -> list[dict]:
        where = {"source": "competitor"}
        if competitor_name:
            where = {"$and": [{"source": "competitor"}, {"competitor_name": competitor_name}]}
        collection = self._get_collection(workspace_id)
        if collection.count() == 0:
            return []
        results = collection.get(where=where, limit=top_k)
        out = []
        for i in range(len(results["ids"])):
            out.append({
                "id": results["ids"][i],
                "text": results["documents"][i],
                "metadata": results["metadatas"][i],
            })
        # Sort by likes desc if present
        out.sort(key=lambda p: p["metadata"].get("likes", 0), reverse=True)
        return out

    def delete_workspace_data(self, workspace_id: int):
        """Full teardown when a company cancels their subscription."""
        try:
            self.client.delete_collection(self._collection_name(workspace_id))
        except Exception:
            pass
