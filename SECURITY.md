# Security Policy

## Versioni supportate

Il branch `main` e l'ultima release pubblicata ricevono correzioni di sicurezza.
Le versioni precedenti possono non ricevere backport.

## Segnalare una vulnerabilità

Usa esclusivamente la funzione privata **Report a vulnerability** di GitHub:

<https://github.com/hor-net/llm-wiki-kiss/security/advisories/new>

Non aprire issue pubbliche contenenti vulnerabilità, token, certificati, path
privati o pagine del wiki. Includi una riproduzione minimale con dati fittizi.

## Modello di sicurezza

llm-wiki-kiss è intenzionalmente single-tenant:

- un processo serve una sola `WIKI_ROOT`;
- clienti differenti devono usare processi, utenti e root differenti;
- MCP stdio e CLI ereditano i permessi dell'utente locale;
- REST è limitata al loopback dagli script ufficiali;
- MCP di rete richiede TLS e Bearer token;
- senza token il livello HTTP resta fail-closed;
- le scritture coordinate funzionano soltanto se passano da `WikiStorage`.

Il progetto non protegge i dati da un amministratore della macchina, da un
processo con gli stessi permessi filesystem o da script che accedono
direttamente alla root.

## Gestione dei segreti

- `.wiki-kiss.env` e le skill generate contengono credenziali reali.
- Non committare `.wiki-kiss.env`, chiavi TLS o `.agents/skills/generated/`.
- Usa root separate e token differenti per installazioni differenti.
- Dopo una possibile esposizione esegui `scripts/configure.sh --rotate-token` e
  rigenera soltanto le skill autorizzate.
- Trasmetti il Bearer token esclusivamente tramite HTTPS.
- Per servizi pubblici usa certificati attendibili e limita l'accesso anche a
  livello di firewall o reverse proxy.

## Dipendenze e verifiche

Le pull request eseguono test, Ruff, validazione Bash e scansione Gitleaks. Le
dipendenze vengono monitorate tramite Dependabot.
