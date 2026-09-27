---
name: "wiki-kiss-operator"
description: "Gestisce l'installazione, l'avvio e la configurazione di un'istanza wiki KISS (server MCP + REST). Invocare quando l'utente chiede di installare, avviare, fermare, integrare o fare troubleshooting del sistema wiki KISS."
---

# Wiki KISS — Operatore

Questa skill spiega a un agente AI (Claude Code, Claude Desktop, Open Cloud,
...) come **installare, configurare e operare** un'istanza del progetto
wiki-kiss, compresa l'integrazione con i client MCP.

## Quando invocare questa skill

- L'utente chiede di "installare il wiki", "configurare il server MCP",
  "far partire la REST", "fermare i servizi", "controllare lo stato".
- L'utente chiede come integrare il wiki con Claude Code, Claude Desktop,
  Open Cloud, Perplexity o un altro client MCP-compatibile.
- L'utente segnala un problema (es. "il server non parte", "la porta è
  occupata", "i tool non compaiono nel client").
- L'utente vuole aggiungere il wiki a un nuovo client o ambiente.

Non invocare se:
- L'utente vuole solo leggere o scrivere contenuti del wiki (usa
  `wiki-kiss-bridge`).

## Stack del progetto

- **Storage**: file `.md`/`.html` in una cartella wiki (default `./wiki`).
- **Server MCP**: Python ≥ 3.10, SDK `mcp`, trasporto stdio.
- **API REST**: FastAPI + Uvicorn su `127.0.0.1:8765` (default).
- **Wrapper**: script shell in `scripts/`.

## Installazione

Eseguire, dall'interno della cartella del progetto:

```bash
# Installa, sceglie la root, genera il token e lascia HTTPS spento
scripts/setup.sh --root ~/wiki-privato --https off

# Crea venv, dipendenze base + dev (pytest, ruff)
scripts/setup.sh --with-dev --root ~/wiki-privato --https off

# Ricrea il venv da zero
scripts/setup.sh --recreate
```

Lo script:
- Rileva automaticamente un interprete Python 3.10+ disponibile.
- Crea `.venv/` se non esiste.
- Installa pacchetti da `requirements.txt` (e `requirements-dev.txt` con
  `--with-dev`).
- Verifica l'importazione dei moduli `wiki_core`, `mcp_server`, `rest_api`.
- Installa i comandi `wiki-kiss` e `wiki-kiss-mcp`.
- Genera `.wiki-kiss.env` (modo 0600) e restituisce il token configurato.

## Trasporti disponibili

Il progetto espone **tre trasporti** per parlare con i 5 tool MCP
(`list_pages`, `read_page`, `search`, `write_page`, `append_note`):

| Trasporto | Porta | Uso |
| --- | --- | --- |
| **stdio** | — | Client MCP locali (Claude Code, Claude Desktop, Open Cloud installato). Il client lancia il server come sottoprocesso. |
| **Streamable HTTP su HTTPS** | 8766 (default) | Client MCP remoti. TLS e Bearer token sono obbligatori. |
| **REST/HTTP loopback** | 8765 (default) | Client HTTP locali; stesso Bearer token, nessuna esposizione remota. |

### Quando usare quale

- **Stdio**: agenti che girano sulla stessa macchina o via SSH/tunnel.
- **Streamable HTTP su HTTPS**: agenti MCP-aware remoti.
- **REST**: client locali che non parlano MCP.

## Avvio e arresto dei servizi

### REST API (uvicorn)

```bash
# In background (default: 127.0.0.1:8765)
scripts/start-rest.sh

# Porta personalizzata; l'host deve restare loopback
scripts/start-rest.sh --host 127.0.0.1 --port 9000

# In foreground (Ctrl-C per fermare)
scripts/start-rest.sh --foreground

# Auto-reload in sviluppo
scripts/start-rest.sh --reload
```

Endpoint principali:
- `GET /health` — health check.
- `GET /stats` — statistiche wiki.
- `GET /pages?subdir=...` — lista pagine.
- `GET /pages/{path:path}` — lettura.
- `PUT /pages/{path:path}` — scrittura.
- `GET /search?q=...` — ricerca.
- `POST /notes` — append nota.
- `GET /docs` — OpenAPI interattivo.

### Server MCP (stdio)

Il server MCP **non** gira come demone: viene avviato dal client come
sottoprocesso. Per test manuali:

```bash
# Avvio in foreground (Ctrl-C o EOF per uscire)
scripts/start-mcp.sh
```

### Server MCP Streamable HTTPS (per client remoti)

Configura e avvia con TLS e Bearer obbligatori:

```bash
scripts/configure.sh --https on \
  --host 0.0.0.0 \
  --url https://wiki.example.com/mcp \
  --cert /percorso/fullchain.pem \
  --key /percorso/privkey.pem
```

Spegnimento immediato, senza interrompere CLI o MCP stdio:

```bash
scripts/configure.sh --https off
```

Non esiste una modalità MCP remota senza autenticazione o senza TLS.

### Variabili d'ambiente riconosciute

| Variabile        | Default     | Effetto                          |
| ---------------- | ----------- | -------------------------------- |
| `WIKI_ROOT`      | `./wiki`    | Cartella del wiki                |
| `WIKI_LOG_LEVEL` | `INFO`      | Livello di log Python            |
| `WIKI_MCP_TOKEN` | (obbligatorio HTTP) | Token unico MCP HTTPS/REST |
| `WIKI_HTTPS_ENABLED` | `0` | Abilita MCP HTTPS |
| `WIKI_HTTP_HOST` | `127.0.0.1` | Host del server MCP HTTPS |
| `WIKI_HTTP_PORT` | `8766` | Porta del server MCP HTTPS |
| `WIKI_MCP_URL` | (unset) | URL pubblica `https://.../mcp` |
| `WIKI_TLS_CERT` | (unset) | Certificato PEM |
| `WIKI_TLS_KEY` | (unset) | Chiave privata PEM |
| `DEFAULT_HOST`   | `127.0.0.1` | Host REST (per `start-rest.sh`)  |
| `DEFAULT_PORT`   | `8765`      | Porta REST (per `start-rest.sh`) |
| `NO_COLOR`       | (unset)     | Disabilita colori nell'output    |

### Stato e stop

```bash
# Stato corrente (servizi, log, pid)
scripts/status.sh

# Fermare uno o più servizi
scripts/stop.sh mcp
scripts/stop.sh mcp-http
scripts/stop.sh rest
scripts/stop.sh all
```

`var/run/*.pid` contiene i PID, `var/log/*.log` i log.

## Integrazione con i client MCP

### Client locali (stdio)

Per generare la configurazione MCP pronta da incollare:

```bash
scripts/install-mcp-client.sh --client claude-code
scripts/install-mcp-client.sh --client claude-desktop
scripts/install-mcp-client.sh --client generic

# Scrive su file (es. .mcp.json per Claude Code)
scripts/install-mcp-client.sh --client claude-code --out .mcp.json
```

Output tipico (per Claude Code / Claude Desktop):

```json
{
  "mcpServers": {
    "wiki-kiss": {
      "command": "/percorso/al/progetto/.venv/bin/python",
      "args": ["-m", "mcp_server", "--root", "/percorso/al/progetto/wiki"],
      "cwd": "/percorso/al/progetto",
      "env": {
        "WIKI_ROOT": "/percorso/al/progetto/wiki",
        "WIKI_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Dove mettere il frammento:

| Client         | File di configurazione                                              |
| -------------- | ------------------------------------------------------------------- |
| Claude Code    | `.mcp.json` nella root del progetto (o globale `~/.claude.json`)     |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json`   |
| Open Cloud     | sezione `mcpServers` nelle impostazioni del client                  |
| Perplexity     | sezione MCP delle impostazioni del client (dove supportato)         |

Dopo aver salvato la configurazione, **riavviare il client** perché
ricarichi l'elenco dei server MCP.

### Client remoti (Streamable HTTP)

Per Open Cloud aggiornato o altri client MCP-aware che supportano
Streamable HTTP transport:

- URL: `https://wiki.example.com/mcp`
- Header: `Authorization: Bearer <token>`
- Header: `Accept: application/json, text/event-stream` (gestito dal client)
- Versione protocollo: `2025-06-18`

## Onboarding degli agenti

Genera una skill personalizzata con URL/path e credenziali protette:

```bash
scripts/onboard-agent.sh --name customer-wiki --label "Customer Wiki"
```

La skill viene creata per default in `.agents/skills/generated/`, ignorata da
Git. Dopo la rotazione del token rigenerarla con `--force`. Vedi
`ONBOARDING.md`.

## Test e qualità

```bash
# Esegue la suite pytest
scripts/run-tests.sh -q

# Smoke test del server MCP via stdio
.venv/bin/python tests/smoke_mcp.py

# Lint
.venv/bin/ruff check wiki_core mcp_server rest_api.py tests
```

## Troubleshooting

### Il client MCP non vede il tool

1. Verifica che il venv sia attivo e che `mcp_server` si importi:
   `scripts/status.sh` → controlla che il venv sia rilevato.
2. Verifica manualmente: `scripts/start-mcp.sh < /dev/null` (deve avviarsi
   e rimanere in attesa senza errori).
3. Riavvia il client MCP dopo aver salvato la configurazione.
4. Controlla il percorso del venv: deve essere **assoluto** nella config MCP.

### La porta REST è occupata

```bash
lsof -iTCP:8765 -sTCP:LISTEN
# Uccidi il processo o scegli un'altra porta
scripts/start-rest.sh --port 9000
```

### Errori `InvalidPathError` o `PageNotFoundError`

- Il percorso contiene `..` o caratteri non ammessi: normalizzalo.
- La pagina non esiste: usa `list_pages` o `search` per trovarla.

### Test MCP falliti in `pytest`

```bash
.venv/bin/python -m pytest -q
```

Se solo i test MCP falliscono, verifica che `mcp` sia installato
nel venv: `scripts/setup.sh --with-dev`.

## Operazioni frequenti

- **Aggiungere un nuovo client stdio**: `scripts/install-mcp-client.sh` e
  incolla la config.
- **Aggiungere un nuovo client HTTP (cloud)**: condividi URL e token
  Bearer. Il client si connette a `https://.../mcp` con
  `Authorization: Bearer <token>`.
- **Cambiare root del wiki**: `scripts/configure.sh --root /nuova/root`.
- **Ruotare il token**: `scripts/configure.sh --rotate-token`, poi rigenera le
  skill autorizzate con `scripts/onboard-agent.sh --force`.
- **Backup**: `tar czf wiki-$(date +%F).tgz wiki/` (tutto è testo).
- **Migrazione**: copia la cartella `wiki/` su un'altra macchina e
  riavvia i servizi: nessun database di cui preoccuparsi.

## Filosofia operativa (KISS)

- Niente database. Niente CMS. Versiona con Git.
- Un solo servizio REST locale opzionale. Un server MCP stdio. Un server MCP HTTPS opzionale.
- I contenuti sono leggibili anche con `cat` o un editor Markdown.
- Le decisioni importanti vanno in `wiki/decisions/` come ADR.
