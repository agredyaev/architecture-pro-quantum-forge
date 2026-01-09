# Методология оценки RAG-системы

## 1. Метрики Retrieval

### Precision@K
Доля релевантных документов среди K возвращённых.
```
Precision@K = |Relevant ∩ Retrieved@K| / K
```
Целевое значение: ≥ 0.7

### Recall@K
Доля найденных релевантных документов от всех релевантных.
```
Recall@K = |Relevant ∩ Retrieved@K| / |Relevant|
```
Целевое значение: ≥ 0.8

### MRR (Mean Reciprocal Rank)
Средний обратный ранг первого релевантного документа.
```
MRR = (1/|Q|) × Σ(1/rank_i)
```

---

## 2. Метрики Generation

### Faithfulness
Доля утверждений ответа, подтверждённых контекстом.
```
Faithfulness = |Supported Claims| / |Total Claims|
```
Целевое значение: ≥ 0.9

### Answer Relevancy
Семантическое соответствие ответа запросу.
Оценка: cosine similarity между эмбеддингами вопроса и ответа.

### Hallucination Rate
Доля ответов с информацией, отсутствующей в контексте.
Целевое значение: ≤ 0.1

---

## 3. Агрегированные метрики

### Answer Rate
```
Answer Rate = |Answered Questions| / |Total Questions|
```
Целевое значение: ≥ 0.7 для известных тем.

### Correct Rejection Rate
```
Correct Rejection Rate = |Correct Rejections| / |Out-of-Domain Questions|
```
Целевое значение: ≥ 0.8

### Coverage Score
```
Coverage Score = 0.4×Answer Rate + 0.3×Correct Rejection Rate + 0.3×Source Accuracy
```
Целевое значение: ≥ 0.65

---

## 4. Golden Set Testing

### Состав набора
- 10 вопросов на известные темы (ожидается ответ)
- 3 вопроса на отсутствующие темы (ожидается отказ)
- 2 вопроса вне домена (ожидается отказ)

### Процедура
1. Загрузить вопросы из `data/golden_questions.json`
2. Выполнить каждый запрос через RAG-pipeline
3. Логировать результат в `logs/evaluation_logs.jsonl`
4. Рассчитать метрики
5. Сгенерировать отчёт `logs/evaluation_report.json`

### Критерии прохождения
- Answer Rate ≥ 70%
- Correct Rejection Rate ≥ 80%
- Coverage Score ≥ 65%

---

## 5. Классификация пробелов

| Тип пробела | Симптом | Действие |
|-------------|---------|----------|
| Missing Content | Нет ответа на известную тему | Добавить документы |
| Poor Chunking | Контекст найден, но нерелевантен | Оптимизировать размер чанков |
| Embedding Mismatch | Семантически похожие документы не находятся | Сменить модель эмбеддингов |
| Generation Failure | Контекст верный, ответ неверный | Доработать промпт |

---

## 6. Выходные артефакты

| Файл | Формат | Содержимое |
|------|--------|------------|
| `logs/query_logs.jsonl` | JSONL | Все запросы с метаданными |
| `logs/evaluation_logs.jsonl` | JSONL | Результаты оценки каждого вопроса |
| `logs/evaluation_report.json` | JSON | Агрегированные метрики и рекомендации |

---

## 7. Референсы

1. Es, S., et al. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation*. arXiv:2309.15217
2. Saad-Falcon, J., et al. (2024). *ARES: An Automated Evaluation Framework for RAG Systems*. ACL Anthology
3. Zhu, K., et al. (2024). *RAGEval: Scenario Specific RAG Evaluation Dataset Generation Framework*. arXiv:2408.01262
4. Chen, J., et al. (2024). *RGB: Benchmarking Retrieval-Augmented Generation for LLMs*. arXiv:2309.01431
5. Chuang, Y., et al. (2025). *HalluSearch: Multilingual Hallucination Detection*. SemEval-2025
6. Vectara. (2024). *HHEM: Hallucination Evaluation Model*. github.com/vectara/hallucination-leaderboard
