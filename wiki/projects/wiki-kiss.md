# llm-wiki-kiss

Esempio di pagina progetto per questo stesso repository.

## Obiettivo

Offrire a LLM e agenti una knowledge base persistente composta da file di testo,
accessibile localmente tramite CLI o MCP stdio e, opzionalmente, tramite MCP
HTTPS autenticato.

## Principi

- un solo wiki per processo;
- niente database;
- letture parallele e scritture coordinate;
- configurazione e backup comprensibili;
- isolamento di clienti differenti tramite processi e filesystem distinti.

## Decisioni

- [Storage su filesystem](../decisions/0001-storage-filesystem.md)
