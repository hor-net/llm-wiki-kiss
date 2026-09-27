# Secrets handling

Policy describing how API tokens, signing keys and passwords must be
handled across the company.

## Storage

- All secrets live in the shared vault (`services/vault.md`).
- Local `.env` files are tolerated only for development and must not be
  committed.

## Sharing

- Share secrets out-of-band (password manager, encrypted channels).
- Never put real secrets in chat, tickets or the wiki.
- Use placeholders like `<api-token>` in documentation.

## Rotation

- Rotate at least every 90 days.
- Rotate immediately on:
  - employee offboarding;
  - suspected exposure;
  - end of an engagement with a third party.
- Document rotations in `logs/<YYYY-MM-DD>.md`.

## Related pages

- [Shared secrets vault](../services/vault.md)
- [Data handling](data-handling.md)
