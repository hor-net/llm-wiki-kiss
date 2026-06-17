---
name: "wiki-kiss-bridge"
description: "Integra un wiki KISS come fonte di conoscenza stabile per un agente AI. Invocare quando l'agente deve leggere, cercare, scrivere o citare contenuti del wiki via MCP, oppure quando ha bisogno di contesto persistente tra sessioni."
---

# Wiki KISS — Bridge per agenti AI

Questa skill spiega a un agente AI (Claude Code, Claude Desktop, Open Cloud,
Perplexity, ...) come interagire con un'istanza di wiki KISS esposta via MCP.

## Quando invocare questa skill

- L'utente chiede di consultare, salvare o organizzare conoscenza nel wiki.
- L'utente cita "il wiki", "wiki-kiss", "wiki KISS" o percorsi che iniziano con
  `wiki/`, `notes/`, `decisions/`, `projects/`, `logs/`.
- L'utente vuole che informazioni condivise siano **persistenti** e non vadano
  perse al termine della sessione.
- L'utente chiede "ricordami", "salva questo", "appuntalo", "cercami" in un
  contesto dove il wiki è la fonte canonica.

Non invocare se:
- L'utente vuole solo risposte effimere o di puro calcolo.
- Il client MCP del wiki non è disponibile (nessun tool `list_pages`, ecc.).

## I cinque tool disponibili

Il server MCP `wiki-kiss` espone:

| Tool          | Scopo                                                  |
| ------------- | ------------------------------------------------------ |
| `list_pages`  | Elenca pagine (opzionale filtro `subdir`).             |
| `read_page`   | Legge il contenuto di una pagina dato `path`.          |
| `search`      | Full-text case-insensitive, ritorna snippet e riga.    |
| `write_page`  | Crea o sovrascrive una pagina.                         |
| `append_note` | Aggiunge rapidamente testo (default: log del giorno).  |

Tutti i percorsi sono **relativi** alla root del wiki e separati da `/`.

## Workflow consigliato

### 1. Prima di scrivere: capire cosa esiste

```
list_pages  →  search(query="...")  →  read_page(path=...)
```

Mai sovrascrivere una pagina senza prima leggerne il contenuto.
Prima di creare una pagina nuova, verificare che non esista già una simile
(usa `list_pages` o `search`).

### 2. Scegliere il percorso giusto

Il wiki segue una convenzione di cartelle. Mappa l'intento dell'utente così:

| Intento                                   | Cartella     | Esempio                              |
| ----------------------------------------- | ------------ | ------------------------------------ |
| Documentazione di progetto                | `projects/`  | `projects/wiki-kiss.md`              |
| Appunti rapidi, idee, osservazioni        | `notes/`     | `notes/2026-06-17-idea-x.md`         |
| Decisioni tecniche (ADR)                  | `decisions/` | `decisions/0002-uso-fastapi.md`      |
| Link e riferimenti esterni                | `references/`| `references/mcp-spec.md`             |
| Log append-only di eventi/attività        | `logs/`      | `logs/2026-06-17.md` (auto)          |

Convenzioni:
- File in **Markdown** (`.md`), UTF-8.
- Nomi in **kebab-case**.
- Ogni pagina inizia con un titolo di primo livello (`# Titolo`).
- Link interni **relativi**: `[altra pagina](../notes/idea.md)`.

### 3. Scrivere con `write_page`

```json
{
  "path": "notes/idea-sull-indicizzazione.md",
  "content": "# Idea sull'indicizzazione\n\nTesto...\n",
  "overwrite": false
}
```

Regole:
- `overwrite: false` per impostazione predefinita; mettere `true` solo se
  l'utente l'ha esplicitamente richiesto o se hai appena letto la pagina
  e ne hai verificato il contenuto.
- Se l'estensione manca, viene aggiunta `.md` automaticamente.
- Includi sempre un frontmatter minimo: `# Titolo` come prima riga.

### 4. Aggiungere note rapide con `append_note`

Per log, micro-aggiornamenti, timestamp automatici:

```json
{ "content": "Deciso di rimandare il refactor.", "heading": "Blocker" }
```

Senza `path`, il contenuto viene accodato al file `logs/YYYY-MM-DD.md`
(UTC). Usalo di default per qualsiasi "ricordami questo" o "appuntalo".

### 5. Cercare con `search`

```json
{ "query": "MCP", "max_results": 10, "subdir": "notes" }
```

Lo snippet include ~60 caratteri di contesto a sinistra e a destra del
match. Usa `subdir` per limitare l'ambito della ricerca.

## Buone pratiche

- **Cita sempre la fonte**: se rispondi a una domanda usando il wiki,
  includi il percorso della pagina (es. "Fonte: `decisions/0001-storage-filesystem.md`").
- **Non duplicare**: prima di scrivere una nuova pagina, controlla se ne
  esiste una semanticamente equivalente.
- **Scrivi per essere letto anche da umani**: il contenuto deve restare
  utile se aperto con un editor di testo puro.
- **Rispetta la struttura**: se l'utente chiede un'ADR, va in `decisions/`,
  non in `notes/`.
- **Log di tracciamento**: per ogni azione significativa, accoda una nota
  al log del giorno con `append_note` (specificando un `heading` se utile).

## Errori comuni da evitare

- Passare percorsi con `..` o slash iniziale: verranno rifiutati.
- Dimenticare l'estensione: il sistema la aggiunge, ma meglio essere espliciti.
- Sovrascrivere senza leggere prima: rischi di perdere informazioni.
- Inventare contenuti che non esistono nel wiki: se non trovi qualcosa
  via `search`, dillo, non riempire i buchi.

## Esempio di interazione completa

1. L'utente chiede: "Ricordi cosa avevamo deciso sullo storage?"
2. `search({ "query": "storage" })` → trova `decisions/0001-storage-filesystem.md`.
3. `read_page({ "path": "decisions/0001-storage-filesystem.md" })` → contenuto.
4. Risposta: "Sì, vedi `decisions/0001-storage-filesystem.md`: abbiamo
   adottato filesystem + Markdown, senza database."

## Esempio di scrittura

1. L'utente chiede: "Salva una nota: oggi abbiamo iniziato il refactor del
   search."
2. `append_note({ "content": "Iniziato refactor del search.", "heading": "Refactor" })`
   → accoda a `logs/2026-06-17.md`.

## Disponibilità

La skill presuppone che il tool MCP `wiki-kiss` sia già configurato nel
client dell'utente. Se `list_pages` fallisce con errore di connessione,
suggerisci di eseguire `scripts/install-mcp-client.sh` e riavviare il client.
