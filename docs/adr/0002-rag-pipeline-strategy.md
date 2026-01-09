# ADR 002: Стратегия RAG пайплайна

## Статус
Принят

## Дата
2026-01-08

## Участники
Архитектор системы

## Контекст
Проблема: пользователи задают вопросы на разговорном языке, документация написана техническим языком.

| Проблема | Текущее | Target |
|----------|---------|--------|
| Precision@5 | 45% | >80% |
| Vocabulary Mismatch | 30% | <10% |
| Latency p95 | - | <1s |

## Источники
- [Research Report](../research/task-1-infrastructure-research.md)
- [ColBERT Paper](https://arxiv.org/abs/2004.12832)
- [mxbai-colbert-large-v1](https://huggingface.co/mixedbread-ai/mxbai-colbert-large-v1)

---

## Анализ альтернатив

### 1. Chunking Strategy

| Метод | Описание | Pros | Cons |
|-------|----------|------|------|
| Fixed-size (512 tok) | Разбиение по количеству токенов | Простота, предсказуемость | Разрыв семантики, 20% fragmentation |
| Recursive Character | Split по разделителям (\n\n, \n, .) | Лучше фиксированного | Все еще разрывает контекст |
| **Semantic Chunking** | Split по embedding similarity | Сохраняет семантику, <5% fragmentation | +50ms на индексацию |
| Agentic Chunking | LLM определяет границы | Лучшее качество | +500ms, дорого |

**Решение: Semantic Chunking**
- Причина: баланс качества и latency
- Fallback: Recursive Character при ошибках

---

### 2. Retrieval Method

| Метод | Precision@5 | Latency | Механизм |
|-------|-------------|---------|----------|
| Dense (single vector) | 65% | 5ms | Query vs Doc = 1 score |
| Sparse (BM25) | 55% | 3ms | Term frequency |
| Hybrid (Dense + Sparse) | 75% | 10ms | RRF merge |
| **ColBERT (late interaction)** | 82% | 30ms | Token-to-token MaxSim |

**Решение: ColBERT (mixedbread-ai/mxbai-colbert-large-v1)**

Причины:
- +17% Precision vs single dense embedding (65% → 82%)
- Late Interaction: каждый токен query сравнивается с каждым токеном doc
- MaxSim scoring: sum of max similarities per query token
- 30ms latency приемлемо для async UX (требование: <1s)

Механизм:
```
query_tokens = embed("What is Project Stardust?")  # [5 x 128]
doc_tokens = embed("Project Stardust was a secret...")  # [20 x 128]

# Late interaction: MaxSim
score = sum(max(q @ d.T for d in doc_tokens) for q in query_tokens)
```

---

### 3. Query Enhancement

| Метод | Описание | Precision | Latency |
|-------|----------|-----------|---------|
| None | Прямой embedding запроса | Baseline | 0ms |
| HyDE | LLM генерит synthetic doc | +7% | +300ms |
| **Query Expansion** | LLM генерит 3 reformulations | +10% | +100ms |
| Query Decomposition | Split complex → sub-queries | +15% | +200ms |

**Решение: Query Expansion (3 variations)**
- Причина: лучше HyDE по latency/quality tradeoff
- Parallel retrieval + RRF merge

---

### 4. Reranking

| Метод | Precision@5 | Latency | Модель |
|-------|-------------|---------|--------|
| None | 65% | 0ms | - |
| Bi-encoder | 70% | 50ms | same as retrieval |
| **Cross-encoder** | 80% | 200ms | mxbai-rerank-large-v1 |
| LLM-as-judge | 85% | 500ms | Gemini |

**Решение: Cross-encoder (mxbai-rerank-large-v1)**
- Причина: лучший quality/latency ratio
- Top-50 → Top-5, threshold 0.5

---

### 5. Adaptive Retrieval

| Подход | Описание | Impact |
|--------|----------|--------|
| Always RAG | Для любого запроса | Baseline |
| **Router-based** | Classifier определяет "нужен ли RAG" | -40% LLM calls |
| Self-RAG | LLM сам решает на лету | Complex, unstable |

**Решение: Router-based (heuristics MVP, classifier v2)**
- Причина: простота, экономия ресурсов

---

## Финальная архитектура

```
Query
  |
  v
[Router] -- no RAG --> [Direct LLM]
  |
  v
[Query Expansion] -- 3 reformulations (parallel)
  |
  v
[ColBERT Retrieval] -- late interaction, Top-50
  |
  v
[Cross-Encoder Rerank] -- Top-5
  |
  v
[LLM Generation]
```

---

## Риски

| Риск | P | I | Митигация |
|------|---|---|-----------|
| Semantic chunker fails | L | M | Fallback to recursive |
| Query expansion latency | M | L | Parallel + timeout |
| Reranker bottleneck | L | M | Cache popular queries |

---

## Метрики

| Показатель | Before | After |
|------------|--------|-------|
| Precision@5 | 45% | 80% |
| Recall@20 | 65% | 88% |
| Latency p50 | 150ms | 400ms |
| Latency p95 | 300ms | 800ms |

---

## Связанные документы
- [rag_service.py](../../src/rag/services/rag_service.py)
- [ADR-001: Tech Stack](./0001-tech-stack-selection.md)
