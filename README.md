# llm-wiki-kiss

> **Un wiki KISS self-hosted per agenti AI** — file Markdown su filesystem,
> accesso uniforme via **MCP** (stdio) e fallback **REST/HTTP** opzionale.
> Stesso contenuto, qualunque sia l'agente: Claude Code, Open Cloud,
> Perplexity, script Python, browser.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-8A2BE2)](https://modelcontextprotocol.io)
[![Made with KISS](https://img.shields.io/badge/principle-KISS-ff69b4)](#filosofia)

---

## Perché

Le conoscenze condivise tra agenti AI oggi vivono sparse: in tool, in
notebook, in conversazioni che si perdono. Questo progetto offre una
**base di conoscenza persistente, portabile e controllabile al 100%**:

- 📁 File `.md` o `.html` leggibili con qualsiasi editor
- 🧠 Un **server MCP** standardizzato che qualunque agente può usare
- 🌐 Una **REST API** minimale come fallback per i client che non supportano MCP
- 🪶 Nessun database, nessun CMS, versionamento con Git
- 🔌 Funziona ovunque: locale, server privato, container, Codespace

## Indice

- [Caratteristiche](#caratteristiche)
- [Architettura](#architettura)
- [Quick start (5 minuti)](#quick-start-5-minuti)
- [Installazione manuale](#installazione-manuale)
- [I 5 tool MCP](#i-5-tool-mcp)
- [API REST](#api-rest)
- [Configurazione del client MCP](#configurazione-del-client-mcp)
- [Skill per agenti](#skill-per-agenti)
- [Script di gestione](#script-di-gestione)
- [Test e qualità](#test-e-qualità)
- [Struttura del wiki](#struttura-del-wiki)
- [Filosofia](#filosofia)
- [Licenza](#licenza)

## Caratteristiche

- **Storage filesystem**: una cartella con file Markdown e link relativi.
- **Server MCP** con cinque tool: `list_pages`, `read_page`, `search`,
  `write_page`, `append_note`.
- **API REST** FastAPI specchio dei tool MCP, con OpenAPI su `/docs`.
- **Sicurezza base**: validazione percorsi (no `..`, no NUL), limite 2 MiB
  per pagina, scope limitato alla root del wiki.
- **Skill SKILL.md** pronte per essere caricate da agenti compatibili
  (TRAE, Claude Code, …).
- **Script shell** che gestiscono venv, dipendenze, port checking, pid e log.

## Architettura

```
llm-wiki-kiss/
├── wiki/                  # dati Markdown (il tuo wiki)
│   ├── index.md
│   ├── projects/  notes/  decisions/  references/  assets/  logs/
├── wiki_core/             # logica filesystem (WikiStorage, validazione, search)
├── mcp_server/            # server MCP stdio (5 tool)
├── rest_api.py            # fallback HTTP FastAPI
├── scripts/               # wrapper shell (setup, start, stop, status, deploy)
├── tests/                 # pytest + smoke test MCP via stdio
├── .trae/skills/          # SKILL.md per agenti AI
├── pyproject.toml, requirements*.txt, .env.example, .gitignore
├── LICENSE                # MIT
└── README.md
```

## Quick start (5 minuti)

Prerequisito: **Python 3.10+**.

```bash
# 1. Clona e configura
git clone https://github.com/hor-net/llm-wiki-kiss.git
cd llm-wiki-kiss

# 2. Crea venv e installa dipendenze (+ dev)
scripts/setup.sh --with-dev

# 3. Avvia la REST API (default: 127.0.0.1:8765)
scripts/start-rest.sh

# 4. Verifica
scripts/status.sh
curl http://127.0.0.1:8765/health
open http://127.0.0.1:8765/docs
```

Per integrare con Claude Code / Claude Desktop / Open Cloud / Perplexity:

```bash
scripts/install-mcp-client.sh --client claude-code
```

Copia l'output nel file di configurazione del tuo client e riavvialo.

## Installazione manuale

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # + requirements-dev.txt per dev
```

## I 5 tool MCP

| Tool          | Cosa fa                                                        |
| ------------- | -------------------------------------------------------------- |
| `list_pages`  | Elenca pagine, opzionale `subdir`.                             |
| `read_page`   | Legge il contenuto di una pagina dato il percorso.             |
| `search`      | Full-text case-insensitive con snippet e numero di riga.       |
| `write_page`  | Crea o sovrascrive una pagina. Aggiunge `.md` se manca.        |
| `append_note` | Aggiunge testo. Di default accoda al log `logs/YYYY-MM-DD.md`. |

Tutti i percorsi sono **relativi** alla root del wiki e separati da `/`.

### Esempi rapidi

```json
// list_pages
{ "subdir": "notes" }

// read_page
{ "path": "notes/esempio-nota.md" }

// search
{ "query": "MCP", "max_results": 20 }

// write_page
{ "path": "notes/idea.md", "content": "# Idea\n\n...", "overwrite": false }

// append_note (path opzionale: default = log del giorno)
{ "content": "Refactor iniziato.", "heading": "Refactor" }
```

## API REST

| Metodo | Endpoint                     | Descrizione                       |
| ------ | ---------------------------- | --------------------------------- |
| GET    | `/health`                    | Health check                      |
| GET    | `/stats`                     | Statistiche wiki                  |
| GET    | `/pages?subdir=...`          | Lista pagine                      |
| GET    | `/pages/{path:path}`         | Leggi pagina                      |
| PUT    | `/pages/{path:path}`         | Scrivi pagina                     |
| GET    | `/search?q=...`              | Ricerca full-text                 |
| POST   | `/notes`                     | Append nota (default log giornaliero) |
| GET    | `/docs`                      | OpenAPI interattivo (Swagger UI)  |

## Configurazione del client MCP

Esempio di frammento per Claude Code / Claude Desktop / Open Cloud /
Perplexity (generato da `scripts/install-mcp-client.sh`):

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

| Client         | File di configurazione                                              |
| -------------- | ------------------------------------------------------------------- |
| Claude Code    | `.mcp.json` nella root del progetto (o globale `~/.claude.json`)     |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json`   |
| Open Cloud     | sezione `mcpServers` nelle impostazioni del client                  |
| Perplexity     | sezione MCP delle impostazioni del client (dove supportato)         |

Dopo la configurazione, **riavvia il client** perché ricarichi l'elenco
dei server MCP.

## Skill per agenti

In [`.trae/skills/`](./.trae/skills/) trovi due skill `SKILL.md` pronte
per essere caricate da TRAE, Claude Code e altri agenti compatibili:

| Skill                  | Quando l'agente la usa                                              |
| ---------------------- | ------------------------------------------------------------------- |
| `wiki-kiss-bridge`     | Leggere, cercare, scrivere, citare contenuti del wiki.              |
| `wiki-kiss-operator`   | Installare, avviare, fermare, integrare o fare troubleshooting.      |

Copia le cartelle in `~/.claude/skills/` (o nel percorso previsto dal
tuo client) per usarle localmente.

## Script di gestione

Tutti accettano `--help`. I log vanno in `var/log/`, i PID in `var/run/`.

| Script                              | Scopo                                                       |
| ----------------------------------- | ----------------------------------------------------------- |
| `scripts/setup.sh`                  | Crea/aggiorna venv e installa dipendenze.                   |
| `scripts/setup.sh --with-dev`       | + pytest, ruff, httpx.                                      |
| `scripts/setup.sh --recreate`       | Ricrea il venv da zero.                                     |
| `scripts/start-mcp.sh`              | Avvia server MCP in foreground (per client MCP).            |
| `scripts/start-rest.sh`             | Avvia REST API in background.                               |
| `scripts/start-rest.sh --foreground` | Avvia REST in foreground.                                   |
| `scripts/start-rest.sh --reload`    | Modalità sviluppo con auto-reload.                          |
| `scripts/stop.sh {mcp\|rest\|all}`  | Ferma uno o più servizi.                                    |
| `scripts/status.sh`                 | Mostra stato, PID, log.                                     |
| `scripts/install-mcp-client.sh`     | Genera config MCP per i vari client.                        |
| `scripts/run-tests.sh`              | Wrapper su `pytest` (accetta argomenti pytest).             |

Variabili d'ambiente riconosciute: `WIKI_ROOT`, `WIKI_LOG_LEVEL`,
`DEFAULT_HOST`, `DEFAULT_PORT`, `NO_COLOR`. Possono essere salvate in
`.env` o `.wiki-kiss.env` (auto-caricati).

## Test e qualità

```bash
scripts/run-tests.sh -q
.venv/bin/python -m pytest -q
.venv/bin/python tests/smoke_mcp.py   # smoke test del server MCP via stdio
.venv/bin/ruff check wiki_core mcp_server rest_api.py tests
```

## Struttura del wiki

Esempio di organizzazione della cartella `wiki/`:

```
wiki/
├── index.md
├── projects/         # documentazione di progetto
├── notes/            # appunti, idee, osservazioni
├── decisions/        # ADR (NNNN-titolo.md)
├── references/       # link e fonti esterne
├── assets/           # immagini, allegati
└── logs/             # log append-only (YYYY-MM-DD.md)
```

**Convenzioni**:

- File in Markdown puro, UTF-8.
- Nomi in `kebab-case`.
- Ogni pagina inizia con un titolo di primo livello (`# Titolo`).
- Link interni relativi: `[altra pagina](../notes/idea.md)`.
- Nessun frontmatter obbligatorio: solo se serve metadata reale.

## Filosofia

KISS prima di tutto.

- **Il wiki conserva conoscenza stabile**: decisioni, progetti, riferimenti.
- **La memoria conversazionale è gestita a parte** (es. QMD): serve per
  il contesto dinamico e di breve durata, non per la conoscenza di lungo periodo.
- **MCP rende quella conoscenza accessibile a tutti gli agenti**: un
  solo contratto, infinite integrazioni.
- **Niente database**: `tar czf wiki-$(date +%F).tgz wiki/` è il backup.
- **Niente lock-in**: tutto è testo, tutto è versionabile con Git.

## Vantaggi e limiti

**Vantaggi**: controllo totale, backup banale, migrazione immediata,
debug semplice, compatibilità con più agenti AI, crescita per gradi.

**Limiti**: nessun backlink automatico, nessun database nativo, nessuna
UI ricca. La qualità dipende dalla disciplina nella scrittura e nelle
convenzioni di naming.

## Contribuire

Issue e PR benvenuti. Linee guida:

- Codice in stile ruff (configurato in `pyproject.toml`).
- Test obbligatori per le modifiche al core (`wiki_core`).
- Stile del wiki: ADR in `decisions/`, regole di naming
  in [`wiki/decisions/0001-storage-filesystem.md`](./wiki/decisions/0001-storage-filesystem.md).

## Licenza

[MIT](./LICENSE) — Copyright (c) 2026 Hornet SRL.

## Crediti

Progetto ispirato al paper del Model Context Protocol
(<https://modelcontextprotocol.io>) e alla filosofia Unix "do one thing
and do it well".
