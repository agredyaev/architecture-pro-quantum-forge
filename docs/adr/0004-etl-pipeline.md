# ADR 004: ETL и инкрементальное обновление

## Статус
Принят

## Дата
2026-01-08

## Участники
Архитектор системы

## Контекст
База знаний (~21k файлов) обновляется ежедневно (~400 страниц/мес). Полная переиндексация:
- Время: 12-15 мин (100K чанков, Nomic Embed, M2)
- Нецелесообразно при изменении 1-2 файлов

Требование FR-04: система не должна повторно обрабатывать неизменённые файлы.

## Источники
- [Research Report](../research/task-1-infrastructure-research.md)

## Анализ альтернатив

### State Store

| Метод | Sync | Отказоустойчивость | Сложность |
|-------|------|-------------------|-----------|
| JSON manifest | Внешний | Рассинхронизация при удалении индекса | Низкая |
| SQLite | Внешний | Рассинхронизация при удалении индекса | Низкая |
| Redis | Внешний | Eviction, требует persistence | Средняя |
| ChromaDB metadata | Встроенный | Автосинхронизация | Низкая |

## Решение

### Chroma Metadata (Stateless ETL)

Хранение хэша файла в metadata чанка:
```python
{
    "source": "docs/api.md",
    "file_hash": "a1b2c3d4...",
    "section": "Authentication",
    "indexed_at": "2026-01-08T12:00:00Z"
}
```

### Алгоритм update_index.py

```
1. SCAN
   - Обход filesystem: glob("data/processed/*.md")
   - Расчет MD5 для каждого файла
   - Результат: dict[path, hash]
   - Время: O(N), ~5 сек для 21K файлов

2. FETCH
   - collection.get(include=["metadatas"])
   - Извлечение unique(source, file_hash)
   - Результат: dict[path, hash]
   - Время: O(N), ~2 сек для 100K чанков

3. DIFF
   - to_ingest = {f: h for f, h in local if f not in chroma or chroma[f] != h}
   - to_delete = {f for f in chroma if f not in local}

4. EXECUTE
   - DELETE: collection.delete(where={"source": {"$in": list(to_delete)}})
   - CHUNK: split(to_ingest files)
   - EMBED: nomic.embed(chunks)
   - UPSERT: collection.upsert(ids, embeddings, metadatas)

5. LOG
   - {"timestamp", "added": len(to_ingest), "deleted": len(to_delete), "duration_sec"}
```

### Error Handling

| Ошибка | Действие | Retry |
|--------|----------|-------|
| ChromaDB connection failed | Exit с кодом 1, log error | 3 попытки, backoff 5s |
| File read error | Skip файл, log warning | Нет |
| Embedding API error | Skip батч, log error | 3 попытки |
| Disk full | Exit с кодом 1, alert | Нет |

### Batching

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| Batch size (embed) | 100 чанков | Память Nomic ~2GB |
| Batch size (upsert) | 500 чанков | ChromaDB оптимум |
| Parallel workers | 1 | M2 unified memory |

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Hash collision (MD5) | <0.0001% | Низкое | Допустимо для MVP |
| Большой FETCH при 1M docs | Средняя | Среднее | Pagination, batch 10K |
| Concurrent ingest | Низкая | Среднее | File lock, singleton |

## Последствия

| Сценарий | Время |
|----------|-------|
| Cold start (21K файлов) | 12-15 мин |
| Incremental (10 файлов) | 10-20 сек |
| Incremental (100 файлов) | 1-2 мин |

Логирование: `logs/update_index.log`
```json
{"timestamp": "2026-01-08T12:00:00Z", "status": "success", "files_scanned": 120, "files_added": 5, "files_updated": 0, "files_deleted": 0, "chunks_indexed": 420, "index_size": 16304, "duration_seconds": 15.0, "errors": []}
```

## Связанные документы
- [Container Diagram](../diagrams/img/container.svg)
- [Deployment Diagram](../diagrams/img/deployment.svg)
- [ADR-001: Tech Stack](./0001-tech-stack-selection.md)
