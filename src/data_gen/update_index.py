"""Incremental knowledge base index update script.

This script scans the knowledge_base directory for new, modified, or deleted
documents and updates the vector index accordingly. Designed for daily automated
execution via cron or launchd.
"""
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import torch

from src.core import IndexUpdateError, get_logger, settings, setup_logging
from src.rag.domain import UpdateStats
from src.rag.infrastructure.chroma_repository import ChromaRepository
from src.rag.services.embeddings import EmbeddingService
from src.rag.services.ingestion import IngestionService

logger = get_logger(__name__)


def compute_file_hash(filepath: Path) -> str:
    """Compute MD5 hash of a file."""
    return hashlib.md5(filepath.read_bytes(), usedforsecurity=False).hexdigest()


def detect_changes(
    source_dir: Path, indexed_sources: dict[str, str]
) -> tuple[list[Path], list[str]]:
    """Detect new, modified, and deleted files.

    Args:
        source_dir: Directory containing source files
        indexed_sources: Mapping of filename -> file_hash from vector DB

    Returns:
        Tuple of (files_to_add, sources_to_delete)
    """
    current_files = list(source_dir.glob("*.md"))
    current_filenames = {f.name for f in current_files}

    to_add: list[Path] = []
    to_delete: list[str] = []

    for filepath in current_files:
        filename = filepath.name
        file_hash = compute_file_hash(filepath)

        if filename not in indexed_sources:
            to_add.append(filepath)
            logger.info("New file detected: %s", filename)
        elif indexed_sources[filename] != file_hash:
            to_delete.append(str(filepath))
            to_add.append(filepath)
            logger.info("Modified file detected: %s", filename)

    for filename in indexed_sources:
        if filename not in current_filenames:
            to_delete.append(filename)
            logger.info("Deleted file detected: %s", filename)

    return to_add, to_delete




def write_log_entry(stats: UpdateStats) -> None:
    """Write JSON log entry to log file."""
    settings.paths.logs_dir.mkdir(exist_ok=True)

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "status": stats.status,
        "files_scanned": stats.files_scanned,
        "files_added": stats.files_added,
        "files_updated": stats.files_updated,
        "files_deleted": stats.files_deleted,
        "chunks_indexed": stats.chunks_indexed,
        "index_size": stats.index_size,
        "duration_seconds": round(stats.duration, 2),
        "errors": stats.errors,
    }

    with settings.paths.update_log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info("Log entry written to %s", settings.paths.update_log_file)


def main() -> None:
    """Run incremental index update."""
    setup_logging()
    start_time = time.perf_counter()
    errors: list[str] = []

    logger.info("=" * 60)
    logger.info("Starting incremental index update")
    logger.info("Source directory: %s", settings.paths.knowledge_base_dir)

    repository = ChromaRepository(persist_path=settings.vector_db.chroma_db_path)
    initial_count = repository.count()
    logger.info("Current index size: %d vectors", initial_count)

    indexed_sources = repository.get_all_sources()
    logger.info("Currently indexed files: %d", len(indexed_sources))

    current_files = list(settings.paths.knowledge_base_dir.glob("*.md"))
    logger.info("Files in knowledge base: %d", len(current_files))

    to_add, to_delete = detect_changes(settings.paths.knowledge_base_dir, indexed_sources)

    files_added = len([f for f in to_add if f.name not in indexed_sources])
    files_updated = len([f for f in to_add if f.name in indexed_sources])
    files_deleted = len([d for d in to_delete if d not in [str(f) for f in to_add]])

    logger.info("Changes detected: %d new, %d modified, %d deleted",
                files_added, files_updated, files_deleted)

    chunks_indexed = 0

    if to_delete:
        logger.info("Deleting vectors for %d sources", len(to_delete))
        try:
            repository.delete_by_source(to_delete)
        except IndexUpdateError as e:
            error_msg = f"Failed to delete sources: {e}"
            logger.exception(error_msg)
            errors.append(error_msg)

    if to_add:
        logger.info("Processing %d files for indexing", len(to_add))
        try:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            logger.info("Using device: %s", device)

            embedding_service = EmbeddingService(device=device)
            ingestion_service = IngestionService(
                repository=repository,
                embedding_service=embedding_service,
            )
            ingestion_service.run_pipeline(to_add)

            chunks_indexed = repository.count() - initial_count + len(to_delete)
        except IndexUpdateError as e:
            error_msg = f"Failed to index files: {e}"
            logger.exception(error_msg)
            errors.append(error_msg)

    duration = time.perf_counter() - start_time
    final_count = repository.count()

    status = "success" if not errors else "partial_success" if final_count > 0 else "failed"

    logger.info("=" * 60)
    logger.info("Update complete in %.2fs", duration)
    logger.info("Final index size: %d vectors", final_count)
    logger.info("Status: %s", status)

    stats = UpdateStats(
        status=status,
        files_scanned=len(current_files),
        files_added=files_added,
        files_updated=files_updated,
        files_deleted=files_deleted,
        chunks_indexed=max(0, chunks_indexed),
        index_size=final_count,
        duration=duration,
        errors=errors,
    )
    write_log_entry(stats)


if __name__ == "__main__":
    main()
