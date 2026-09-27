# Configurazione single-wiki

llm-wiki-kiss esegue **un solo wiki per processo o container**. La
configurazione operativa è salvata in `.wiki-kiss.env`, escluso da Git e creato
con permessi `0600`.

## Setup iniziale

Lo script di setup installa dipendenze e comandi CLI, configura la root e genera
un token casuale di 256 bit:

```bash
scripts/setup.sh --with-dev --root ~/wiki-privato --https off
```

Al termine stampa:

```text
WIKI_MCP_TOKEN=<token-generato>
```

Conserva il token in un password manager. Lo stesso token protegge MCP HTTPS e
la REST API locale. MCP stdio e la CLI non usano token perché comunicano
localmente e seguono i permessi del filesystem.

Se certificato e chiave esistono già, il setup può anche avviare HTTPS:

```bash
scripts/setup.sh --root /srv/wiki/cliente-a --https on \
  --host 0.0.0.0 --port 8766 \
  --url https://wiki.example.com/mcp \
  --cert /etc/tls/wiki.crt --key /etc/tls/wiki.key
```

Per saltare la configurazione durante un aggiornamento:

```bash
scripts/setup.sh --no-config
```

## Configurazione interattiva

```bash
scripts/configure.sh
```

Lo script chiede la root e se attivare MCP HTTPS. La root viene creata se manca.
HTTPS è disabilitato per default e non può essere attivato senza certificato e
chiave privata leggibili.

Configurazione non interattiva:

```bash
scripts/configure.sh --root /srv/wiki/cliente-a --https off
```

## Token

Mostrare il token configurato:

```bash
scripts/configure.sh --show-token
```

Ruotarlo in qualunque momento:

```bash
scripts/configure.sh --rotate-token
```

La rotazione riavvia gli eventuali servizi HTTP attivi affinché il vecchio
token cessi immediatamente di funzionare. Il token non deve essere passato in URL,
committato o condiviso tra clienti.

## Accendere e spegnere MCP HTTPS

### Certificato attendibile

Per un servizio raggiungibile da altre macchine usa certificato e chiave PEM
rilasciati per il nome DNS del server, oppure termina TLS in un reverse proxy.
Per il TLS diretto gestito dal progetto:

```bash
scripts/configure.sh \
  --https on \
  --host 0.0.0.0 \
  --port 8766 \
  --url https://wiki.example.com/mcp \
  --cert /etc/letsencrypt/live/wiki.example.com/fullchain.pem \
  --key /etc/letsencrypt/live/wiki.example.com/privkey.pem
```

Il comando salva la configurazione e avvia `mcp-http`. Endpoint:

```text
https://HOST:8766/mcp
```

### Certificato self-signed per prove locali

Un certificato self-signed è adatto solo a test o reti controllate e deve essere
esplicitamente considerato attendibile dal client:

```bash
mkdir -p var/tls
chmod 700 var/tls
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -keyout var/tls/wiki-kiss.key \
  -out var/tls/wiki-kiss.crt \
  -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
chmod 600 var/tls/wiki-kiss.key

scripts/configure.sh --https on \
  --host 127.0.0.1 \
  --cert var/tls/wiki-kiss.crt \
  --key var/tls/wiki-kiss.key
```

### Spegnimento

```bash
scripts/configure.sh --https off
```

Questo arresta il processo HTTPS e ne impedisce il riavvio accidentale tramite
`start-mcp-http.sh`. MCP stdio e CLI restano disponibili offline:

```bash
scripts/wiki.sh search "query locale"
.venv/bin/python -m mcp_server --root /percorso/wiki
```

Per riaccendere usando certificato e chiave già salvati:

```bash
scripts/configure.sh --https on
```

Stato corrente:

```bash
scripts/status.sh
```

## REST API

La REST API usa lo stesso `WIKI_MCP_TOKEN` ma lo script `start-rest.sh` accetta
solo binding loopback (`127.0.0.1`, `localhost`, `::1`). Per accesso remoto usa
MCP HTTPS. Anche REST resta fail-closed se il token non è configurato.

## File `.wiki-kiss.env`

Le variabili gestite sono:

```dotenv
WIKI_ROOT=/percorso/assoluto/wiki
WIKI_MCP_TOKEN=<segreto>
WIKI_HTTPS_ENABLED=0
WIKI_HTTP_HOST=127.0.0.1
WIKI_HTTP_PORT=8766
WIKI_MCP_URL=https://wiki.example.com/mcp
WIKI_TLS_CERT=/percorso/certificato.pem
WIKI_TLS_KEY=/percorso/chiave.pem
```

Non modificare o copiare questo file tra clienti. Ogni container deve avere
root, token, certificato e configurazione indipendenti.

Per generare una skill LLM contenente URL/path e credenziali dell'istanza,
consulta [`ONBOARDING.md`](ONBOARDING.md).
