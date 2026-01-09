"""Semantic cache service using Redis for RAG query caching."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import numpy as np
import redis

from src.core import get_logger, settings

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = get_logger(__name__)

# Type alias for sync Redis client with bytes response
RedisClient = redis.Redis[bytes]


class SemanticCache:
    """Semantic cache for RAG queries using Redis and embeddings similarity."""

    def __init__(
        self,
        redis_url: str | None = None,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
    ) -> None:
        """Initialize semantic cache.

        Args:
            redis_url: Redis connection URL
            similarity_threshold: Cosine similarity threshold for cache hit (0-1)
            ttl_seconds: Cache entry TTL in seconds
        """
        self.redis_url = redis_url or settings.redis.redis_url
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self._client: RedisClient | None = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Redis."""
        try:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=False,
            )
            self._client.ping()
            self._connected = True
            logger.info("Connected to Redis at %s", self.redis_url)
        except redis.ConnectionError as e:
            logger.warning("Redis connection failed: %s", e)
            self._connected = False
            return False
        else:
            return True

    def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            self._client.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected and self._client is not None

    def _hash_embedding(self, embedding: NDArray[np.float32]) -> str:
        """Create a hash key from embedding for exact match lookup."""
        return hashlib.sha256(embedding.tobytes()).hexdigest()[:32]

    def _cosine_similarity(
        self,
        a: NDArray[np.float32],
        b: NDArray[np.float32],
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def get(
        self,
        query: str,
        query_embedding: NDArray[np.float32],
    ) -> dict | None:
        """Get cached response if similar query exists.

        Args:
            query: The query text
            query_embedding: Query embedding vector

        Returns:
            Cached response dict or None if no cache hit
        """
        if not self.is_connected:
            return None

        try:
            assert self._client is not None
            exact_key = f"cache:exact:{self._hash_embedding(query_embedding)}"
            cached = self._client.get(exact_key)
            if cached:
                logger.debug("Exact cache hit for query: %s", query[:50])
                return json.loads(cached.decode())

            cursor: int = 0
            while True:
                cursor, keys = self._client.scan(
                    cursor=cursor,
                    match="cache:semantic:*",
                    count=100,
                )
                for key in keys:
                    data = self._client.get(key)
                    if not data:
                        continue

                    entry = json.loads(data.decode())
                    cached_embedding = np.array(
                        entry["embedding"], dtype=np.float32
                    )
                    similarity = self._cosine_similarity(
                        query_embedding, cached_embedding
                    )

                    if similarity >= self.similarity_threshold:
                        logger.info(
                            "Semantic cache hit (sim=%.3f) for: %s",
                            similarity,
                            query[:50],
                        )
                        return entry["response"]

                if cursor == 0:
                    break

        except redis.RedisError as e:
            logger.warning("Redis cache get failed: %s", e)

        return None

    def set(
        self,
        query: str,
        query_embedding: NDArray[np.float32],
        response: dict,
    ) -> bool:
        """Cache a query response.

        Args:
            query: The query text
            query_embedding: Query embedding vector
            response: Response dict to cache

        Returns:
            True if cached successfully
        """
        if not self.is_connected:
            return False

        try:
            assert self._client is not None
            semantic_key = f"cache:semantic:{self._hash_embedding(query_embedding)}"
            entry = {
                "query": query,
                "embedding": query_embedding.tolist(),
                "response": response,
            }
            self._client.setex(
                semantic_key,
                self.ttl_seconds,
                json.dumps(entry),
            )

            exact_key = f"cache:exact:{self._hash_embedding(query_embedding)}"
            self._client.setex(
                exact_key,
                self.ttl_seconds,
                json.dumps(response),
            )

            logger.debug("Cached response for: %s", query[:50])
        except redis.RedisError as e:
            logger.warning("Redis cache set failed: %s", e)
            return False
        else:
            return True

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of keys deleted
        """
        if not self.is_connected:
            return 0

        try:
            assert self._client is not None
            keys = list(self._client.scan_iter(match="cache:*"))
            if keys:
                deleted = self._client.delete(*keys)
                return deleted if isinstance(deleted, int) else 0
        except redis.RedisError as e:
            logger.warning("Redis cache clear failed: %s", e)

        return 0

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        if not self.is_connected:
            return {"connected": False}

        try:
            assert self._client is not None
            info = self._client.info("memory")
            keys_count = len(list(self._client.scan_iter(match="cache:*")))

            memory_used = "unknown"
            if isinstance(info, dict):
                memory_used = str(info.get("used_memory_human", "unknown"))

            return {
                "connected": True,
                "cached_queries": keys_count // 2,  # Divided by 2 (exact + semantic)
                "memory_used": memory_used,
            }
        except redis.RedisError:
            return {"connected": False}
