# ADR 001: Выбор технологического стека

## Статус
Принят

## Дата
2026-01-08

## Участники
Архитектор системы

## Контекст
RAG-система для базы знаний QuantumForge Software.

Исходные данные:
- Документов: 21,250 (18K MD + 3K Confluence + 250 PDF)
- Чанков после индексации: 85,000-110,000
- Нагрузка: 100-500 запросов/день
- Пользователи: разработчики, саппорт, менеджеры

Ограничения:
- C-01: ChromaDB persistent storage обязателен
- C-02: Локальные embeddings (без OpenAI API)
- C-03: Бюджет LLM API < $50/мес
- BG-01: TTFT < 3 сек

## Decision Drivers

| Критерий | Вес | Обоснование |
|----------|-----|-------------|
| Стоимость/мес | 30% | Бюджет ограничен |
| Latency (TTFT) | 25% | UX Telegram требует < 3 сек |
| Качество ответов | 25% | 80% точность на Golden Set |
| Простота интеграции | 10% | Сроки MVP 2 недели |
| Приватность | 10% | SOC 2 документы |

## Источники
- [Research Report](../research/task-1-infrastructure-research.md)

## Анализ альтернатив

### 1. LLM

| Модель | Input $/1M | Output $/1M | Context | MMLU | TTFT |
|--------|------------|-------------|---------|------|------|
| GPT-5 mini | 0.25 | 2.00 | 128K | 84% | 200-400ms |
| Gemini 2.5 Flash | 0.50 | 3.00 | 1M | 86% | 150-300ms |
| Claude Haiku 4.5 | 1.00 | 5.00 | 200K | 82% | 200-400ms |
| Llama 3.1 70B | 0 (GPU $316/мес) | - | 128K | 83% | 2-5s |

Расчет стоимости (500 req/day, 2000 tok in, 500 tok out):
- GPT-5 mini: $22.50/мес
- Gemini 2.5 Flash: $37.50/мес
- Llama 70B: $316/мес (GPU)

### 2. Vector DB

| База | Query (100K) | Index (100K) | Metadata | Persistence |
|------|--------------|--------------|----------|-------------|
| FAISS | 0.34 ms | 5 сек | Нет | Ручное |
| ChromaDB | 2.58 ms | 20 сек | SQLite | Автоматическое |
| Qdrant | 1-3 ms | 15 сек | RocksDB | Автоматическое |

### 3. Embeddings

| Модель | Dim | Context | MTEB | Индексация (100K, M2) |
|--------|-----|---------|------|----------------------|
| Nomic Embed v1.5 | 768 | 8192 | 62.28 | 12-15 мин |
| BGE-M3 | 1024 | 8192 | 64.5 | 15-20 мин |
| OpenAI small | 1536 | 8191 | 62.3 | Зависит от сети |

## Решение

| Компонент | Выбор | Обоснование |
|-----------|-------|-------------|
| LLM | Gemini 2.5 Flash | Контекст 1M (8x больше GPT-5 mini), TTFT 150-300ms, $37.50/мес |
| Vector DB | ChromaDB | Соответствует C-01, встроенные метаданные, 2.58ms query |
| Embeddings | Nomic Embed v1.5 | Соответствует C-02 и FR-03 (768 dim), 8192 контекст |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | Необходим для FR-05 (score > 2.8 фильтрация) |

## План миграции на Qdrant

Триггеры:
- Документов > 500K (ChromaDB degradation)
- Требуется hybrid search (dense + sparse)
- Query latency > 50ms

| Этап | Действие | Время |
|------|----------|-------|
| 1 | Docker compose: qdrant/qdrant:latest | 1 час |
| 2 | Адаптер LangChain: Chroma -> Qdrant | 2 часа |
| 3 | Переиндексация (100K чанков) | 15 мин |
| 4 | Тестирование (Golden Set) | 2 часа |

Стоимость: +0 EUR (тот же сервер CPX41).

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Gemini API недоступен | Низкая | Высокое | Fallback на GPT-5 mini (конфиг) |
| PII утечка в Google | Средняя | Высокое | Regex фильтр перед отправкой (ADR-003) |
| ChromaDB > 500K docs | Низкая | Среднее | Миграция на Qdrant (план в ADR-004) |
| Бюджет превышен | Средняя | Низкое | Rate limiting, semantic cache |

## Последствия

Позитивные:
- Локальный запуск embeddings и vector DB
- TTFT 150-300ms (требование: <3s)
- Стоимость $37.50/мес (в рамках C-03: <$50)

Негативные:
- Vendor lock-in на Gemini API
- Нет hybrid search в ChromaDB
- Данные запросов уходят в Google Cloud

## Связанные документы
- [Research Report](../research/task-1-infrastructure-research.md)
- [Container Diagram](../diagrams/img/container.svg)
- [Deployment Diagram](../diagrams/img/deployment.svg)
