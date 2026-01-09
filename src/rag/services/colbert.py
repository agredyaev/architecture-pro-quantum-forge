import sys
import types
from pathlib import Path

from src.core import ModuleImportError

# Shim for RAGatouille compatibility with newer LangChain
# RAGatouille < 0.1.0 expects langchain.retrievers.document_compressors.base.BaseDocumentCompressor
if "langchain.retrievers" not in sys.modules:
    try:
        m_retrievers = types.ModuleType("langchain.retrievers")
        sys.modules["langchain.retrievers"] = m_retrievers

        m_compressors = types.ModuleType("langchain.retrievers.document_compressors")
        setattr(m_retrievers, "document_compressors", m_compressors)
        sys.modules["langchain.retrievers.document_compressors"] = m_compressors

        m_base = types.ModuleType("langchain.retrievers.document_compressors.base")

        class BaseDocumentCompressor:
            pass

        setattr(m_base, "BaseDocumentCompressor", BaseDocumentCompressor)
        setattr(m_compressors, "base", m_base)
        sys.modules["langchain.retrievers.document_compressors.base"] = m_base
    except ModuleImportError as e:
        # Best effort shim - log at debug level since this is expected in some environments
        import logging
        logging.getLogger(__name__).debug(
            "Could not create LangChain compatibility shim: %s", e
        )

from ragatouille import RAGPretrainedModel

from src.core import get_logger, settings

logger = get_logger(__name__)


class ColBERTRetriever:
    """ColBERT-based retriever using late interaction."""

    def __init__(self, index_path: Path | None = None) -> None:
        """Initialize ColBERT retriever."""
        self.index_path = index_path or Path(settings.rag.colbert_index_path)
        self._rag: RAGPretrainedModel | None = None
        self._index_name = "quantum_knowledge"

    def _load_model(self) -> RAGPretrainedModel:
        """Load or create RAGPretrainedModel."""
        if self._rag is None:
            if (self.index_path / ".ragatouille").exists():
                logger.info("Loading existing ColBERT index from %s", self.index_path)
                self._rag = RAGPretrainedModel.from_index(
                    str(self.index_path / ".ragatouille" / "colbert" / "indexes" / self._index_name)
                )
            else:
                logger.info("Creating new ColBERT model: %s", settings.models.colbert_model_path)
                self._rag = RAGPretrainedModel.from_pretrained(settings.models.colbert_model_path)
        return self._rag

    def index_documents(self, documents: list[str], metadatas: list[dict]) -> None:
        """Index documents with ColBERT."""
        rag = self._load_model()

        doc_ids = [meta.get("filename", f"doc_{i}") for i, meta in enumerate(metadatas)]

        logger.info("Indexing %d documents with ColBERT...", len(documents))

        self.index_path.mkdir(parents=True, exist_ok=True)

        rag.index(
            collection=documents,
            document_ids=doc_ids,
            index_name=self._index_name,
            max_document_length=settings.rag.chunk_size,
            split_documents=False,
        )

        logger.info("ColBERT indexing complete")

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search using ColBERT late interaction."""
        rag = self._load_model()

        results = rag.search(query=query, k=top_k)

        return [
            {
                "text": r["content"],
                "source": r.get("document_id", "unknown"),
                "score": r["score"],
            }
            for r in results
        ]

    def is_indexed(self) -> bool:
        """Check if ColBERT index exists."""
        return (self.index_path / ".ragatouille").exists()
