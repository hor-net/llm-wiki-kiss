# Shared Secrets Vault

Canonical reference for the internal secrets vault where API tokens,
database credentials and signing keys are stored.

## Endpoints

- API: `https://vault.example.internal/v1`
- Web UI: `https://vault.example.internal/`

## Authentication

- Service tokens: short-lived (1 hour), JWT, fetched through the
  internal SSO.
- Human access: SSO + hardware key required.

## Paths

- Production services: `services/<service-name>/<env>`.
- Shared credentials: `shared/<team>/<credential>`.

## Common operations

```bash
# Read a service token (never copy the value into the wiki body)
vault read services/crm/prod

# Rotate a credential
vault rotate services/crm/prod --reason "annual rotation"
```

## Related pages

- [Policies: secrets handling](../policies/secrets.md)
