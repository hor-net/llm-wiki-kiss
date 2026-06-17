# ADR 0001 — Storage su filesystem

## Stato
Accettato.

## Contesto
Serve un posto semplice per conservare conoscenza condivisa tra agenti AI.
Le opzioni valutate sono state:
1. Database relazionale (SQLite, Postgres).
2. CMS (Notion, Confluence, Obsidian sync server).
3. File system + Markdown.

## Decisione
Si adotta il file system con file Markdown.

## Conseguenze
- Versionamento con Git immediato.
- Backup pari a `tar` della cartella.
- Migrazione banale verso qualsiasi altro formato testuale.
- Nessun lock-in tecnologico.
- Si perde: ricerca full-text performante, backlink automatici, multi-utente concorrente.
