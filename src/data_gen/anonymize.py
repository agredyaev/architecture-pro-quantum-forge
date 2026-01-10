"""Anonymization script for knowledge base documents."""
import json
import re
from pathlib import Path

from src.core import get_logger, settings, setup_logging

logger = get_logger(__name__)


def load_replacements(path: Path) -> dict[str, str]:
    """Load replacements from external JSON file."""
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    logger.warning("Replacements file not found: %s", path)
    return {}


def sanitize_text(text: str, replacements: dict[str, str]) -> str:
    """Replace terms in text using case-insensitive regex."""
    for old, new in replacements.items():
        pattern = re.compile(re.escape(old), re.IGNORECASE)
        text = pattern.sub(new, text)
    return text


def process_file(file_path: Path, replacements: dict[str, str]) -> bool:
    """Read, sanitize, and save a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        new_content = sanitize_text(content, replacements)

        new_filename = sanitize_text(file_path.name, replacements)
        new_filename = new_filename.replace(" ", "_")

        out_path = settings.paths.data_processed_dir / new_filename
        out_path.write_text(new_content, encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to process %s", file_path)
        return False
    else:
        return True


def main() -> None:
    setup_logging()
    settings.paths.data_processed_dir.mkdir(parents=True, exist_ok=True)

    replacements = load_replacements(settings.paths.replacements_file)
    if not replacements:
        logger.error("No replacements loaded. Exiting.")
        return

    with settings.paths.terms_map_file.open("w", encoding="utf-8") as f:
        json.dump(replacements, f, indent=2, ensure_ascii=False)

    files = list(settings.paths.data_raw_dir.glob("*.md"))
    logger.info("Starting anonymization of %d files...", len(files))

    processed_count = sum(1 for fp in files if process_file(fp, replacements))

    logger.info(
        "Processed %d/%d files. Saved to %s",
        processed_count,
        len(files),
        settings.paths.data_processed_dir,
    )


if __name__ == "__main__":
    main()
