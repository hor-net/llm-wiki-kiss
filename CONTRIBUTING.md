# Contributing to llm-wiki-kiss

Thank you for your interest. The project favours small, filesystem-oriented,
easy-to-understand solutions.

## Before you start

- Use the GitHub issue templates for bugs and feature requests.
- Follow [`SECURITY.md`](SECURITY.md) for vulnerabilities, never a public
  issue.
- Do not attach tokens, `.wiki-kiss.env`, generated skills or private wikis.

## Development environment

```bash
git clone https://github.com/hor-net/llm-wiki-kiss.git
cd llm-wiki-kiss
scripts/setup.sh --with-dev --root ./wiki --https off
```

The setup generates a local token. Do not commit it.

## Mandatory checks

```bash
python -m pytest -q
python -m ruff check wiki_core mcp_server rest_api.py tests
find scripts -type f -name '*.sh' -print0 | xargs -0 bash -n
python tests/smoke_mcp.py
python tests/smoke_mcp_http.py
```

## Architectural rules

1. One wiki per process; no multi-tenant routing.
2. No database or mandatory external services.
3. All mutations go through `WikiStorage`.
4. Reads are lock-free; writes are atomic and coordinated.
5. No remote MCP access without TLS and authentication.
6. REST is limited to the loopback.
7. Markdown files must remain readable without the software.
8. Tests are mandatory for storage, security, CLI and operational scripts.

## Style

- Python 3.10+.
- Ruff as configured in `pyproject.toml`.
- Wiki page filenames in `kebab-case`.
- Code identifiers stay in English; documentation may be translated.

## Pull requests

Keep PRs focused. Describe:

- the problem solved;
- the previous and new behaviour;
- the tests executed;
- the implications for security, compatibility and existing data.

By contributing you accept that the code is distributed under the
AGPL-3.0-or-later licence of the project.
