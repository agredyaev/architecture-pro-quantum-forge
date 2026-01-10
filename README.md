# QuantumForge RAG Bot

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-4B8BBE)
![Redis](https://img.shields.io/badge/Redis-5%2B-DC382D?logo=redis&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?logo=google&logoColor=white)
![ColBERT](https://img.shields.io/badge/ColBERT-colbert--ir%2Fcolbertv2.0-777777)

Telegram bot that answers questions from a local knowledge base using retrieval + Gemini 2.5 Flash.

## What it does
- Query expansion (LLM paraphrases) then dense + ColBERT retrieval and cross-encoder reranking
- Incremental indexing of markdown in `data/processed/`
- Evaluation pipeline with LLM-as-judge metrics

## Quickstart
1. `make install`
2. `make setup-env` (set `GEMINI_API_KEY`, optional `TELEGRAM_BOT_TOKEN`)
3. `make update-index`
4. `make bot`

## Evaluation
`make evaluate`

## Docs
- `docs/c4-model.md`
- `docs/diagrams/img/`
- `docs/evaluation-methodology.md`
