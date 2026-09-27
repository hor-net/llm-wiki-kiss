# Pubblicare una release GitHub

Il progetto viene distribuito come repository Git clonabile. Non sono richiesti
Docker o pubblicazione PyPI.

## Checklist

1. Verifica che il wiki di esempio non contenga dati privati.
2. Verifica che non siano tracciati `.wiki-kiss.env`, skill generate, token o
   chiavi TLS.
3. Aggiorna versione in `pyproject.toml`, API REST e `CHANGELOG.md`.
4. Esegui:

   ```bash
   python -m pytest -q
   python -m ruff check wiki_core mcp_server rest_api.py tests
   find scripts -type f -name '*.sh' -print0 | xargs -0 bash -n
   python tests/smoke_mcp.py
   python tests/smoke_mcp_http.py
   ```

5. Prova da clone pulito:

   ```bash
   scripts/setup.sh --with-dev --root ./wiki --https off
   scripts/wiki.sh list
   scripts/install-mcp-client.sh --client generic
   scripts/onboard-agent.sh --name release-smoke --mode local
   ```

6. Controlla che le GitHub Actions siano verdi.
7. Rivedi il diff e crea commit coerenti.
8. Crea un tag annotato e pubblicalo:

   ```bash
   git tag -a v0.3.0 -m "llm-wiki-kiss v0.3.0"
   git push origin main
   git push origin v0.3.0
   ```

9. Crea la GitHub Release usando la sezione corrispondente di `CHANGELOG.md`.

Non creare il tag finché il working tree non è pulito e la CI non è verde.
