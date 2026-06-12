# Deployment Information

## Public URL

Status: ready to deploy. A real Railway/Render URL must be filled in after logging into the target cloud account.

```text
https://<your-agent-domain>.railway.app
```

## Platform

Recommended: Railway with a Redis plugin, or Render Blueprint with Redis.

## Environment Variables Set

```bash
ENVIRONMENT=production
AGENT_API_KEY=<strong-secret>
REDIS_URL=<redis-url>
REQUIRE_REDIS=true
RATE_LIMIT_PER_MINUTE=10
MONTHLY_BUDGET_USD=10
ALLOWED_ORIGINS=*
```

## Railway Commands

```bash
railway login
railway init
railway add redis
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=<strong-secret>
railway variables set REDIS_URL=<redis-url>
railway variables set REQUIRE_REDIS=true
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set MONTHLY_BUDGET_USD=10
railway up
railway domain
```

## Render Steps

1. Push this repository to GitHub.
2. Render Dashboard -> New -> Blueprint.
3. Select the repository.
4. Confirm `render.yaml`.
5. Set `REDIS_URL` from the Render Redis service if it is not auto-wired.
6. Deploy and copy the generated public URL here.

## Test Commands

Replace `$URL` and `$KEY` with the deployed URL and `AGENT_API_KEY`.

### Health Check

```bash
curl "$URL/health"
```

Expected: HTTP 200 with `"status":"ok"`.

### Readiness Check

```bash
curl "$URL/ready"
```

Expected: HTTP 200 when Redis is connected. HTTP 503 is acceptable while Redis/platform startup is still in progress.

### Authentication Required

```bash
curl -X POST "$URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

Expected: HTTP 401.

### Authenticated Agent Request

```bash
curl -X POST "$URL/ask" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"My name is Alice"}'
```

Expected: HTTP 200.

### Conversation History

```bash
curl -X POST "$URL/ask" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"What is my name?"}'
```

Expected answer mentions Alice.

### Rate Limiting

```bash
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/ask" \
    -H "X-API-Key: $KEY" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"test_rate\",\"question\":\"test $i\"}"
done
```

Expected: first 10 requests return 200, later requests return 429.

## Local Verification

```bash
cp .env.example .env
NGINX_PORT=8080 docker compose up --build --scale agent=3
curl http://localhost:8080/health
curl -X POST http://localhost:8080/ask \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local","question":"My name is Alice"}'
```

Verified locally on 2026-06-12:
- Docker image size: 381 MB.
- Stack: 3 healthy agent replicas, 1 healthy Redis, Nginx on port 8080.
- `/health`: 200.
- `/ready`: 200 with Redis.
- Missing API key on `/ask`: 401.
- Conversation test: `"What is my name?"` returns Alice.
- Rate limit: first 10 requests return 200, later requests return 429.
