"""Domain entities for RAG system using Pydantic."""
from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    source: str
    filename: str
    file_hash: str
    section: str = ""
    page: int = 0

    model_config = {"frozen": True}


class Chunk(BaseModel):
    """A chunk of text with its metadata and embedding."""

    id: str
    text: str
    metadata: ChunkMetadata
    embedding: list[float] = Field(default_factory=list)

    model_config = {"frozen": True}


class Document(BaseModel):
    """A source document before chunking."""

    path: str
    content: str
    file_hash: str

    model_config = {"frozen": True}
