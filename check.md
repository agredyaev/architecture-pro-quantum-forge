# Documentation and Diagram Consistency Check

## Scope
- docs/*.md
- docs/diagrams/src/*.puml
- src/core/config.py, src/rag/services/*
- docker-compose.yml

## Alignment Summary (Docs -> Current Config Defaults)
- LLM/Judge: Gemini 2.5 Flash
- ColBERT model: colbert-ir/colbertv2.0
- Reranker model: cross-encoder/ms-marco-MiniLM-L-6-v2
- Rerank threshold: 2.8
- Knowledge base path: data/processed
- Update log: logs/update_index.log
- Deployment diagram includes ETL container and data/raw + data/processed volumes

## Notes
- If config values change, update docs/diagrams and regenerate SVGs from puml sources.
