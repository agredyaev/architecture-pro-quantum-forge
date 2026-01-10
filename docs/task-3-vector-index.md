# Задание 3: Векторный индекс

## Компоненты

| Файл | Назначение |
|------|------------|
| [ingest.py](../src/data_gen/ingest.py) | Entry point |
| [ingestion.py](../src/rag/services/ingestion.py) | Pipeline logic |
| [embeddings.py](../src/rag/services/embeddings.py) | Embedding generation |
| [chroma_repository.py](../src/rag/infrastructure/chroma_repository.py) | Vector storage |
| [test_retrieval.py](../src/data_gen/test_retrieval.py) | Retrieval validation |

## Конфигурация

Источник: [config.py](../src/core/config.py)

| Параметр | Значение |
|----------|----------|
| `chunk_size` | 512 |
| `chunk_overlap` | 50 |
| `separators` | `["\n\n", "\n", ". ", " ", ""]` |
| `chroma_db_path` | `data/chroma_storage` |
| `chroma_collection_name` | `quantum_knowledge` |
| `chroma_batch_size` | 5000 |
| `hnsw:space` | `cosine` |
| `embedding_model_path` | `nomic-ai/nomic-embed-text-v1.5` |
| `vector_size` | 768 |

## Pipeline

| Шаг | Executor | Операция |
|-----|----------|----------|
| 1. Parse | ProcessPoolExecutor | UnstructuredMarkdownLoader → RecursiveCharacterTextSplitter |
| 2. Embed | multi_process_pool (CPU) / batch (GPU) | SentenceTransformer encode |
| 3. Write | Sequential batch 5000 | ChromaDB add |

## Embedding

| Параметр | Значение |
|----------|----------|
| Model | `nomic-ai/nomic-embed-text-v1.5` |
| Размерности (Matryoshka) | 768, 512, 256, 128, 64 |
| Doc prefix | `search_document: ` |
| Query prefix | `search_query: ` |

## Метаданные chunk

| Поле | Источник |
|------|----------|
| `id` | UUID5(content + filename) |
| `file_hash` | MD5 исходного файла |
| `filename` | Имя файла |
| `source` | Полный путь |

## Запуск

| Команда | Описание |
|---------|----------|
| `make ingest` | Полная индексация |
| `uv run python -m src.data_gen.test_retrieval` | Тест retrieval |

## ADR

- [0002-rag-pipeline-strategy.md](adr/0002-rag-pipeline-strategy.md)
- [0001-tech-stack-selection.md](adr/0001-tech-stack-selection.md)
