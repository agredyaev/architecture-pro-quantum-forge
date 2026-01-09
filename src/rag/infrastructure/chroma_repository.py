"""Repository interfaces and implementations for vector storage."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import chromadb

from src.core import get_logger, settings

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection

logger = get_logger(__name__)


class VectorRepository(ABC):
    """Abstract interface for vector storage operations."""

    @abstractmethod
    def add_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Add a batch of vectors to the repository."""

    @abstractmethod
    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        """Query the repository for similar vectors."""

    @abstractmethod
    def delete_by_source(self, sources: list[str]) -> None:
        """Delete all vectors from the given source files."""

    @abstractmethod
    def get_all_sources(self) -> dict[str, str]:
        """Get mapping of source -> file_hash for all indexed documents."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of vectors in the repository."""


class ChromaRepository(VectorRepository):
    """ChromaDB implementation of VectorRepository."""

    def __init__(self, persist_path: str) -> None:
        logger.info("Initializing ChromaDB at %s", persist_path)
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection: Collection = self.client.get_or_create_collection(
            name=settings.vector_db.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self.collection.add(
            ids=ids,
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=documents,
            metadatas=metadatas,  # type: ignore[arg-type]
        )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )  # type: ignore[return-value]

    def delete_by_source(self, sources: list[str]) -> None:
        if sources:
            self.collection.delete(where={"source": {"$in": sources}})

    def get_all_sources(self) -> dict[str, str]:
        """Get mapping of source -> file_hash for all indexed documents."""
        result = self.collection.get(include=["metadatas"])
        sources: dict[str, str] = {}
        if result["metadatas"]:
            for meta in result["metadatas"]:
                if meta and "filename" in meta and "file_hash" in meta:
                    sources[meta["filename"]] = meta["file_hash"]
        return sources

    def count(self) -> int:
        return self.collection.count()
