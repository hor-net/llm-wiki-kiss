# Onboarding degli agenti LLM

`scripts/onboard-agent.sh` genera una skill conforme al formato **Agent Skills**
per una specifica istanza single-wiki. La skill contiene istruzioni operative e
file di connessione personalizzati con root, URL MCP HTTPS e Bearer token.

> La skill generata contiene una credenziale reale. Non committarla, non
> allegarla a ticket o conversazioni e non condividerla tra clienti.

## Prerequisiti

Prima configura l'istanza:

```bash
scripts/setup.sh --root ~/wiki-privato --https off
# oppure
scripts/configure.sh --root ~/wiki-privato --https off
```

Per una skill remota configura anche HTTPS e la URL pubblica:

```bash
scripts/configure.sh --https on \
  --host 0.0.0.0 \
  --url https://wiki.example.com/mcp \
  --cert /etc/tls/fullchain.pem \
  --key /etc/tls/privkey.pem
```

## Generazione

Modalità automatica:

```bash
scripts/onboard-agent.sh --name customer-wiki --label "Customer Wiki"
```

- Se HTTPS è acceso e `WIKI_MCP_URL` è disponibile, genera una skill remota.
- Altrimenti genera una skill locale basata su MCP stdio e filesystem path.

Forzare la modalità:

```bash
scripts/onboard-agent.sh --name customer-wiki --mode local
scripts/onboard-agent.sh --name customer-wiki --mode https
```

La destinazione predefinita è:

```text
.agents/skills/generated/<nome-skill>/
```

È ignorata da Git e viene scoperta come project skill dai client compatibili
con Agent Skills, incluso Pi. Per installazione globale:

```bash
scripts/onboard-agent.sh --name customer-wiki \
  --target ~/.agents/skills
```

Per client che usano un'altra directory:

```bash
scripts/onboard-agent.sh --name customer-wiki \
  --target ~/.claude/skills
```

## Contenuto generato

```text
customer-wiki/
├── SKILL.md
└── references/
    ├── connection.json
    └── mcp-config.json
```

- `SKILL.md`: descrizione, trigger, workflow e regole per non esporre segreti.
- `connection.json`: modalità, root, URL e token dell'istanza.
- `mcp-config.json`: configurazione MCP locale oppure Streamable HTTPS pronta da
  adattare al client.

Directory e file vengono creati rispettivamente con permessi `0700` e `0600`.
Il token non viene stampato durante l'onboarding.

## Aggiornamento e rotazione

Lo script non sovrascrive una skill esistente senza consenso:

```bash
scripts/onboard-agent.sh --name customer-wiki --force
```

Dopo una rotazione del token occorre rigenerare tutte le skill autorizzate:

```bash
scripts/configure.sh --rotate-token
scripts/onboard-agent.sh --name customer-wiki --force
```

Una skill vecchia continuerà a contenere il token revocato e non riuscirà più a
connettersi. Questo comportamento è intenzionale.

## Revoca di un agente

Con un singolo token per istanza non esistono token separati per agente. Per
revocare una skill o un agente:

1. elimina la directory della skill;
2. ruota il token dell'istanza;
3. rigenera soltanto le skill ancora autorizzate.

Per isolamento tra clienti usa sempre container, root, configurazioni e token
differenti.
