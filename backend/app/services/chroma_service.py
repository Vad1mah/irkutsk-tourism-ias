import asyncio
import logging

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_gigachat import GigaChatEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


class ChromaService:
    """Сервис для работы с векторной БД ChromaDB."""

    def __init__(self):
        self._client: chromadb.PersistentClient | None = None
        self._embeddings: GigaChatEmbeddings | None = None
        self._collection = None

    @property
    def is_initialized(self) -> bool:
        return self._client is not None and self._collection is not None

    def init(self) -> None:
        """Инициализировать клиент ChromaDB и embeddings."""
        if self._client is not None:
            return
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        credentials = settings.get_gigachat_credentials()
        if credentials:
            try:
                self._embeddings = GigaChatEmbeddings(
                    credentials=credentials,
                    verify_ssl_certs=False,
                )
            except Exception as e:
                logger.warning(f"GigaChat Embeddings init failed: {e}")
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB initialized, docs: {self._collection.count()}")

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """Добавить документы в коллекцию."""
        if not self._embeddings:
            return
        embeddings = self._embeddings.embed_documents(texts)
        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def get_collection_count(self) -> int:
        """Количество документов в коллекции."""
        if not self._collection:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return -1

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """Поиск релевантных документов с опциональной фильтрацией."""
        if not self._embeddings:
            return []
        query_embedding = self._embeddings.embed_query(query)
        query_params: dict = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_params["where"] = where
        try:
            results = self._collection.query(**query_params)
        except Exception as e:
            logger.warning(f"ChromaDB query with filter failed, retrying without: {e}")
            query_params.pop("where", None)
            results = self._collection.query(**query_params)

        docs = []
        if not results["ids"] or not results["ids"][0]:
            return docs

        for i in range(len(results["ids"][0])):
            docs.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return docs

    def add_documents_batch(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
        batch_size: int = 100,
    ) -> int:
        """Добавить документы батчами."""
        if not self._embeddings:
            return 0

        total_added = 0
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            try:
                embeddings = self._embeddings.embed_documents(batch_texts)
                self._collection.add(
                    documents=batch_texts,
                    embeddings=embeddings,
                    metadatas=batch_metadatas,
                    ids=batch_ids,
                )
                total_added += len(batch_ids)
            except Exception as e:
                logger.error(f"Error adding batch {i}: {e}")

        return total_added

    def delete_document(self, doc_id: str) -> bool:
        """Удалить документ по ID."""
        if not self._collection:
            return False
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False

    def clear_collection(self) -> None:
        """Очистить коллекцию."""
        if not self._collection:
            return
        try:
            all_ids = self._collection.get()["ids"]
            if all_ids:
                self._collection.delete(ids=all_ids)
            logger.info("Collection cleared")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")


    async def add_documents_async(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        await asyncio.to_thread(self.add_documents, texts, metadatas, ids)

    async def search_async(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        return await asyncio.to_thread(self.search, query, n_results, where)

    async def add_documents_batch_async(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
        batch_size: int = 100,
    ) -> int:
        return await asyncio.to_thread(
            self.add_documents_batch, texts, metadatas, ids, batch_size,
        )


chroma_service = ChromaService()
