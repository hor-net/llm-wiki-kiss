# Contribuire a llm-wiki-kiss

Grazie per il contributo. Il progetto privilegia soluzioni piccole,
filesystem-oriented e comprensibili.

## Prima di iniziare

- Per bug e funzionalità usa i template GitHub.
- Per vulnerabilità segui [`SECURITY.md`](SECURITY.md), mai issue pubbliche.
- Non allegare token, `.wiki-kiss.env`, skill generate o wiki privati.

## Ambiente di sviluppo

```bash
git clone https://github.com/hor-net/llm-wiki-kiss.git
cd llm-wiki-kiss
scripts/setup.sh --with-dev --root ./wiki --https off
```

Il setup genera un token locale. Non commetterlo.

## Verifiche obbligatorie

```bash
python -m pytest -q
python -m ruff check wiki_core mcp_server rest_api.py tests
find scripts -type f -name '*.sh' -print0 | xargs -0 bash -n
python tests/smoke_mcp.py
python tests/smoke_mcp_http.py
```

## Regole architetturali

1. Un solo wiki per processo; niente routing multi-tenant.
2. Niente database o servizi esterni obbligatori.
3. Tutte le mutazioni passano da `WikiStorage`.
4. Letture lock-free, scritture atomiche e coordinate.
5. Niente accesso MCP remoto senza TLS e autenticazione.
6. REST limitata al loopback.
7. File Markdown leggibili anche senza il software.
8. Test obbligatori per storage, sicurezza, CLI e script operativi.

## Stile

- Python 3.10+.
- Ruff secondo `pyproject.toml`.
- Nomi pagina wiki in `kebab-case`.
- Testo e documentazione possono essere in italiano; API e nomi pubblici devono
  restare chiari e stabili.

## Pull request

Mantieni le PR focalizzate. Descrivi:

- problema risolto;
- comportamento precedente e nuovo;
- test eseguiti;
- implicazioni per sicurezza, compatibilità e dati esistenti.

Contribuendo accetti che il codice sia distribuito secondo la licenza
AGPL-3.0-or-later del progetto.
