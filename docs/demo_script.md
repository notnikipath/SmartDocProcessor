# Demo Script

1. Start stack:
   - `docker compose up --build -d`
2. Generate dataset:
   - `python scripts/generate_test_dataset.py`
3. Upload a document through frontend (`http://localhost:5173`) or API.
4. Open pipeline status endpoint:
   - `GET http://localhost:8600/pipeline/status/{job_id}`
5. Show extracted result and encrypted/decrypted payload:
   - `GET /pipeline/document/{doc_id}?decrypted=true`
6. Apply manual correction:
   - `POST /review/{doc_id}`
7. Show versions and learning samples:
   - `GET /results/{doc_id}/versions`
   - `GET /learning/samples`
8. Trigger retrain simulation:
   - `POST /learning/retrain`
9. Export in JSON/XML/CSV:
   - `GET /exports/{doc_id}?format=json|xml|csv`
