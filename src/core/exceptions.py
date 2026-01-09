"""Custom exceptions for the application."""


class QuantumForgeError(Exception):
    """Base exception for all application errors."""


class ConfigurationError(QuantumForgeError):
    """Configuration is missing or invalid."""


class APIKeyMissingError(ConfigurationError):
    """API key is not configured."""

    def __init__(self, key_name: str = "GEMINI_API_KEY") -> None:
        super().__init__(f"{key_name} is not configured in .env")
        self.key_name = key_name


class EmbeddingError(QuantumForgeError):
    """Error during embedding generation."""


class RetrievalError(QuantumForgeError):
    """Error during document retrieval."""


class IndexNotFoundError(RetrievalError):
    """Vector index does not exist."""

    def __init__(self, index_path: str) -> None:
        super().__init__(f"Index not found at {index_path}")
        self.index_path = index_path


class GenerationError(QuantumForgeError):
    """Error during LLM generation."""


class SecurityError(QuantumForgeError):
    """Security-related error (base)."""


class InjectionDetectedError(SecurityError):
    """Prompt injection was detected."""

    def __init__(self, source: str = "query") -> None:
        super().__init__(f"Injection detected in {source}")
        self.source = source


class CanaryLeakError(SecurityError):
    """Canary token was leaked in output."""


class ContextInjectionError(SecurityError):
    """Injection detected in retrieved context."""

    def __init__(self, source_file: str) -> None:
        super().__init__(f"Injection in context from {source_file}")
        self.source_file = source_file


class ChunkingError(QuantumForgeError):
    """Error during document chunking."""


class RerankerError(QuantumForgeError):
    """Error during reranking."""


class IndexUpdateError(QuantumForgeError):
    """Error during index update operation."""


class QueryExpansionError(QuantumForgeError):
    """Error during query expansion."""


class ModuleImportError(QuantumForgeError):
    """Error importing optional module."""

    def __init__(self, module_name: str, reason: str = "") -> None:
        msg = f"Failed to import module: {module_name}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
        self.module_name = module_name


class EvaluationError(QuantumForgeError):
    """Error during evaluation."""

