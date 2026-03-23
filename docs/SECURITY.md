# Production Security Configuration

This document explains the security features added to ByteWallet AI for production deployment.

## Overview

The following security features have been implemented:

1. **CORS Origin Control** — Configurable allowed origins (no more `*` wildcard in production)
2. **API Key Authentication** — Simple but effective API key validation
3. **Rate Limiting** — Per-client request throttling
4. **Async Federated Learning** — Replaced `threading.Lock` with `asyncio.Lock` for FastAPI-native concurrency

---

## Configuration

All settings are controlled via environment variables:

### 1. CORS Origins (`CORS_ORIGINS`)

**Development (default):**
```bash
CORS_ORIGINS=*
```

**Production:**
```bash
CORS_ORIGINS=https://wallet.example.com,https://app.example.com
```

### 2. API Key Authentication (`API_KEYS`)

**Development (default):**
```bash
API_KEYS=              # Empty = auth disabled (dev mode)
```

**Production (REQUIRED):**
```bash
API_KEYS=prod-key-abc123,prod-key-xyz789
```

When set, all `/v1/*` endpoints require the `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/v1/predict-burn-rate \
  -H "X-API-Key: prod-key-abc123" \
  -H "Content-Type: application/json" \
  -d @tests/sample_kukue_request.json
```

### 3. Rate Limiting (`RATE_LIMIT`)

**Default:**
```bash
RATE_LIMIT=100/minute
```

**Available periods:**
- `second` (requests per second)
- `minute` (requests per minute) 
- `hour` (requests per hour)
- `day` (requests per day)

**Examples:**
```bash
RATE_LIMIT=10/second      # Burst traffic handling
RATE_LIMIT=1000/hour      # Standard tier
RATE_LIMIT=10000/day      # Generous daily limit
```

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum allowed requests
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Window`: Window duration in seconds

---

## Security Implementation Details

### API Authentication (`app/security.py`)

- **Dependency-based:** Uses FastAPI's `Depends()` system for clean route protection
- **Graceful fallback:** If `API_KEYS` is empty, auth is disabled (safe for dev)
- **Header-based:** Uses standard `X-API-Key` header
- **Multi-key support:** Supports multiple valid keys (comma-separated)

### Rate Limiting (`app/security.py`)

- **Client identification:** Uses IP + API key for unique client tracking
- **In-memory storage:** Fast, no external dependencies (Redis recommended for scale)
- **Auto-cleanup:** Removes expired entries periodically
- **Health check exemption:** `/` and `/health` endpoints are not rate-limited

### CORS (`app/config.py` + `app/main.py`)

- **Environment-driven:** Origins loaded from config, not hardcoded
- **Parsing helper:** `cors_origins_list` property handles comma-separated values
- **Backwards compatible:** Still supports `"*"` for development

### Async Federated Server (`ml/federated/server.py`)

- **New `AsyncFedAvgServer`:** Uses `asyncio.Lock` instead of `threading.Lock`
- **Backwards compatible:** `FedAvgServer` class wraps async version for legacy sync code
- **Event loop safe:** Handles both sync and async contexts correctly

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Set `CORS_ORIGINS` to your actual domain(s), not `*`
- [ ] Generate strong API keys (use `openssl rand -hex 32`)
- [ ] Set `API_KEYS` with at least one production key
- [ ] Review `RATE_LIMIT` based on expected traffic
- [ ] Set `AI_DEFAULT_MODE` appropriately (`rules_only` is safest)
- [ ] Configure `OLLAMA_BASE_URL` if using external LLM
- [ ] Run tests: `python -m pytest tests/ -v`

---

## Security Considerations

### Known Limitations

1. **In-memory rate limiter:** For high-traffic production, replace with Redis-based solution
2. **API key storage:** Keys are in-memory only; rotate via `API_KEYS` env var updates
3. **No audit logging:** Request logging should be added for compliance requirements
4. **No HTTPS enforcement:** Configure at reverse proxy (nginx, cloud load balancer)

### Recommended Additions for Enterprise

1. **JWT tokens** — Replace API keys with JWT for fine-grained user auth
2. **Request signing** — Sign requests with HMAC for integrity verification
3. **IP allowlisting** — Restrict access to known IP ranges
4. **Audit logging** — Log all predictions and federated updates
5. **Redis rate limiter** — Shared state across multiple app instances
6. **WAF rules** — CloudFlare/AWS WAF for DDoS protection

---

## Testing with Authentication

When `API_KEYS` is set, tests automatically use the first key:

```python
# tests/test_api.py automatically handles this
headers = get_test_headers()  # Includes X-API-Key if configured
```

To run tests without auth:
```bash
unset API_KEYS
python -m pytest tests/ -v
```

To run tests with auth:
```bash
export API_KEYS="test-key-12345"
python -m pytest tests/ -v
```

---

## Migration from Previous Versions

If upgrading from a version without security:

1. **No breaking changes** — If `API_KEYS` is not set, everything works as before
2. **Optional opt-in** — Add security settings when ready
3. **Gradual rollout** — Can add auth to staging before production

---

## Support

For security-related issues:
1. Check `app/security.py` implementation
2. Review FastAPI security docs: https://fastapi.tiangolo.com/tutorial/security/
3. Check rate limiting patterns: https://slowapi.readthedocs.io/
