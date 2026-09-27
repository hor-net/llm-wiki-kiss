# ADR 0001 — Storage su filesystem

## Stato

Accettata.

## Contesto

Il wiki deve restare leggibile senza servizi esterni, database o formati
proprietari. Agenti diversi devono poter consultare la stessa knowledge base
tramite un'interfaccia stabile.

## Decisione

Le pagine sono file Markdown o HTML UTF-8 sotto una singola root configurata.
Gli indici sono derivati deterministicamente dai file. Le scritture passano da
`WikiStorage`, usano un lock per root e pubblicazione atomica.

## Conseguenze

- backup e migrazione consistono nella copia della directory;
- Git può versionare i contenuti;
- ricerca e indici rimangono semplici;
- non esistono transazioni distribuite o query da database;
- script che scrivono direttamente nei file aggirano il coordinamento.
