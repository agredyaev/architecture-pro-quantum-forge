"""Ingestion service for processing and indexing documents."""
import hashlib
import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from src.core import get_logger, settings
from src.rag.infrastructure.chroma_repository import VectorRepository
from src.rag.services.embeddings import EmbeddingService

logger = get_logger(__name__)


def process_single_file(filepath: Path) -> list[dict]:
    """Parse and chunk a single file. Runs in separate process."""
    from src.core import settings as local_settings

    try:
        loader = UnstructuredMarkdownLoader(str(filepath))
        raw_docs = loader.load()
        if not raw_docs:
            return []

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=local_settings.rag.chunk_size,
            chunk_overlap=local_settings.rag.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        docs = splitter.split_documents(raw_docs)

        file_hash = hashlib.md5(filepath.read_bytes(), usedforsecurity=False).hexdigest()
        filename = filepath.name

        results = []
        for doc in docs:
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.page_content + filename))
            results.append({
                "id": doc_id,
                "text": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "file_hash": file_hash,
                    "filename": filename,
                    "source": str(filepath),
                },
            })
    except (OSError, ValueError):
        return []
    else:
        return results


class IngestionService:
    """Service for ingesting documents into vector storage."""

    def __init__(
        self,
        repository: VectorRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        """Initialize with injected dependencies."""
        self.repository = repository
        self.embedding_service = embedding_service
        logger.info("IngestionService initialized")

    def run_pipeline(self, files: list[Path]) -> None:
        """Run the full ingestion pipeline for given files."""
        all_chunks: list[dict] = []

        logger.info("Step 1: Parsing %d files (Parallel CPU)", len(files))
        with ProcessPoolExecutor() as executor:
            results = list(tqdm(
                executor.map(process_single_file, files),
                total=len(files),
                unit="file",
            ))

        for res in results:
            all_chunks.extend(res)

        total_chunks = len(all_chunks)
        logger.info("Generated %d chunks", total_chunks)

        if total_chunks == 0:
            logger.warning("No content found. Exiting.")
            return

        logger.info("Step 2: Embedding %d vectors (Batch CPU)", total_chunks)

        texts = [c["text"] for c in all_chunks]
        ids = [c["id"] for c in all_chunks]
        metadatas = [c["metadata"] for c in all_chunks]

        embeddings = self.embedding_service.embed_documents(texts, settings.rag.vector_size)

        logger.info("Step 3: Writing to VectorRepository (Batched)")

        batch_size = settings.vector_db.chroma_batch_size
        for i in tqdm(range(0, total_chunks, batch_size), desc="Writing DB"):
            end = min(i + batch_size, total_chunks)
            self.repository.add_batch(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=texts[i:end],
                metadatas=metadatas[i:end],
            )

        logger.info("Ingestion Complete. Total vectors: %d", self.repository.count())
