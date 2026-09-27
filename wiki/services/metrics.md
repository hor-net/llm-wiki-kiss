# Metrics API

Canonical reference for the internal metrics ingestion and query API used
by all company services.

## Endpoints

- Ingest: `https://metrics.example.internal/v1/ingest`
- Query: `https://metrics.example.internal/v1/query`
- Dashboards: `https://grafana.example.internal/d/metrics`

## Authentication

- Bearer token issued by the shared secrets vault.
- Tokens are scoped per service (for example `metrics.write` for agents
  that publish data, `metrics.read` for agents that only query).
- Tokens expire every 90 days; rotate them via the vault.

## Rate limits

- Ingest: 1000 events per second per token.
- Query: 30 queries per minute per token.

## Common error codes

| Code | Meaning |
|------|---------|
| 400  | Malformed payload or query |
| 401  | Invalid or expired token |
| 413  | Payload too large (> 1 MiB) |
| 429  | Rate limit exceeded |
| 503  | Backend unavailable, retry with backoff |

## On-call

- Channel: `#oncall-metrics`

## Related pages

- [Policies: on-call rotation](../policies/on-call.md)
