"""Test script for retrieval quality validation."""
import torch

from src.core import get_logger, settings, setup_logging
from src.rag.infrastructure.chroma_repository import ChromaRepository
from src.rag.services.embeddings import EmbeddingService

logger = get_logger(__name__)


def test_retrieval(query: str, n_results: int = 5) -> None:
    """Test retrieval for a given query."""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print("=" * 60)

    results = repository.query(
        query_embedding=embedding_service.embed_query(query, settings.rag.vector_size),
        n_results=n_results,
    )

    if results["documents"] and results["documents"][0]:
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            strict=True,
        )):
            print(f"\n[{i+1}] Score: {1 - dist:.4f} | Source: {meta.get('filename', 'N/A')}")
            print(f"    {doc[:200]}...")
    else:
        print("No results found.")


if __name__ == "__main__":
    setup_logging()

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info("Loading services...")

    repository = ChromaRepository(persist_path=settings.vector_db.chroma_db_path)
    embedding_service = EmbeddingService(device=device)

    print(f"\nIndex contains {repository.count()} vectors")

    test_retrieval("Who is the Chief Architect Zero?")
    test_retrieval("What is Project Stardust?")
    test_retrieval("How does the Source Code work?")
