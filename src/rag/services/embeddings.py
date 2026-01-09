"""High-performance embedding service using SentenceTransformers."""
import logging

import numpy as np
from sentence_transformers import SentenceTransformer

from src.core import MatryoshkaDim, settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding service with Matryoshka Representation Learning support."""

    def __init__(self, device: str = "cpu") -> None:
        model_path = settings.models.embedding_model_path
        logger.info("Loading embedding model: %s on %s", model_path, device)
        self.model = SentenceTransformer(
            model_path,
            trust_remote_code=True,
            device=device,
        )
        self.doc_prefix = "search_document: "
        self.query_prefix = "search_query: "

    def embed_documents(self, texts: list[str], dim: MatryoshkaDim = 768) -> list[list[float]]:
        """Embed documents with optional Matryoshka truncation."""
        prefixed_texts = [self.doc_prefix + t for t in texts]

        if self.model.device.type == "cpu":
            # Multi-process encoding for CPU
            logger.info("Starting multi-process embedding pool")
            pool = self.model.start_multi_process_pool()
            try:
                embeddings = self.model.encode_multi_process(
                    prefixed_texts,
                    pool,
                    normalize_embeddings=True,
                )
            finally:
                self.model.stop_multi_process_pool(pool)
        else:
            # Standard batch encoding for GPU/MPS
            embeddings = self.model.encode(
                prefixed_texts,
                convert_to_numpy=True,
                show_progress_bar=True,
                normalize_embeddings=True,
            )

        if dim < settings.models.max_embedding_dim:
            embeddings = embeddings[:, :dim]
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms

        return embeddings.tolist()

    def embed_query(self, text: str, dim: MatryoshkaDim = 768) -> list[float]:
        """Embed a single query."""
        prefixed_text = self.query_prefix + text
        embedding = self.model.encode(
            [prefixed_text],
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        if dim < settings.models.max_embedding_dim:
            embedding = embedding[:, :dim]
            norm = np.linalg.norm(embedding, axis=1, keepdims=True)
            embedding = embedding / norm

        return embedding[0].tolist()
