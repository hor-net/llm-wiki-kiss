# Agents — llm-wiki-kiss

Questo documento descrive l'ecosistema **llm-wiki-kiss**, un wiki **KISS** (Keep It Simple, Stupid) self-hosted per agenti AI. È progettato per offrire una knowledge base persistente, portabile e controllabile al 100%, accessibile a diversi modelli tramite **MCP** (Model Context Protocol).

---

## Panoramica

**llm-wiki-kiss** trasforma file Markdown statici in una source di verità condivisa tra agenti AI. Risolve il problema della conoscenza frammentata nei tool, negli appunti e nelle conversazioni: tutto è persistentemente archiviato in filesystem e uniformemente esposto tramite un contratto MCP standardizzato.

### Filosofia
- **KISS**: nessun database, nessun CMS complesso, solo file e link.
- **Persistente**: il wiki sopravvive tra sessioni di agente.
- **Portabile**: una cartella tar.gz è tutto il backup necessario.
- **Multicast**: lo stesso contenuto serve Claude Code, Open Cloud, Perplexity, script Python, ecc.

---

## Architettura

```
llm-wiki-kiss/
├── wiki/                    # dati Markdown (il tuo wiki)
│   ├── index.md            # punto d'entrata principale
│   ├── projects/           # documentazione di progetto
│   ├── notes/              # appunti, idee, osservazioni rapide
│   ├── decisions/          # ADR e decisioni tecniche
│   ├── references/         # link e fonti esterne
│   ├── assets/             # immagini, allegati
│   └── logs/               # log append-only (YYYY-MM-DD.md)
├── wiki_core/              # storage, validazione, ricerca, locking e CLI
├── mcp_server/             # MCP stdio + Streamable HTTP su TLS, single-wiki
├── rest_api.py             # fallback HTTP FastAPI
├── scripts/                # setup, configure, CLI e gestione servizi
├── tests/                  # pytest + smoke test MCP
├── CONFIGURATION.md        # root, token, TLS e toggle HTTPS
├── ONBOARDING.md           # skill personalizzate con connessione privata
├── .trae/skills/           # template SKILL.md per agenti AI
└── pyproject.toml          # metadato progetto, dipendenze, tooling
```

### Strumenti MCP (5 in totale)

| Tool | Descrizione | Tipo |
|------|-------------|------|
| `list_pages` | Elenca pagine nel wiki (`subdir` opzionale). | Lettura |
| `read_page` | Legge il contenuto completo di una pagina. | Lettura |
| `search` | Full-text search case-insensitive con snippet e numero di riga. | Lettura |
| `write_page` | Crea o sovrascrive una pagina e rigenera gli indici. | Scrittura protetta |
| `append_note` | Accoda testo a una pagina o al log giornaliero e rigenera gli indici. | Scrittura protetta |

### Server e Porte

- **MCP stdio**: processo locale, per agent che usano IPC.
- **MCP Streamable HTTP su HTTPS** (opzionale): TLS e Bearer obbligatori.
- **REST API FastAPI**: fallback opzionale, protetto dallo stesso Bearer.

Default: `127.0.0.1:8765` (REST locale), `127.0.0.1:8766` (MCP HTTPS).

### Accesso locale offline

- MCP `stdio`: `python -m mcp_server --root /percorso/wiki`; comunica solo su
  stdin/stdout e non apre socket.
- CLI: `scripts/wiki.sh` oppure `python -m wiki_core.cli`; offre `list`, `read`,
  `search`, `write`, `append`, `stats` e `rebuild-indexes`.
- MCP stdio e CLI non richiedono `WIKI_MCP_TOKEN`; la protezione è affidata ai
  permessi dell'utente e del filesystem locale.
- Tutte le mutazioni passano comunque da `WikiStorage` e rispettano il lock.

### Modello di isolamento

Ogni processo o container serve esattamente una root `WIKI_ROOT` e usa un
solo token `WIKI_MCP_TOKEN` per entrambi i trasporti HTTP. Clienti o wiki differenti devono essere
eseguiti in container separati, con filesystem, token e porta indipendenti.
Non introdurre routing multi-tenant o registri di wiki nel processo.

### Setup e configurazione

- `scripts/setup.sh --root PATH --https off` installa il progetto, crea la root,
  genera il token e stampa `WIKI_MCP_TOKEN=...`.
- `scripts/configure.sh` salva la configurazione in `.wiki-kiss.env` con modo
  `0600`; questo file è ignorato da Git e prevale su `.env`.
- HTTPS è spento per default. `configure.sh --https on --cert CERT --key KEY`
  salva e avvia il servizio; `configure.sh --https off` lo arresta e disabilita.
- `start-mcp-http.sh` deve rifiutare l'avvio senza flag abilitato, token,
  certificato o chiave. Non aggiungere fallback HTTP in chiaro.
- Per bind wildcard (`0.0.0.0`/`::`) è obbligatoria `WIKI_MCP_URL`, usata
  dall'onboarding per configurare i client.
- La REST API è ammessa solo in loopback; l'accesso remoto passa da MCP HTTPS.
- Rotazione token: `configure.sh --rotate-token`; lettura esplicita:
  `configure.sh --show-token`.
- Guida operativa: [`CONFIGURATION.md`](CONFIGURATION.md).

### Onboarding degli agenti

- `scripts/onboard-agent.sh` genera una skill Agent Skills personalizzata.
- Output predefinito: `.agents/skills/generated/<name>/`, ignorato da Git.
- `references/connection.json` e `mcp-config.json` contengono root, URL e token;
  directory e file devono mantenere rispettivamente modi `0700` e `0600`.
- La modalità `auto` sceglie HTTPS quando attivo, altrimenti MCP stdio locale.
- Non stampare il token durante l'onboarding e non committare skill generate.
- Dopo `configure.sh --rotate-token`, rigenerare le skill autorizzate con
  `--force`; eliminare quelle revocate.
- Specifica e procedure: [`ONBOARDING.md`](ONBOARDING.md).

### Concorrenza e resilienza

La concorrenza resta filesystem-based e senza servizi esterni:

- letture, liste e ricerche non acquisiscono lock e possono procedere in parallelo;
- ogni mutazione acquisisce un lock esclusivo **per root wiki**;
- il lock combina un `RLock` condiviso nel processo e un file lock del sistema
  operativo (`.wiki-kiss.lock`) per coordinare processi diversi;
- pagina e indici sono scritti su file temporanei nella stessa directory,
  sincronizzati e pubblicati con `os.replace`, quindi un lettore non vede file
  scritti a metà;
- `append_note` è un read-modify-write protetto: append concorrenti non vengono persi;
- la rigenerazione degli indici avviene dentro lo stesso lock della modifica;
- il timeout predefinito è 10 secondi e produce `WriteLockTimeoutError`.

Il lock coordina solo processi che usano `WikiStorage`. Un editor o script che
scrive direttamente nei file può aggirarlo; in presenza di più agenti tutte le
mutazioni devono quindi passare dal core, da MCP o dalla REST API. Il file di
lock è solo un artefatto tecnico: non va cancellato durante l'esecuzione e non
può rimanere “bloccato” dopo la morte del processo, perché il lock è gestito
dal sistema operativo.

---

## Storage e Contenuti

### Formato
- File **Markdown** puro, UTF-8. (In futuro HTML se serve rich.)
- Link interni relativi: `[testo](../notes/idea.md)`, `[# Sezione](#titolo)` .
- Nomi file `kebab-case`.
- Nessun frontmatter obbligatorio; il primo titolo è il nome pagina.

### Convenzioni
1. Ogni pagina parte con `# Titolo` .
2. Link relativi a cartelle parenti: `[altro](../notes/idea.md)` .
3. **Niente database**: backup semplice con `tar`, migrazione immediata.
4. Versionamento con Git; ogni commit è un punto di controllo stabile.

### Tipologie di pagine (best-practice)

| Categoria        | Scopo                                          | Cartella       |
|------------------|------------------------------------------------|-----------------|
| `projects/*.md`  | Doc progetti, roadmap, specifiche              | `projects/`    |
| `notes/*.md`     | Appunti, idee, osservazioni rapide              | `notes/`       |
| `decisions/*.md` | ADR (architecture decision records)             | `decisions/`   |
| `references/*`   | Link esterni, fonti, articoli                   | `references/`  |
| `assets/*`       | Immagini, PDF, audio                           | `assets/`      |
| `logs/*.md`      | Log delle operazioni (append-only)              | `logs/`        |

---

## API REST

Una API minimale serve come fallback per client legacy. Espone gli stessi operatori base dei tool MCP, più `/health` e `/stats`. Endpoint principali:

- `GET /health` — Health check
- `GET /stats` — Statistiche wiki (conteggio pagine, dimensione totale)
- `GET /pages?subdir=…` — Lista pagine nella root o subdir specifica
- `GET /pages/{path:path}` — Legge contenuto di una pagina
- `PUT /pages/{path:path}` — Crea/sovrascrive pagina; restituisce info
- `GET /search?q=…` — Full-text search con snippet e numero di riga
- `POST /notes` — Append nota (default log giornaliero)

`/health` è pubblico ma non espone root o contenuti. Tutti gli altri endpoint,
compresi `/docs` e `/openapi.json`, richiedono `Authorization: Bearer
<WIKI_MCP_TOKEN>`. Senza token il servizio risponde `503` e non serve dati.

---

## Configurazione del Client

Configura un server MCP nel tuo client AI. Esempio: Claude Code, Open Cloud, Perplexity.

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

Variabili principali: `WIKI_ROOT`, `WIKI_MCP_TOKEN`, `WIKI_HTTPS_ENABLED`,
`WIKI_HTTP_HOST`, `WIKI_HTTP_PORT`, `WIKI_MCP_URL`, `WIKI_TLS_CERT`,
`WIKI_TLS_KEY`, `WIKI_LOG_LEVEL`, `NO_COLOR`.

### Scripts di gestione (`scripts/*`)

| Script                           | Scopo                                                        |
|----------------------------------|--------------------------------------------------------------|
| [`setup.sh`](scripts/setup.sh)  | Installa e configura root, token e stato HTTPS               |
| `configure.sh`                 | Modifica root/token e accende o spegne MCP HTTPS             |
| `onboard-agent.sh`             | Genera skill privata con URL/path e credenziali              |
| `start-mcp.sh`                  | Lancia server MCP stdio (locale, senza rete)                 |
| `wiki.sh`                       | CLI locale per contenuti e manutenzione indici               |
| `start-mcp-http.sh`             | Lancia MCP HTTPS solo se abilitato                           |
| `start-rest.sh`                 | Avvia API REST in background                                 |
| `stop.sh {mcp|mcp-http|rest}`   | Ferma i servizi                                               |
| `status.sh`                     | Mostra stato, PID, log                                       |
| `run-tests.sh`                  | Wrapper su pytest, con args opzionali                        |
| `install-mcp-client.sh`         | Genera config MCP per CLI diversi (Claude Code, ecc.)        |

---

## Skill per Agenti AI

In `.trae/skills/` due skill `SKILL.md` pronte:

1. **wiki-kiss-bridge**: strumenti per leggere, cercare e aggiungere informazioni al wiki (per agent che vogliono usare la knowledge base).
2. **wiki-kiss-operator**: comandi di installazione, avvio, gestione operativa e troubleshooting.

Copia in `~/.claude/skills/` (o percorso fornito dal tuo client) e riavvia l'agent per caricare le skill.

---

## Test e Qualità

```bash
scripts/run-tests.sh -q
.venv/bin/python -m pytest -q
.venv/bin/ruff check wiki_core mcp_server rest_api.py tests
```

- **pytest** per storage, CLI, autenticazione e concorrenza thread/processi.
- **Smoke test** MCP stdio e trasporto HTTP protetto da TLS in produzione.
- **Ruff** per linting/stile.

### Regole per modificare il core

1. Non introdurre database, Redis o code esterne senza un requisito dimostrato.
2. Mantenere una sola root e un solo token per processo; usare container
   separati, volumi non condivisi e token distinti per clienti differenti.
3. Non scrivere pagine o indici direttamente dagli handler: usare `WikiStorage`.
4. Ogni nuova mutazione deve usare il write lock della root e scrittura atomica.
5. Le letture devono restare lock-free; accettano di osservare la versione
   completa precedente o successiva, mai un file parziale.
6. Gli indici sono dati derivati e deterministici: nessun LLM nella generazione.
7. Aggiungere test di concorrenza quando cambia il percorso di scrittura.

---

## Esempio di Pagina Markdown

```markdown
# HoRNetMBC

**HoRNet** · versione 1.0.4 · Dynamics

## Repository

- **GitHub:** https://github.com/hor-net/HoRNetMBC
- **Path locale:** `/Users/…/Projects/HoRNetMBC`

## Identificativi Plugin

- **Manufacturer ID:** `HrNt`
- **Unique ID:** `bI8H`
- **AAX Type IDs:** `IEF1, IEF2`

## Build

- Script di build cross-platform in `scripts/`
- Installer su `installer/` per macOS/Windows
```

---

## Sicurezza

- Validazione percorsi: nessun symlink o `..` arbitrario.
- Limite file 2 MiB per singola pagina.
- Scope limitato alla root del wiki (`WIKI_ROOT`).
- TLS e autenticazione Bearer obbligatori per MCP di rete; Bearer obbligatorio
  per REST locale; comportamento
  fail-closed se `WIKI_MCP_TOKEN` non è configurato.
- Gli health check pubblici non espongono root, percorsi o contenuti.
- Tutte le risposte HTTP usano `Cache-Control: no-store` e non devono essere
  memorizzate da browser o proxy.

---

## Licenza, Contributi e Riferimenti

- **Licenza:** GNU AGPL v3 o successiva — Copyright (C) 2026 Hornet SRL.
- **Contribuire:** issue/PR benvenuti; linee guida in README.md.
- **Riferimento MCP:** https://modelcontextprotocol.io
- **Filosofia Unix:** "do one thing and do it well".
