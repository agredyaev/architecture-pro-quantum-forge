"""Centralized logging configuration."""
import logging
import sys

from src.core.config import settings


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=level,
        format=settings.logging.log_format,
        datefmt=settings.logging.log_date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
