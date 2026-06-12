# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Secret bi dat thang trong source code: `OPENAI_API_KEY` va database password nam trong `app.py`.
2. Log in ra secret: debug print hien thi API key trong terminal/log.
3. Config bi co dinh trong code: `DEBUG`, `MAX_TOKENS`, host va port khong doc tu environment.
4. Server bind `localhost`, nen container/cloud platform khong route duoc traffic tu ben ngoai.
5. Bat `reload=True`, phu hop development nhung khong phu hop production.
6. Khong co `/health` va `/ready`, platform khong biet luc nao can restart hoac stop routing.
7. Khong co graceful shutdown, request dang xu ly co the bi cat ngang khi deploy/restart.
8. Khong co auth/rate limit/cost guard, public API co the bi spam va gay ton chi phi.

### Exercise 1.2: Basic version observation
Basic app co the chay local bang:

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
curl -X POST "http://localhost:8000/ask?question=hello"
```

Ket luan: app tra loi duoc tren laptop, nhung chua production-ready vi phu thuoc localhost, secret nam trong code, khong co health check va khong co lifecycle handling.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Config | Hardcoded values | Environment variables | Cloud platforms inject config via env; khong can sua code khi deploy. |
| Secrets | API key/password trong source | Secret lay tu env | Tranh lo secret tren GitHub va de rotate key. |
| Host/port | `localhost:8000` | `0.0.0.0:$PORT` | Container/cloud can listen tren public interface va dynamic port. |
| Health check | Khong co | `/health` | Platform tu dong restart khi container loi. |
| Readiness | Khong co | `/ready` | Load balancer chi route traffic khi app san sang. |
| Logging | `print()` va log secret | Structured JSON logging | De search/parse trong monitoring system, khong ro ri secret. |
| Shutdown | Dot ngot | Lifespan/graceful shutdown | Hoan thanh request va dong connection truoc khi stop. |
| Debug mode | `reload=True` | Bat/tat qua env | Tranh reload process va leak debug info trong production. |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image cua basic Dockerfile la `python:3.11`, day la full Python image nen de dung nhung kha lon.
2. Working directory la `/app`.
3. `COPY requirements.txt` truoc de tan dung Docker layer cache: neu code doi nhung dependencies khong doi thi khong can cai lai package.
4. `CMD` la default command co the override khi `docker run`; `ENTRYPOINT` gan container voi mot executable chinh va thuong dung khi image hanh xu nhu mot CLI/service co dinh.

### Exercise 2.2: Build and run
Expected commands:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```

Basic image dung `python:3.11` nen thuong lon gan 1 GB tuy cache/platform.

### Exercise 2.3: Image size comparison
- Develop: about 1.0 GB, vi dung full `python:3.11`.
- Final production image measured locally: 381 MB (`batch02-day12_doanquang-agent:latest`).
- Difference: khoang 60%+ nho hon so voi single-stage full Python image, va duoi nguong 500 MB cua rubric.

Stage 1 (`builder`) cai build tools va dependencies. Stage 2 (`runtime`) chi copy installed packages va source code can chay, nen image nho hon va it attack surface hon.

### Exercise 2.4: Docker Compose stack
Services chinh:
- `nginx`: reverse proxy/load balancer, expose HTTP cho client.
- `agent`: FastAPI service xu ly `/ask`, `/health`, `/ready`.
- `redis`: shared state cho history, rate limit va budget.

Architecture:

```text
Client -> Nginx -> agent replicas -> Redis
```

Nginx route request vao service `agent:8000`; cac agent instance doc/ghi chung Redis nen scale ngang van giu duoc state.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
Deployment package da san sang voi `Dockerfile`, `railway.toml`, health check path `/health`, va env config.

Required Railway variables:

```bash
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=<strong-secret>
railway variables set REDIS_URL=<railway-redis-url>
railway variables set REQUIRE_REDIS=true
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set MONTHLY_BUDGET_USD=10
```

Public URL can dien sau khi deploy bang `railway domain`.

### Exercise 3.2: Render comparison
`railway.toml` tap trung vao build/deploy command cho mot service. `render.yaml` mo ta infrastructure theo Blueprint: web service, region, health check, auto deploy va env vars. Render co the khai bao Redis service trong Blueprint; Railway thuong them Redis plugin va set `REDIS_URL`.

### Exercise 3.3: Cloud Run understanding
`cloudbuild.yaml` build image va push len registry. `service.yaml` mo ta Cloud Run service: container image, env vars, scaling, resources va health/runtime settings. Cloud Run phu hop production hon khi can autoscaling, IAM va CI/CD chat che.

## Part 4: API Security

### Exercise 4.1: API key authentication
API key duoc check trong dependency doc header `X-API-Key`. Neu thieu hoac sai key, API tra `401`. Rotate key bang cach doi `AGENT_API_KEY` tren cloud dashboard va restart/redeploy service, khong can sua source code.

### Exercise 4.2: JWT authentication
JWT flow:
1. Client gui username/password toi `/token`.
2. Server tao signed token chua `sub`, `role`, `iat`, `exp`.
3. Client gui `Authorization: Bearer <token>` cho request sau.
4. Server verify signature/expiry va lay user identity tu token.

JWT la stateless vi server khong can luu session trong memory cho moi request.

### Exercise 4.3: Rate limiting
Implementation final dung sliding window tren Redis sorted set:
- Key: `rate:{user_id}`
- Window: 60 seconds
- Limit: 10 requests/minute/user
- Khi vuot limit, API tra `429` va header `Retry-After`.

Admin bypass co the lam bang role-based limit: user thuong 10 req/min, admin 100+ req/min hoac bo qua limiter cho role `admin`.

### Exercise 4.4: Cost guard implementation
Final implementation track monthly spend theo key `budget:{user_id}:{YYYY-MM}` trong Redis. Moi request uoc tinh token cost, check budget $10/month/user, record usage bang `INCRBYFLOAT`, va set TTL 32 ngay. Khi vuot budget, API tra `402 Payment Required`.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks
Final app co:
- `GET /health`: liveness, luon tra status process/app info neu app con song.
- `GET /ready`: readiness, tra `200` khi app ready va Redis ping OK; tra `503` khi chua san sang.

### Exercise 5.2: Graceful shutdown
Final app dung FastAPI lifespan de log startup/shutdown va dong readiness flag. Uvicorn xu ly SIGTERM; khi container bi stop, lifecycle shutdown chay va log `graceful shutdown complete`.

### Exercise 5.3: Stateless design
Conversation history, rate limit va budget deu dung Redis khi chay production/compose:
- `history:{user_id}`
- `rate:{user_id}`
- `budget:{user_id}:{YYYY-MM}`

Vi state nam ngoai process, nhieu agent replicas co the serve cung mot user ma khong mat conversation.

### Exercise 5.4: Load balancing
`docker-compose.yml` co `nginx`, `agent`, `redis`. Chay scale:

```bash
docker compose up --scale agent=3
```

Nginx proxy toi DNS service `agent:8000`; Docker Compose round-robin giua replicas.

### Exercise 5.5: Test stateless
Test flow:
1. Gui request dau voi `user_id=test` va question `"My name is Alice"`.
2. Kill/restart mot agent instance.
3. Gui request tiep `"What is my name?"`.
4. Response van tra `"Your name is Alice."` vi history doc tu Redis, khong phu thuoc instance cu.

## Part 6: Final Project Summary

Final project da duoc dat tai repo root va `06-lab-complete/`:
- Multi-stage Dockerfile, non-root user, slim base image, healthcheck.
- Docker Compose stack: nginx + scalable agent + Redis.
- API key auth voi `X-API-Key`.
- Redis sliding-window rate limit 10 req/min/user.
- Redis monthly cost guard $10/user/month.
- Health/readiness endpoints.
- Redis-backed conversation history.
- Structured JSON logging.
- Railway/Render config san sang deploy.

## README Discussion Answers

### Section 1
1. Neu push API key hardcoded len GitHub public, key co the bi crawler quet trong vai phut, bi dung trai phep va tao bill ngoai y muon. Cach xu ly la revoke key ngay, rotate secret, kiem tra logs va xoa secret khoi git history neu can.
2. Stateless quan trong khi scale vi request cua cung mot user co the vao bat ky instance nao. Neu state nam trong memory, instance khac se mat conversation/session; dung Redis/DB giup moi replica doc duoc cung state.
3. Dev/prod parity nghia la moi truong local, staging va production cang giong nhau cang tot: cung Python version, dependency, env config, backing services va container runtime de tranh loi "works on my machine".

### Section 2
1. Copy `requirements.txt` va `pip install` truoc `COPY . .` de Docker cache dependency layer; sua source code khong lam cai lai packages.
2. `.dockerignore` nen chua `.env`, `.venv/`, `venv/`, `__pycache__/`, `.git/`, test/cache/local artifacts. `.env` quan trong vi chua secret; `venv/` quan trong vi lam image lon va co package theo OS local.
3. Neu agent can doc file tu disk, mount volume bang Compose, vi du `./data:/app/data:ro` cho read-only input hoac named volume `agent-data:/app/data` cho persistent runtime data.

### Section 3
1. Serverless khong phai luc nao cung tot cho AI agent vi cold start, timeout, connection reuse kem, streaming/websocket kho hon va chi phi co the cao voi workload dai.
2. Cold start la do tre khi platform phai khoi dong container/function moi. UX bi anh huong vi request dau tien cham, dac biet voi agent can load model/config/connection.
3. Nen upgrade tu Railway len Cloud Run khi can autoscaling tot hon, IAM, VPC, observability, traffic splitting, SLO production va CI/CD chuan doanh nghiep.

### Section 4
1. API key phu hop service-to-service hoac demo don gian; JWT phu hop user login/stateless session; OAuth2 phu hop delegated access voi ben thu ba va enterprise SSO.
2. Rate limit nen bat dau thap, vi du 10 req/min/user cho demo AI agent, roi tang theo tier/role va chi phi model.
3. Neu API key bi lo: revoke/rotate key, tim source leak, audit logs, thong bao user lien quan, them anomaly detection va giam quota tam thoi.

## Bonus Point Exercise: CI/CD

Da implement bonus GitHub Actions:
- `.github/workflows/ci-cd.yml`: CI lint, unit test coverage, production readiness, Docker config, Docker build, CD Railway/Render.
- `requirements-dev.txt`: pytest, coverage, ruff, httpx.
- `pyproject.toml`: Ruff config va coverage threshold 75%.
- `tests/test_app.py`: auth, conversation history, rate limiting, health/readiness, metrics/history endpoints.
- `BONUS_CICD.md`: huong dan demo va secrets can set.

Ket qua verify local:
- `ruff check app tests --no-cache`: pass.
- `pytest`: 5 passed, coverage 75.49%, dat nguong 75%.
