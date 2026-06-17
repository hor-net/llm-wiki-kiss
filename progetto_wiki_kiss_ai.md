# Progetto Wiki KISS self-hosted per agenti AI

## Obiettivo
Creare una knowledge base privata, semplice e controllabile al 100%, accessibile da più modelli e agenti AI tramite MCP, senza introdurre layer software superflui.

## Principi
- KISS prima di tutto.
- I contenuti vivono in file Markdown o HTML statici.
- Nessun database obbligatorio.
- Nessun CMS pesante.
- Accesso uniforme per gli agenti tramite MCP.
- Possibile API HTTP minimale come fallback.

## Idea generale
Il progetto separa chiaramente tre livelli:

1. **Memoria conversazionale / operativa**
   - Gestita dal sistema dell’agente, per esempio QMD o equivalente.
   - Serve per recall di sessioni, task correnti e contesto breve.

2. **Knowledge base / wiki**
   - File `.md` o `.html` organizzati in cartelle.
   - Link ipertestuali tra pagine e sezioni.
   - Contenuto leggibile anche fuori dal sistema.

3. **Interfaccia per AI**
   - Un server MCP che espone strumenti standardizzati.
   - Opzionale: una API HTTP minimale.
   - Permette l’uso da Open Cloud, Claude Code, Perplexity e altri client compatibili.

## Struttura del contenuto
Esempio di organizzazione:

- `wiki/index.md`
- `wiki/projects/`
- `wiki/notes/`
- `wiki/decisions/`
- `wiki/references/`
- `wiki/assets/`

Ogni pagina può linkare le altre con percorsi relativi:

- `[Pagina correlata](../notes/nome-nota.md)`
- `[Sezione](#titolo-sezione)`

## Funzioni minime del sistema
Il server MCP dovrebbe offrire almeno questi tool:

- `list_pages`: elenco delle pagine disponibili.
- `read_page`: lettura del contenuto di una pagina.
- `search`: ricerca testuale nel wiki.
- `write_page`: creazione o aggiornamento di una pagina.
- `append_note`: aggiunta rapida di un’informazione o log.

## Perché MCP
MCP è il livello giusto perché crea un contratto unico tra il wiki e gli agenti AI.
Invece di costruire integrazioni diverse per ogni modello, esponi un solo servizio standard.

Questo rende possibile:
- usare lo stesso wiki da più agenti;
- mantenere il contenuto centrale e coerente;
- ridurre duplicazioni di integrazione;
- restare compatibili con client diversi.

## Perché non un CMS pesante
Un CMS o una piattaforma wiki completa aggiunge spesso:
- database;
- autenticazione complessa;
- UI ricca ma più fragile;
- più manutenzione;
- più lock-in operativo.

Qui l’obiettivo è opposto: massima semplicità, massima portabilità, minimo attrito.

## Stack consigliato
### Storage
- Markdown puro, preferibilmente.
- HTML solo se serve presentazione statica particolare.
- Git per versionamento.

### Accesso umano
- Editor di testo o editor Markdown.
- File system locale o server Git.
- Eventuale sito statico per navigazione umana.

### Accesso AI
- Server MCP dedicato.
- Eventuale API REST minima come fallback.

### Ricerca
- Full-text search semplice.
- Se necessario, in seguito si può aggiungere indice semantico, ma non è necessario all’inizio.

## Vantaggi
- Controllo totale dei dati.
- Nessun lock-in.
- Backup semplici.
- Migrazione facile.
- Compatibilità con più agenti AI.
- Debug e manutenzione molto più facili.
- Possibilità di crescere per gradi.

## Limiti
- Meno funzioni automatiche rispetto a Notion o NotebookLM.
- Più disciplina richiesta nella scrittura e organizzazione.
- Nessun backlink automatico o database nativo, a meno di aggiungerli in seguito.
- La qualità dipende molto dalla convenzione dei nomi e dalla struttura.

## Workflow operativo
1. Scrivere note e documenti in Markdown.
2. Organizzarli in cartelle logiche.
3. Collegare le pagine con link relativi.
4. Esporre il contenuto tramite MCP.
5. Usare il wiki come fonte comune per tutti gli agenti.
6. Tenere QMD o memoria equivalente per il contesto breve e dinamico.

## Regola pratica
La memoria serve a ricordare il contesto della conversazione.
Il wiki serve a conservare conoscenza stabile e condivisa.
MCP serve a rendere quella conoscenza accessibile agli agenti.

## Conclusione
La soluzione più semplice e robusta è un wiki statico in Markdown o HTML, con link ipertestuali e un piccolo server MCP davanti.
È un compromesso molto buono tra controllo, semplicità e interoperabilità con diversi modelli AI.
