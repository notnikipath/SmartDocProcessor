# Project Report

## Objective

Build an intelligent distributed system that recognizes, classifies, and extracts structured data from heterogeneous documents.

## Result summary

- Implemented 9 microservices + frontend + shared contracts.
- Implemented end-to-end pipeline with stage-wise artifact persistence.
- Implemented asynchronous execution using Celery, RabbitMQ, and Redis.
- Added security and quality controls (RBAC, audit, encrypted payload, review loop).
- Added 6 optional features from the assignment groups.

## Target metrics (baseline simulation)

- OCR accuracy: `0.983`
- Classification accuracy: `0.956`
- Avg processing time: `7.4s`
- Concurrent users target: `120`

## Known limitations

- Baseline OCR is heuristic-first unless external engines are connected.
- Storage is in-memory in this educational version (replace with PostgreSQL/S3 adapters for production).
