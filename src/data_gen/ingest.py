"""Ingestion script for processing knowledge base documents."""
import time

import torch

from src.core import get_logger, settings, setup_logging
from src.rag.infrastructure.chroma_repository import ChromaRepository
from src.rag.services.embeddings import EmbeddingService
from src.rag.services.ingestion import IngestionService

logger = get_logger(__name__)


def main() -> None:
    setup_logging()
    start_time = time.perf_counter()

    files = list(settings.paths.data_processed_dir.glob("*.md"))
    if not files:
        logger.error("No files found in %s", settings.paths.data_processed_dir)
        return

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info("Using device: %s", device)

    repository = ChromaRepository(persist_path=settings.vector_db.chroma_db_path)
    embedding_service = EmbeddingService(device=device)

    service = IngestionService(
        repository=repository,
        embedding_service=embedding_service,
    )
    service.run_pipeline(files)

    duration = time.perf_counter() - start_time
    logger.info("Total Time: %.2fs", duration)


if __name__ == "__main__":
    main()
