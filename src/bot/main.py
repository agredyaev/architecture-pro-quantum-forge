"""Telegram bot for QuantumForge RAG."""
import asyncio

import torch
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from src.core import GenerationError, get_logger, settings, setup_logging
from src.rag.infrastructure.chroma_repository import ChromaRepository
from src.rag.services.embeddings import EmbeddingService
from src.rag.services.rag_service import RAGService

logger = get_logger(__name__)

dp = Dispatcher()
rag_service: RAGService | None = None


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "Welcome to QuantumForge Assistant!\n\n"
        "I can answer questions about the QuantumForge knowledge base.\n"
        "Just send me your question."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help\n\n"
        "Just send any question to search the knowledge base."
    )


@dp.message(F.text)
async def handle_query(message: Message) -> None:
    """Handle user queries."""
    if not rag_service:
        await message.answer("Service not initialized. Please try again later.")
        return

    query = message.text
    if not query:
        return

    await message.answer("Searching knowledge base...")

    try:
        result = rag_service.generate(
            query=query,
            use_few_shot=True,
            use_cot=True,
            top_k=settings.rag.top_k_rerank,
        )

        response = result.response
        sources = result.sources

        if sources:
            sources_text = "\n\nSources: " + ", ".join(sources[:3])
            response += sources_text

        await message.answer(response)

    except GenerationError:
        logger.exception("Error processing query")
        await message.answer("Sorry, an error occurred. Please try again.")


async def main() -> None:
    """Main entry point."""
    setup_logging()

    if not settings.models.gemini_api_key:
        logger.error("GEMINI_API_KEY not set in .env")
        return

    telegram_token = settings.telegram.telegram_bot_token
    if not telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        return

    global rag_service

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info("Initializing services on %s...", device)

    repository = ChromaRepository(persist_path=settings.vector_db.chroma_db_path)
    embedding_service = EmbeddingService(device=device)
    rag_service = RAGService(
        repository=repository,
        embedding_service=embedding_service,
    )

    logger.info("Starting Telegram bot...")
    bot = Bot(token=telegram_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
