"""Query enhancement services: expansion, router."""
import google.generativeai as genai

from src.core import QueryExpansionError, get_logger, settings

logger = get_logger(__name__)


def expand_query(query: str) -> list[str]:
    """Generate query variations using LLM."""
    if not settings.rag.use_query_expansion:
        return [query]

    if not settings.models.gemini_api_key:
        logger.warning("No GEMINI_API_KEY, skipping query expansion")
        return [query]

    try:
        genai.configure(api_key=settings.models.gemini_api_key)
        model = genai.GenerativeModel(settings.models.gemini_model)

        prompt = settings.rag.expansion_prompt.format(
            count=settings.rag.expansion_count,
            query=query,
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=200,
            ),
        )

        if response.text:
            alternatives = [
                line.strip()
                for line in response.text.strip().split("\n")
                if line.strip()
            ]
            return [query, *alternatives[:settings.rag.expansion_count]]

    except QueryExpansionError:
        logger.exception("Query expansion failed")

    return [query]


def needs_retrieval(query: str) -> bool:
    """Determine if query needs RAG or can be answered directly."""
    if not settings.rag.use_adaptive_router:
        return True

    query_lower = query.lower().strip()

    for pattern in settings.rag.greeting_patterns:
        if query_lower.startswith(pattern) or query_lower == pattern:
            logger.info("Router: greeting detected, skipping RAG")
            return False

    if len(query_lower) < settings.rag.min_query_length:
        logger.info("Router: query too short, skipping RAG")
        return False

    return True
