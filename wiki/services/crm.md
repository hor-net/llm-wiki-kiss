# Internal CRM

Canonical reference for the internal customer relationship management
service used by sales, support and marketing agents.

## Endpoints

- Production: `https://crm.example.internal/api/v1`
- Staging: `https://crm-staging.example.internal/api/v1`

## Authentication

- Method: OAuth2 client credentials.
- Client ID and secret live in the shared secrets vault under
  `services/crm/prod`.
- Request scope: `crm.read` for read-only access, `crm.write` for write
  access.

## Rate limits

- 60 requests per minute per client.
- Burst up to 120 requests for no more than 10 seconds.

## Common error codes

| Code | Meaning |
|------|---------|
| 401  | Invalid or expired token |
| 403  | Missing scope |
| 404  | Customer not found |
| 429  | Rate limit exceeded, retry after `Retry-After` seconds |
| 5xx  | Server-side issue; escalate via the on-call channel |

## On-call

- Channel: `#oncall-crm` on the internal chat.
- Escalation: follow `policies/on-call.md`.

## Runbooks

- Replay queue: `https://runbooks.example.internal/crm/replay`
- Token rotation: `https://runbooks.example.internal/crm/rotate-token`

## Related pages

- [Policies: data handling](../policies/data-handling.md)
- [Policies: on-call rotation](../policies/on-call.md)
