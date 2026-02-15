# Cross talk network builder

The network builder service is a semantic text processor, that receives user messages
and supports a query that will list other users that are 'close' in terms of semantic connection (i.e. are talking about or writing about the same thing).

Details of the mathematics used can be found in [maths.md](maths.md).


## Local deployment

```bash
docker compose down && docker compose up --build
. .venv/bin/activate
pytest
```

Services started:
- `api` message injestion and query endpoints
- `embedder` consumes `messages.>` and publishes `embeddings.>`
- `clusterer` consumes `embeddings.>` and publishes `clusters.>`

- API: http://localhost:8000
- NATS: nats://localhost:4222
- NATS monitor: http://localhost:8222
- Postgres: localhost:5432
