# Data handling

Policy describing how customer and company data must be handled by every
service and agent.

## Classification

- **Public**: marketing content, public documentation.
- **Internal**: processes, runbooks, internal contacts.
- **Confidential**: customer data, business metrics, contracts.
- **Restricted**: credentials, personal data, financial information.

## Rules

- Never store confidential or restricted data in the wiki. Use the
  vault instead.
- Mask emails, phone numbers and identifiers when sharing logs.
- Delete temporary artefacts containing confidential data as soon as
  the work is done.

## Related pages

- [Secrets handling](secrets.md)
- [Shared services](../services/)
