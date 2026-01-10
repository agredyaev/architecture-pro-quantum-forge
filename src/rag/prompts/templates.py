"""Prompt templates loader for RAG with Few-shot and Chain-of-Thought."""
from functools import lru_cache

from src.core import settings


@lru_cache(maxsize=10)
def _load_template(name: str) -> str:
    """Load a template file from prompts directory."""
    path = settings.paths.prompts_dir / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    msg = f"Template not found: {path}"
    raise FileNotFoundError(msg)


def get_system_prompt() -> str:
    """Get the system prompt template."""
    return _load_template("system")


def get_few_shot_examples() -> str:
    """Get the few-shot examples template."""
    return _load_template("few_shot")


def get_cot_instruction() -> str:
    """Get the Chain-of-Thought instruction template."""
    return _load_template("cot")


def get_user_template() -> str:
    """Get the user prompt template."""
    return _load_template("user")


def build_system_prompt(context: str) -> str:
    """Build the system prompt with context."""
    template = get_system_prompt()
    extra_instructions = ""
    if settings.rag.strict_attribution:
        extra_instructions = settings.rag.strict_attribution_instruction
    return template.format(
        context=context,
        extra_instructions=extra_instructions,
    )


def build_user_prompt(
    query: str,
    use_few_shot: bool = True,
    use_cot: bool = True,
) -> str:
    """Build the user prompt with optional Few-shot and CoT."""
    few_shot = get_few_shot_examples() if use_few_shot else ""
    cot = get_cot_instruction() if use_cot else ""
    template = get_user_template()

    return template.format(
        few_shot=few_shot,
        cot_instruction=cot,
        query=query,
    ).strip()


def reload_templates() -> None:
    """Clear template cache to reload from disk."""
    _load_template.cache_clear()
