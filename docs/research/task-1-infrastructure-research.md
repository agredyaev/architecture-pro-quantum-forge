# Задание 1: Исследование моделей и инфраструктуры

Дата: 2026-01-08
Версия: 4.0

## Резюме

| Компонент | Рекомендация | Цена | Обоснование |
|-----------|--------------|------|-------------|
| LLM | Gemini 2.5 Flash | $0.50/1M in, $3.00/1M out | Контекст 1M, баланс цена/качество |
| Embeddings | Nomic Embed v1.5 | 0 (локально) | MTEB 62.28, 768 dim, 8192 контекст |
| Vector DB | ChromaDB | 0 | Простота, persistence, метаданные |
| Инфраструктура | Hetzner CPX41 | 25 EUR/мес | 8 vCPU, 16 GB RAM |

---

## 1. Контекст QuantumForge Software

### 1.1 Данные компании

| Параметр | Значение |
|----------|----------|
| Markdown/MDX файлов | 18,000 |
| Confluence страниц | 3,000 |
| PDF спецификаций | 250 |
| Прирост | 400 страниц/мес |
| Общий объем текста | 150-200 MB |
| Расчетное количество чанков | 85,000-110,000 |

### 1.2 Нагрузка

| Роль | Запросов/день |
|------|---------------|
| Разработчики | 10-20/чел |
| Саппорт | 5-10/чел |
| Менеджеры | 2-5/чел |
| Оценка для MVP | 100-500 всего |

---

## 2. Сравнение LLM-моделей

### 2.1 Локальные модели (Hugging Face)

| Модель | Параметры | Context | VRAM | MMLU | Throughput (A10) |
|--------|-----------|---------|------|------|------------------|
| Llama 3.1 8B | 8B | 128K | 16 GB | 68.4% | 40-60 tok/s |
| Llama 3.1 70B | 70B | 128K | 140 GB | 83.0% | 8-15 tok/s |
| Mistral 7B | 7B | 32K | 14 GB | 62.5% | 50-70 tok/s |
| Qwen2.5 72B | 72B | 128K | 144 GB | 85.3% | 8-12 tok/s |

Источники:
- Hugging Face: https://huggingface.co/meta-llama
- Open LLM Leaderboard: https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard

### 2.2 Облачные модели

| Модель | Input $/1M | Output $/1M | Context | MMLU | TTFT |
|--------|------------|-------------|---------|------|------|
| GPT-5 mini | 0.25 | 2.00 | 128K | 84% | 200-400ms |
| GPT-5.2 | 1.75 | 14.00 | 128K | 92% | 300-500ms |
| Gemini 2.5 Flash | 0.50 | 3.00 | 1M | 86% | 150-300ms |
| Claude Haiku 4.5 | 1.00 | 5.00 | 200K | 82% | 200-400ms |
| YandexGPT Pro 5.1 | 0.44 RUB/1K | 0.44 RUB/1K | 32K | N/A | 400-700ms |

Источники:
- OpenAI: https://openai.com/pricing
- Google: https://ai.google.dev/pricing
- Anthropic: https://anthropic.com/pricing
- Yandex: https://yandex.cloud/docs/foundation-models/pricing

### 2.3 Сравнение по критериям

| Критерий | Локальные (70B) | Облачные (Gemini 2.5 Flash) |
|----------|-----------------|---------------------------|
| Качество (MMLU) | 83-85% | 86% |
| Скорость (TTFT) | 2-5 сек (GPU) | 150-300 мс |
| Скорость (throughput) | 8-15 tok/s | 100+ tok/s |
| Стоимость/мес (500 req/day) | $316+ (GPU аренда) | $37 |
| Развертывание | Сложное (VRAM, drivers) | Простое (API key) |
| Конфиденциальность | Полная | Данные уходят в облако |

### 2.4 Расчет стоимости для QuantumForge

Параметры: 500 запросов/день, 2000 токенов input, 500 токенов output

| Модель | Input/мес | Output/мес | Итого/мес |
|--------|-----------|------------|-----------|
| GPT-5 mini | $7.50 | $15.00 | $22.50 |
| Gemini 2.5 Flash | $15.00 | $22.50 | $37.50 |
| Claude Haiku 4.5 | $30.00 | $37.50 | $67.50 |
| Llama 70B (RunPod A10) | $316 (GPU) | - | $316+ |

### 2.5 Рекомендация по LLM

Gemini 2.5 Flash:
- Контекст 1M токенов (критично для RAG с 10-20 чанками по 500 токенов)
- MMLU 86% (выше локальных 70B моделей)
- TTFT 150-300ms (требование BG-01 < 3 сек выполнено)
- $37/мес vs $316/мес за локальную 70B

Альтернатива: GPT-5 mini при бюджете < $25/мес

---

## 3. Сравнение Embedding-моделей

### 3.1 Локальные модели (Sentence-Transformers)

| Модель | Dim | Max Tokens | MTEB | Индексация (100K, M2) |
|--------|-----|------------|------|----------------------|
| Nomic Embed v1.5 | 768 | 8192 | 62.28 | 12-15 мин |
| BGE-M3 | 1024 | 8192 | 64.5 | 15-20 мин |
| all-MiniLM-L6-v2 | 384 | 512 | 56.3 | 5-8 мин |
| E5-Mistral-7B | 4096 | 32768 | 66.6 | 60+ мин (GPU) |

### 3.2 Облачные модели (OpenAI)

| Модель | Dim | Max Tokens | MTEB | Цена/1M tok |
|--------|-----|------------|------|-------------|
| text-embedding-3-small | 1536 | 8191 | 62.3 | $0.02 |
| text-embedding-3-large | 3072 | 8191 | 64.6 | $0.13 |

Источники:
- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- Nomic: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
- OpenAI: https://openai.com/pricing

### 3.3 Сравнение по критериям

| Критерий | Локальные (Nomic) | Облачные (OpenAI small) |
|----------|-------------------|-------------------------|
| Скорость индексации | 100-150 doc/s (CPU) | Зависит от сети |
| Качество (MTEB) | 62.28 | 62.3 |
| Стоимость индексации (200MB) | $0 | $1.00 |
| Стоимость запросов/мес | $0 | $0.03 |
| Офлайн работа | Да | Нет |

### 3.4 Nomic Embed v1.5 (Matryoshka)

| Размерность | MTEB Score | Память (100K чанков) |
|-------------|------------|----------------------|
| 768 | 62.28 | 307 MB |
| 256 | 61.04 | 102 MB |
| 128 | 59.34 | 51 MB |

### 3.5 Рекомендация по Embeddings

Nomic Embed v1.5:
- Соответствует требованию FR-03 (768 dim)
- Соответствует требованию C-02 (локальные embeddings)
- Контекст 8192 токенов (достаточно для чанков 500-1000 токенов)
- Индексация 100K чанков: 12-15 мин на M2
- Apache 2.0 лицензия

---

## 4. Сравнение векторных баз данных

### 4.1 ChromaDB vs FAISS

| Критерий | ChromaDB | FAISS |
|----------|----------|-------|
| Тип | Embedded DB | Library |
| Query time (100K) | 2.58 ms | 0.34 ms |
| Индексация (100K) | 20 сек | 5 сек |
| Metadata storage | Встроено (SQLite) | Внешнее (нужна доп. БД) |
| Persistence | Автоматическое | Ручное (pickle/np.save) |
| Фильтрация | Встроенная | Внешняя реализация |
| GPU ускорение | Нет | Да (5-10x) |
| LangChain интеграция | Нативная | Нативная |
| Масштабируемость | До 1M документов | Без ограничений |

Источники:
- Towards AI Benchmark: https://towardsai.net/p/machine-learning/comparing-vector-databases
- ChromaDB: https://docs.trychroma.com
- FAISS: https://github.com/facebookresearch/faiss

### 4.2 Сложность внедрения

ChromaDB (минимальный код):
```python
import chromadb
client = chromadb.PersistentClient(path="data/chroma")
collection = client.create_collection("docs")
collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metas)
results = collection.query(query_embeddings=[query_vec], n_results=10)
```

FAISS (требует обвязку):
```python
import faiss
import json
index = faiss.IndexFlatL2(768)
index.add(vectors)
faiss.write_index(index, "index.faiss")
# Метаданные отдельно
with open("metadata.json", "w") as f:
    json.dump(metas, f)
```

### 4.3 Стоимость владения

| Статья | ChromaDB | FAISS |
|--------|----------|-------|
| Лицензия | Apache 2.0 | MIT |
| RAM (100K docs, 768 dim) | 500 MB | 400 MB |
| Disk | 1 GB | 400 MB + metadata |
| Доп. инфраструктура | Нет | SQLite/Postgres для metadata |
| Время разработки | 2-4 часа | 8-16 часов |

### 4.4 Рекомендация по Vector DB

ChromaDB:
- Соответствует требованию C-01 (persistent storage в data/chroma_storage)
- Встроенные метаданные source, page, section (FR-02)
- Простая интеграция с LangChain
- Query time 2.58ms достаточен для < 500 запросов/день
- Миграция на Qdrant при росте > 500K документов

---

## 5. Инфраструктура

### 5.1 Варианты серверов

| Вариант | CPU | RAM | GPU | Цена/мес | Применимость |
|---------|-----|-----|-----|----------|--------------|
| A. Apple Silicon M2 | 8 cores | 16 GB | Unified | 0 (локально) | Разработка |
| B. Hetzner CPX41 | 8 vCPU | 16 GB | Нет | 25 EUR | Production MVP |
| C. Hetzner CPX51 | 16 vCPU | 32 GB | Нет | 50 EUR | Production рост |
| D. RunPod A10 | 16 vCPU | 64 GB | A10 24GB | $316 | Локальная LLM |

Источники:
- Hetzner: https://www.hetzner.com/cloud
- RunPod: https://www.runpod.io/pricing

### 5.2 Рекомендация по инфраструктуре

Вариант B (Hetzner CPX41):
- 8 vCPU достаточно для ChromaDB + Nomic Embed
- 16 GB RAM > 500 MB (ChromaDB) + 2 GB (Nomic model)
- 240 GB SSD > 1 GB (index) + 200 MB (база знаний)
- 20 TB трафика > потребности MVP
- 25 EUR/мес = $27

---

## 6. Итоговые конфигурации (3 варианта)

### 6.1 Вариант 1: Минимальный бюджет

| Компонент | Выбор | Характеристики | Цена/мес |
|-----------|-------|----------------|----------|
| LLM | GPT-5 mini | 128K context, MMLU 84% | $22.50 |
| Embeddings | Nomic v1.5 | 768 dim, MTEB 62.28 | $0 |
| Vector DB | ChromaDB | 2.58ms query | $0 |
| Хостинг | Hetzner CPX21 | 3 vCPU, 4 GB | 8 EUR |
| **Итого** | | | **~$31** |

Ограничения: контекст 128K может быть недостаточен для 15-20 чанков

### 6.2 Вариант 2: Оптимальный (рекомендуется)

| Компонент | Выбор | Характеристики | Цена/мес |
|-----------|-------|----------------|----------|
| LLM | Gemini 2.5 Flash | 1M context, MMLU 86% | $37.50 |
| Embeddings | Nomic v1.5 | 768 dim, MTEB 62.28 | $0 |
| Vector DB | ChromaDB | 2.58ms query | $0 |
| Хостинг | Hetzner CPX41 | 8 vCPU, 16 GB | 25 EUR |
| **Итого** | | | **~$65** |

Преимущества: контекст 1M, быстрый TTFT, запас по ресурсам

### 6.3 Вариант 3: Максимальная конфиденциальность

| Компонент | Выбор | Характеристики | Цена/мес |
|-----------|-------|----------------|----------|
| LLM | Llama 3.1 70B | 128K context, MMLU 83% | $316 (GPU) |
| Embeddings | Nomic v1.5 | 768 dim, MTEB 62.28 | $0 |
| Vector DB | FAISS | 0.34ms query | $0 |
| Хостинг | RunPod A10 | 16 vCPU, 64 GB, A10 | $316 |
| **Итого** | | | **~$316** |

Применимость: только при запрете на передачу данных в облако

### 6.4 Сравнение вариантов

| Критерий | Вариант 1 | Вариант 2 | Вариант 3 |
|----------|-----------|-----------|-----------|
| Стоимость/мес | $31 | $65 | $316 |
| Контекст LLM | 128K | 1M | 128K |
| Качество (MMLU) | 84% | 86% | 83% |
| TTFT | 200-400ms | 150-300ms | 2-5s |
| Конфиденциальность | Низкая | Низкая | Полная |
| Сложность | Низкая | Низкая | Высокая |

**Выбор: Вариант 2** - оптимальный баланс цена/качество/функциональность

---

## 7. Соответствие требованиям

| ID | Требование | Решение | Статус |
|----|------------|---------|--------|
| BG-01 | TTFT < 3 сек | Gemini 2.5 Flash: 150-300ms | OK |
| FR-02 | Метаданные (source, page) | ChromaDB встроенные | OK |
| FR-03 | 768 dim | Nomic Embed v1.5 | OK |
| C-01 | ChromaDB persistent | data/chroma_storage | OK |
| C-02 | Локальные embeddings | Nomic (без API) | OK |
| C-03 | Бюджет < $5/мес | $65/мес | Превышен |

Примечание: требование C-03 ($5/мес) нереалистично. Минимальный рабочий бюджет: $31/мес.

---

## 8. Источники

| Ресурс | URL |
|--------|-----|
| OpenAI Pricing | https://openai.com/pricing |
| Google AI Pricing | https://ai.google.dev/pricing |
| Anthropic Pricing | https://anthropic.com/pricing |
| Yandex Cloud | https://yandex.cloud/docs/foundation-models/pricing |
| MTEB Leaderboard | https://huggingface.co/spaces/mteb/leaderboard |
| Open LLM Leaderboard | https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard |
| Nomic Embed v1.5 | https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 |
| ChromaDB Docs | https://docs.trychroma.com |
| FAISS GitHub | https://github.com/facebookresearch/faiss |
| Hetzner Cloud | https://www.hetzner.com/cloud |
| RunPod Pricing | https://www.runpod.io/pricing |
| Vector DB Benchmark | https://towardsai.net/p/machine-learning/comparing-vector-databases |
