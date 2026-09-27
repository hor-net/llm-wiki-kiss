# Security Policy

## Supported versions

The `main` branch and the latest public release receive security fixes.
Previous versions may not receive backports.

## Reporting a vulnerability

Use the **Report a vulnerability** private form on GitHub only:

<https://github.com/hor-net/llm-wiki-kiss/security/advisories/new>

Do not open public issues containing vulnerabilities, tokens, certificates,
private paths or wiki pages. Provide a minimal reproduction with dummy data.

## Threat model

llm-wiki-kiss is intentionally single-tenant:

- one process serves a single `WIKI_ROOT`;
- different customers must use different processes, users and roots;
- MCP stdio and the CLI inherit the permissions of the local user;
- REST is limited to the loopback by the official scripts;
- network MCP requires TLS and a Bearer token;
- without a token the HTTP layer stays fail-closed;
- coordinated writes only work when they go through `WikiStorage`.

The project does not protect data from a host administrator, from a process
with the same filesystem permissions, or from scripts that access the root
directly.

## Secret handling

- `.wiki-kiss.env` and generated skills contain real credentials.
- Never commit `.wiki-kiss.env`, TLS keys or `.agents/skills/generated/`.
- Use separate roots and distinct tokens for different installations.
- After a possible exposure run `scripts/configure.sh --rotate-token` and
  regenerate only the still-authorised skills.
- Transmit the Bearer token only over HTTPS.
- For public services use trusted certificates and restrict access at the
  firewall or reverse-proxy level as well.

## Dependencies and checks

Pull requests run tests, Ruff, Bash validation and Gitleaks. Dependencies
are monitored via Dependabot.
