# Deployment Guide

## Local deployment

```bash
cd d:\Шарага\Кинжа4\Task_4_SmartDocProcessor
cp .env.example .env
docker compose up --build -d
```

## Production checklist

1. Set strong `JWT_SECRET` and `ENCRYPTION_KEY`.
2. Replace local RabbitMQ/Redis/PostgreSQL/MinIO with managed services.
3. Place API Gateway behind TLS reverse proxy.
4. Enable persistent volumes and backup schedules.
5. Configure webhook allowlist and outbound network rules.
6. Scale workers: `docker compose up --scale api-worker=4 -d`.
7. Add monitoring (Prometheus/Grafana) and centralized logs.

## Health checks

- `GET /health` on each service.
- `GET /services/health` on gateway.
- `GET /dashboard` for aggregated runtime metrics.

## CI commands

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```
