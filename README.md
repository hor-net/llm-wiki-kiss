# llm-wiki-kiss

> **Un wiki KISS self-hosted per agenti AI** — file Markdown su filesystem,
> accesso uniforme via **MCP** (stdio) e fallback **REST/HTTP** opzionale.
> Stesso contenuto, qualunque sia l'agente: Claude Code, Open Cloud,
> Perplexity, script Python, browser.

[![License: AGPL v3 or later](https://img.shields.io/badge/License-AGPLv3%2B-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-8A2BE2)](https://modelcontextprotocol.io)
[![Tests](https://github.com/hor-net/llm-wiki-kiss/actions/workflows/tests.yml/badge.svg)](https://github.com/hor-net/llm-wiki-kiss/actions/workflows/tests.yml)
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
- [Configurazione](#configurazione)
- [Uso locale offline](#uso-locale-offline)
- [I 5 tool MCP](#i-5-tool-mcp)
- [API REST](#api-rest)
- [Configurazione del client MCP](#configurazione-del-client-mcp)
- [Skill per agenti](#skill-per-agenti)
- [Onboarding personalizzato](#onboarding-personalizzato)
- [Script di gestione](#script-di-gestione)
- [Test e qualità](#test-e-qualità)
- [Struttura del wiki](#struttura-del-wiki)
- [Filosofia](#filosofia)
- [Licenza](#licenza)

## Caratteristiche

- **Storage filesystem**: una cartella con file Markdown e link relativi.
- **Concorrenza KISS**: letture parallele, lock di scrittura per singola root e
  pubblicazione atomica di pagine e indici.
- **Server MCP stdio** con cinque tool: `list_pages`, `read_page`,
  `search`, `write_page`, `append_note`.
- **Server MCP Streamable HTTP** (MCP 2025) per client cloud con
  autenticazione Bearer obbligatoria e fail-closed.
- **API REST** FastAPI protetta dallo stesso token, con OpenAPI su `/docs`.
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
├── mcp_server/            # server MCP stdio + Streamable HTTP (5 tool)
├── rest_api.py            # fallback HTTP FastAPI
├── scripts/               # setup, configure, CLI, start, stop e status
├── tests/                 # pytest + smoke test MCP via stdio e HTTP
├── CONFIGURATION.md       # root, token, TLS e toggle HTTPS
├── ONBOARDING.md          # generazione skill personalizzate
├── SECURITY.md            # modello di sicurezza e segnalazioni
├── CONTRIBUTING.md        # guida per contributori
├── CHANGELOG.md           # cronologia delle release
├── .trae/skills/          # template SKILL.md per agenti AI
├── pyproject.toml, requirements*.txt, .env.example, .gitignore
├── LICENSE                # GNU AGPL v3 or later
└── README.md
```

## Quick start (5 minuti)

Prerequisito: **Python 3.10+**.

```bash
# 1. Clona e configura
git clone https://github.com/hor-net/llm-wiki-kiss.git
cd llm-wiki-kiss

# 2. Installa, scegli la root, genera il token e lascia HTTPS spento
scripts/setup.sh --with-dev --root ./wiki --https off

# 3. Recupera il token generato e avvia la REST API locale
export WIKI_MCP_TOKEN="$(scripts/configure.sh --show-token)"
scripts/start-rest.sh

# 4. Verifica (health pubblico, dati autenticati)
scripts/status.sh
curl http://127.0.0.1:8765/health
curl -H "Authorization: Bearer $WIKI_MCP_TOKEN" http://127.0.0.1:8765/stats
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

## Configurazione

Lo script [`scripts/configure.sh`](scripts/configure.sh) seleziona la root,
genera o ruota il token e accende/spegne realmente l'interfaccia MCP HTTPS. Le
impostazioni sono salvate in `.wiki-kiss.env` con permessi `0600`.

```bash
scripts/configure.sh                              # modalità interattiva
scripts/configure.sh --root ~/wiki-privato --https off
scripts/configure.sh --show-token
scripts/configure.sh --rotate-token
scripts/configure.sh --https off                  # arresta e disabilita HTTPS
scripts/configure.sh --https on                   # riusa certificato/chiave salvati
```

HTTPS richiede sempre certificato e chiave PEM. La guida completa, inclusa la
creazione di un certificato self-signed per test, è in
[`CONFIGURATION.md`](CONFIGURATION.md).

## Uso locale offline

Né MCP `stdio` né la CLI aprono porte o richiedono un token. Entrambi accedono
direttamente alla singola root `WIKI_ROOT` e riusano locking, validazione e
scritture atomiche di `WikiStorage`.

### MCP stdio

La configurazione client mostrata più avanti avvia:

```bash
.venv/bin/python -m mcp_server --root /percorso/del/wiki
```

La comunicazione avviene sui flussi stdin/stdout del sottoprocesso locale: non
usa HTTP, DNS o connessioni di rete.

### CLI

Dal checkout usa `scripts/wiki.sh`; dopo l'installazione del pacchetto è
disponibile anche `wiki-kiss`.

```bash
scripts/wiki.sh list
scripts/wiki.sh read notes/idea.md
scripts/wiki.sh search "testo da trovare" --subdir notes
scripts/wiki.sh write notes/idea.md --content $'# Idea\n\nContenuto'
printf '# Da stdin\n\nTesto\n' | scripts/wiki.sh write notes/stdin.md
scripts/wiki.sh append logs/manuale.md --content "Operazione completata"
printf 'Nota dal processo locale\n' | scripts/wiki.sh append
scripts/wiki.sh stats
scripts/wiki.sh rebuild-indexes
```

La root può essere scelta con `--root /percorso/wiki` oppure con `WIKI_ROOT`.
`read` produce Markdown puro; `list`, `search`, `write`, `append` e `stats`
producono JSON, quindi sono utilizzabili anche da script e agenti locali.
L'accesso locale segue i permessi del filesystem: per un wiki privato usa una
root non condivisa e, su Unix, permessi come `chmod -R go-rwx /percorso/wiki`.

## I 5 tool MCP

| Tool          | Cosa fa                                                        |
| ------------- | -------------------------------------------------------------- |
| `list_pages`  | Elenca pagine, opzionale `subdir`.                             |
| `read_page`   | Legge il contenuto di una pagina dato il percorso.             |
| `search`      | Full-text case-insensitive con snippet e numero di riga.       |
| `write_page`  | Crea o sovrascrive una pagina. Aggiunge `.md` se manca.        |
| `append_note` | Aggiunge testo. Di default accoda al log `logs/YYYY-MM-DD.md`. |

Tutti i percorsi sono **relativi** alla root del wiki e separati da `/`.

### Concorrenza

Le letture sono lock-free. `write_page`, `append_note` e la rigenerazione degli
indici sono serializzati per root tramite `.wiki-kiss.lock`, valido tra thread e
processi. Le scritture usano file temporanei, `fsync` e `os.replace`: un lettore
vede il file completo precedente o successivo, mai una scrittura parziale.
Istanze o container distinti restano indipendenti. Gli handler MCP eseguono le
operazioni filesystem nel thread pool standard, così non bloccano l'event loop.

Il coordinamento vale per le modifiche effettuate tramite `WikiStorage`, MCP o
REST. Script ed editor che scrivono direttamente nella root aggirano il lock.

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

Tutti gli endpoint REST, inclusi `/docs` e `/openapi.json`, richiedono
`Authorization: Bearer <WIKI_MCP_TOKEN>`. Solo `/health` è pubblico e non
espone root, percorsi o contenuti. Le risposte HTTP impostano
`Cache-Control: no-store`. Se il token manca, il servizio resta **fail-closed**
e risponde `503` senza servire dati.

## MCP Streamable HTTP (per client cloud)

Il server MCP è esposto anche via HTTPS con il nuovo trasporto
**Streamable HTTP** (MCP 2025-06-18), così client MCP-aware in cloud
(Open Cloud aggiornato, ecc.) possono usarlo senza lanciare un
sottoprocesso.

```bash
scripts/configure.sh --https on \
  --host 0.0.0.0 \
  --port 8766 \
  --url https://wiki.example.com/mcp \
  --cert /percorso/fullchain.pem \
  --key /percorso/privkey.pem
```

Il client si connette a `https://HOST:8766/mcp` con:

```
POST /mcp
Authorization: Bearer segreto-casuale-lungo
Accept: application/json, text/event-stream
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

Per spegnerlo in qualunque momento usa `scripts/configure.sh --https off`.
MCP stdio e CLI continuano a funzionare. Per un servizio pubblico usa un
certificato attendibile (per esempio Let's Encrypt) oppure un reverse proxy TLS.

Il processo serve una sola root (`WIKI_ROOT`) con un solo token obbligatorio
(`WIKI_MCP_TOKEN`). Senza token entrambi i trasporti HTTP restano fail-closed.
Per gestire clienti o wiki distinti, avvia istanze o container separati con
filesystem, token e porta propri. Non condividere volumi o token tra clienti.

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

## Onboarding personalizzato

Genera una Agent Skill specifica per l'istanza configurata:

```bash
scripts/onboard-agent.sh --name customer-wiki --label "Customer Wiki"
```

La modalità `auto` usa HTTPS quando è acceso e configurato, altrimenti MCP
stdio locale. La skill contiene:

- `SKILL.md` personalizzato;
- `references/connection.json` con root, URL e token;
- `references/mcp-config.json` pronto da adattare al client.

La destinazione predefinita `.agents/skills/generated/` è ignorata da Git. I
file hanno permessi `0600` e contengono credenziali reali: non vanno condivisi
o committati. Dopo la rotazione del token rigenera la skill con `--force`.
Consulta [`ONBOARDING.md`](ONBOARDING.md) per modalità locale/remota,
installazione globale e revoca.

## Script di gestione

Tutti accettano `--help`. I log vanno in `var/log/`, i PID in `var/run/`.

| Script                              | Scopo                                                       |
| ----------------------------------- | ----------------------------------------------------------- |
| `scripts/setup.sh`                  | Crea/aggiorna venv e installa dipendenze.                   |
| `scripts/setup.sh --with-dev`       | + pytest, ruff, httpx.                                      |
| `scripts/setup.sh --recreate`       | Ricrea il venv da zero.                                     |
| `scripts/configure.sh`              | Configura root, token e stato MCP HTTPS.                    |
| `scripts/onboard-agent.sh`          | Genera una skill privata con URL/path e credenziali.        |
| `scripts/start-mcp.sh`              | Avvia server MCP stdio (locale, senza rete).                |
| `scripts/wiki.sh`                   | CLI locale per leggere, cercare e modificare il wiki.       |
| `scripts/start-mcp-http.sh`         | Avvia MCP HTTPS solo se abilitato e configurato.            |
| `scripts/start-rest.sh`             | Avvia REST API in background.                               |
| `scripts/start-rest.sh --foreground` | Avvia REST in foreground.                                   |
| `scripts/start-rest.sh --reload`    | Modalità sviluppo con auto-reload.                          |
| `scripts/stop.sh {mcp\|mcp-http\|rest\|all}` | Ferma uno o più servizi.                       |
| `scripts/status.sh`                 | Mostra stato, PID, log.                                     |
| `scripts/install-mcp-client.sh`     | Genera config MCP stdio per i vari client.                  |
| `scripts/run-tests.sh`              | Wrapper su `pytest` (accetta argomenti pytest).             |

Variabili principali: `WIKI_ROOT`, `WIKI_MCP_TOKEN`, `WIKI_HTTPS_ENABLED`,
`WIKI_HTTP_HOST`, `WIKI_HTTP_PORT`, `WIKI_MCP_URL`, `WIKI_TLS_CERT`, `WIKI_TLS_KEY`,
`WIKI_LOG_LEVEL`, `DEFAULT_HOST`, `DEFAULT_PORT`, `NO_COLOR`.
`configure.sh` gestisce `.wiki-kiss.env`, che prevale sull'eventuale `.env`.

## Test e qualità

```bash
scripts/run-tests.sh -q
.venv/bin/python -m pytest -q
.venv/bin/python tests/smoke_mcp.py       # smoke test MCP stdio
.venv/bin/python tests/smoke_mcp_http.py  # smoke test MCP Streamable HTTP
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
UI ricca e nessuna transazione distribuita. La qualità dipende dalla disciplina
nella scrittura e nelle convenzioni di naming. Il file lock presuppone un
filesystem che supporti correttamente i lock del sistema operativo.

## Contribuire

Issue e PR benvenuti. Leggi [`CONTRIBUTING.md`](CONTRIBUTING.md) prima di
proporre modifiche. Per vulnerabilità usa la procedura privata descritta in
[`SECURITY.md`](SECURITY.md), non una issue pubblica.

- Codice in stile Ruff e test obbligatori per le modifiche al core.
- Stile del wiki: ADR in `decisions/`; riferimento:
  [`wiki/decisions/0001-storage-filesystem.md`](wiki/decisions/0001-storage-filesystem.md).
- Cronologia: [`CHANGELOG.md`](CHANGELOG.md).
- Procedura di release: [`RELEASING.md`](RELEASING.md).

## Licenza

[GNU AGPL v3 or later](./LICENSE) — Copyright (C) 2026 Hornet SRL.

È possibile utilizzare e vendere il servizio, rispettando i termini della
licenza. In particolare, l'AGPLv3 richiede di offrire il sorgente della
versione modificata agli utenti che la usano tramite rete. I dati e i wiki
degli utenti non diventano per questo parte del codice concesso in licenza.

## Crediti

Progetto ispirato al paper del Model Context Protocol
(<https://modelcontextprotocol.io>) e alla filosofia Unix "do one thing
and do it well".
