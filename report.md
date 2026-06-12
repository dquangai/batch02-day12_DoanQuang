# Báo cáo hoàn thành Day 12 Lab - Deployment AI Agent

**Tên:** Đoàn Minh Quang  
**MHV:** 2A202600757  
**Ngày thực hiện:** 12/06/2026  

---

## 1. Tổng quan

Em đã hoàn thành đầy đủ Day 12 Lab về triển khai AI Agent lên môi trường production. Nội dung đã làm bao gồm:

- Phân tích khác biệt giữa localhost và production.
- Hoàn thiện câu trả lời cho các phần lý thuyết và câu hỏi thảo luận.
- Xây dựng production-ready AI agent.
- Dockerize ứng dụng bằng multi-stage Dockerfile.
- Thiết kế stack Docker Compose gồm Nginx, nhiều agent replicas và Redis.
- Bảo mật API bằng API key.
- Thêm rate limiting, cost guard, health check, readiness check.
- Lưu conversation history trong Redis để hỗ trợ stateless scaling.
- Thêm cấu hình deploy Railway và Render.
- Làm thêm phần bonus CI/CD bằng GitHub Actions.

Các file nộp chính:

- `MISSION_ANSWERS.md`
- `DEPLOYMENT.md`
- `BONUS_CICD.md`
- `app/`
- `06-lab-complete/`
- `Dockerfile`
- `docker-compose.yml`
- `.github/workflows/ci-cd.yml`
- `tests/test_app.py`

---

## 2. Part 1 - Localhost vs Production

Em đã đọc và phân tích code basic trong `01-localhost-vs-production/develop/app.py`, sau đó xác định các anti-pattern chính:

1. Hardcode API key trong source code.
2. Hardcode database URL và password.
3. Log secret ra terminal.
4. Config không đọc từ environment variables.
5. Host/port bị cố định.
6. Bật debug/reload trong môi trường không phù hợp production.
7. Không có health check endpoint.
8. Không có readiness check.
9. Không xử lý graceful shutdown.
10. Không có authentication, rate limit hoặc cost protection.

Em cũng đã so sánh bản basic với bản production và ghi rõ vì sao các điểm sau quan trọng:

- Environment variables.
- Secret management.
- Structured logging.
- Health/readiness checks.
- Graceful shutdown.
- Binding `0.0.0.0` và dùng dynamic `$PORT`.

Nội dung trả lời chi tiết đã được ghi trong `MISSION_ANSWERS.md`.

---

## 3. Part 2 - Docker

Em đã hoàn thành phần Docker gồm:

- Giải thích Dockerfile basic.
- Trả lời câu hỏi về base image, working directory, Docker layer cache, `CMD` và `ENTRYPOINT`.
- So sánh single-stage và multi-stage Docker build.
- Tối ưu Dockerfile production bằng multi-stage build.
- Chạy app bằng non-root user trong container.
- Thêm `HEALTHCHECK`.
- Thêm `.dockerignore` để loại bỏ `.env`, virtualenv, cache và file không cần thiết.

Kết quả Docker image final:

- Image: `batch02-day12_doanquang-agent:latest`
- Size đo được: `381MB`
- Đạt yêu cầu lab: nhỏ hơn `500MB`

---

## 4. Part 3 - Cloud Deployment

Em đã chuẩn bị cấu hình deploy cho Railway và Render:

- `railway.toml`
- `render.yaml`
- `DEPLOYMENT.md`

Các biến môi trường cần set khi deploy:

```bash
ENVIRONMENT=production
AGENT_API_KEY=<strong-secret>
REDIS_URL=<redis-url>
REQUIRE_REDIS=true
RATE_LIMIT_PER_MINUTE=10
MONTHLY_BUDGET_USD=10
ALLOWED_ORIGINS=*
```

Em cũng đã trả lời phần so sánh Railway, Render và Cloud Run trong `MISSION_ANSWERS.md`.

Ghi chú: Public URL thật cần đăng nhập tài khoản Railway hoặc Render để deploy. Repo đã sẵn sàng deploy, còn URL thật sẽ được điền sau khi deploy trên tài khoản cloud.

---

## 5. Part 4 - API Gateway & Security

Em đã triển khai đầy đủ security stack cho final agent:

### API Key Authentication

- File: `app/auth.py`
- Header sử dụng: `X-API-Key`
- Nếu thiếu hoặc sai key: trả `401 Unauthorized`
- Key được đọc từ biến môi trường `AGENT_API_KEY`
- Không hardcode secret trong code

### Rate Limiting

- File: `app/rate_limiter.py`
- Thuật toán: sliding window
- Storage production: Redis sorted set
- Limit: `10 requests/minute/user`
- Khi vượt limit: trả `429 Too Many Requests`
- Có header `Retry-After`

### Cost Guard

- File: `app/cost_guard.py`
- Budget: `$10/month/user`
- Storage production: Redis
- Key Redis: `budget:{user_id}:{YYYY-MM}`
- Khi vượt budget: trả `402 Payment Required`

---

## 6. Part 5 - Scaling & Reliability

Em đã hoàn thiện các yêu cầu reliability:

### Health Check

- Endpoint: `GET /health`
- Trả về status app, version, environment, uptime, request count, storage mode.
- Dùng cho liveness probe.

### Readiness Check

- Endpoint: `GET /ready`
- Kiểm tra app đã ready và Redis có kết nối được hay không.
- Nếu Redis chưa sẵn sàng: trả `503`.
- Khi chạy Docker Compose với Redis: trả `200`.

### Graceful Shutdown

- Sử dụng FastAPI lifespan.
- Log startup và shutdown.
- Có handler cho `SIGTERM` và `SIGINT`.
- Uvicorn dùng `timeout_graceful_shutdown=30`.

### Stateless Design

State không lưu trong memory khi production. Các dữ liệu runtime được đưa vào Redis:

- Conversation history: `history:{user_id}`
- Rate limit window: `rate:{user_id}`
- Monthly budget: `budget:{user_id}:{YYYY-MM}`

Nhờ vậy nhiều agent replicas có thể phục vụ cùng một user mà không mất context.

### Load Balancing

Docker Compose final gồm:

- `nginx`
- `agent`
- `redis`

Có thể scale agent:

```bash
docker compose up --build --scale agent=3
```

Nginx proxy request tới service `agent:8000`, Docker Compose phân phối request giữa các replicas.

---

## 7. Part 6 - Final Production Agent

Em đã xây dựng final production agent ở cả hai vị trí để phù hợp nhiều cách chấm:

1. Repo root:
   - `app/`
   - `Dockerfile`
   - `docker-compose.yml`
   - `requirements.txt`
   - `.env.example`
   - `.dockerignore`
   - `railway.toml`
   - `render.yaml`

2. Folder lab:
   - `06-lab-complete/app/`
   - `06-lab-complete/Dockerfile`
   - `06-lab-complete/docker-compose.yml`
   - `06-lab-complete/nginx.conf`
   - `06-lab-complete/README.md`

Chức năng final agent:

- REST API `POST /ask`.
- Input gồm `user_id` và `question`.
- Có conversation history.
- Có câu trả lời theo context, ví dụ nhớ câu `"My name is Alice"` và trả lời được `"What is my name?"`.
- API key authentication.
- Rate limiting.
- Cost guard.
- Health/readiness endpoints.
- Metrics endpoint.
- Structured JSON logging.
- Security headers.
- Redis-backed state.

---

## 8. Bonus - CI/CD Pipeline

Em đã làm thêm phần bonus trong `CODE_LAB.md`:

> Tạo CI/CD pipeline bằng GitHub Actions để deploy app lên Railway hoặc Render. CI có lint, unit test coverage. CD có deploy. Demo để cộng điểm.

Các file đã thêm:

- `.github/workflows/ci-cd.yml`
- `requirements-dev.txt`
- `pyproject.toml`
- `tests/test_app.py`
- `BONUS_CICD.md`

### CI Stages

Pipeline GitHub Actions thực hiện:

1. Checkout source code.
2. Setup Python 3.11.
3. Start Redis service.
4. Install dependencies.
5. Run lint bằng Ruff.
6. Run unit tests bằng Pytest.
7. Run coverage check.
8. Run production readiness checker.
9. Validate Docker Compose config.
10. Build Docker image.

### CD Stages

Pipeline hỗ trợ deploy theo biến GitHub `DEPLOY_TARGET`:

- Nếu `DEPLOY_TARGET=railway`: deploy bằng Railway CLI.
- Nếu `DEPLOY_TARGET=render`: gọi Render Deploy Hook.

Secrets cần set:

- Railway:
  - `RAILWAY_TOKEN`
  - `RAILWAY_SERVICE`

- Render:
  - `RENDER_DEPLOY_HOOK_URL`

---

## 9. Unit Tests & Coverage

Em đã thêm test trong `tests/test_app.py`:

1. Test thiếu API key trả `401`.
2. Test agent giữ conversation history.
3. Test hỏi `"What is my name?"` trả lời được `"Alice"`.
4. Test rate limit: 10 request đầu `200`, request thứ 11 trả `429`.
5. Test `/health` và `/ready`.
6. Test `/`, `/metrics`, `/history/{user_id}`, delete history.

Kết quả local:

```text
5 passed
Coverage: 75.49%
Coverage threshold: 75%
```

---

## 10. Kết quả kiểm thử

Các lệnh đã chạy và kết quả:

### Ruff lint

```bash
ruff check app tests --no-cache
```

Kết quả:

```text
All checks passed!
```

### Pytest coverage

```bash
pytest
```

Kết quả:

```text
5 passed
Required test coverage of 75% reached
Total coverage: 75.49%
```

### Production readiness checker

```bash
python 06-lab-complete/check_production_ready.py
```

Kết quả:

```text
20/20 checks passed (100%)
PRODUCTION READY
```

### Docker Compose config

```bash
docker compose config
```

Kết quả: config hợp lệ.

### Docker stack local

Stack đã chạy thành công với:

- 3 agent replicas healthy.
- 1 Redis container healthy.
- 1 Nginx container running.
- Nginx expose local qua port `8080`.

Kết quả endpoint:

- `GET /health`: `200`
- `GET /ready`: `200`
- `POST /ask` không có key: `401`
- `POST /ask` có key: `200`
- Rate limit: request thứ 11 trở đi trả `429`
- Conversation history: hỏi lại tên trả về `Alice`

Docker image final:

```text
batch02-day12_doanquang-agent:latest 381MB
```

---

## 11. Các file quan trọng

### Source code

- `app/main.py`
- `app/config.py`
- `app/auth.py`
- `app/rate_limiter.py`
- `app/cost_guard.py`
- `utils/mock_llm.py`

### Docker & deployment

- `Dockerfile`
- `docker-compose.yml`
- `nginx.conf`
- `.dockerignore`
- `.env.example`
- `railway.toml`
- `render.yaml`

### Documentation

- `MISSION_ANSWERS.md`
- `DEPLOYMENT.md`
- `BONUS_CICD.md`
- `report.md`

### CI/CD & tests

- `.github/workflows/ci-cd.yml`
- `requirements-dev.txt`
- `pyproject.toml`
- `tests/test_app.py`

---

## 12. Kết luận

Em đã hoàn thành toàn bộ Day 12 Lab và phần bonus. Final project đáp ứng các tiêu chí chính:

- Production-ready FastAPI agent.
- Docker multi-stage image dưới 500MB.
- API key authentication.
- Redis-backed rate limiting.
- Redis-backed monthly cost guard.
- Redis-backed conversation history.
- Health/readiness checks.
- Stateless design.
- Load balancing với Nginx.
- Railway/Render deployment config.
- GitHub Actions CI/CD bonus.
- Unit test coverage đạt yêu cầu.

Repo hiện đã sẵn sàng để nộp và deploy lên Railway hoặc Render khi có tài khoản cloud.
