"""Semantic chunking service using embedding similarity."""
from typing import TYPE_CHECKING

from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core import ChunkingError, get_logger, settings

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

logger = get_logger(__name__)


class ChunkingService:
    """Service for document chunking with semantic or recursive splitting."""

    def __init__(self, embedding_model: "Embeddings") -> None:
        """Initialize with embedding model for semantic chunking."""
        self.embedding_model = embedding_model
        self._semantic_chunker: SemanticChunker | None = None
        self._recursive_chunker = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag.chunk_size,
            chunk_overlap=settings.rag.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _get_semantic_chunker(self) -> SemanticChunker:
        """Lazy init semantic chunker."""
        if self._semantic_chunker is None:
            self._semantic_chunker = SemanticChunker(
                embeddings=self.embedding_model,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=int(settings.rag.semantic_threshold * 100),
            )
        return self._semantic_chunker

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks using configured strategy."""
        if not settings.rag.use_semantic_chunking:
            return self._recursive_chunker.split_text(text)

        try:
            chunker = self._get_semantic_chunker()
            return chunker.split_text(text)
        except ChunkingError:
            logger.exception("Semantic chunking failed, falling back to recursive")
            return self._recursive_chunker.split_text(text)

    def split_documents(self, documents: list) -> list:
        """Split LangChain documents."""
        if not settings.rag.use_semantic_chunking:
            return self._recursive_chunker.split_documents(documents)

        try:
            chunker = self._get_semantic_chunker()
            return chunker.split_documents(documents)
        except ChunkingError:
            logger.exception("Semantic chunking failed, falling back to recursive")
            return self._recursive_chunker.split_documents(documents)
