"""Wiki page downloader for knowledge base creation."""
import email.utils
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import trafilatura
from tqdm import tqdm

from src.core import get_logger, settings, setup_logging

logger = get_logger(__name__)


def load_urls() -> list[str]:
    """Load URLs from external JSON file."""
    if settings.paths.scrape_urls_file.exists():
        with settings.paths.scrape_urls_file.open(encoding="utf-8") as f:
            return json.load(f)
    logger.warning("URLs file not found: %s", settings.paths.scrape_urls_file)
    return []


def get_file_mtime_rfc2822(filepath: Path) -> str | None:
    """Get file modification time in RFC 2822 format (for HTTP headers)."""
    if not filepath.exists():
        return None
    mtime = filepath.stat().st_mtime
    return email.utils.formatdate(mtime, usegmt=True)


def fetch_and_save_page(url: str, output_dir: Path) -> bool:
    """Fetch a URL and save as Markdown file, respecting If-Modified-Since."""
    filename = url.rstrip("/").split("/")[-1] + ".md"
    filepath = output_dir / filename

    last_modified = get_file_mtime_rfc2822(filepath)

    # trafilatura doesn't expose headers easily in fetch_url,
    # so we use requests directly to support If-Modified-Since headers.

    headers = {"User-Agent": "QuantumForgeBot/1.0"}
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == settings.scraping.http_not_modified:
            logger.debug("Skipped %s (Not Modified)", url)
            return True  # Considered success (up to date)

        if response.status_code != settings.scraping.http_ok:
            logger.warning("Failed to fetch %s: Status %d", url, response.status_code)
            return False

        downloaded = response.text

    except (requests.RequestException, OSError) as e:
        logger.warning("Error fetching %s: %s", url, e)
        return False

    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        no_fallback=True,
    )

    if not text:
        logger.warning("Extracted text is empty for %s", url)
        return False

    content = f"---\nsource: {url}\n---\n\n{text}"

    try:
        filepath.write_text(content, encoding="utf-8")
        logger.debug("Saved %s", filename)
    except OSError:
        logger.exception("FileSystem error while writing %s", filename)
        return False

    return True


def main() -> None:
    """Download all defined URLs."""
    setup_logging()
    settings.paths.data_raw_dir.mkdir(parents=True, exist_ok=True)

    urls = load_urls()
    if not urls:
        logger.error("No URLs loaded. Exiting.")
        return

    logger.info("Starting download of %d pages...", len(urls))

    success_count = 0
    with (
        tqdm(total=len(urls), desc="Downloading") as pbar,
        ThreadPoolExecutor(max_workers=5) as executor,
    ):
            futures = [
                executor.submit(fetch_and_save_page, url, settings.paths.data_raw_dir)
                for url in urls
            ]
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
                pbar.update(1)

    logger.info("Download completed. Success: %d/%d", success_count, len(urls))


if __name__ == "__main__":
    main()
