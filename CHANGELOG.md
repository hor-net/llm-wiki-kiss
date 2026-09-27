# Changelog

Le modifiche rilevanti sono documentate in questo file. Il formato segue
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) e il progetto usa
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0]

### Added

- CLI locale per lista, lettura, ricerca, scrittura, append, statistiche e indici.
- Lock di scrittura per root tra thread e processi.
- Scritture atomiche di pagine e indici.
- Setup e configurazione persistente di root, token e HTTPS.
- Attivazione e spegnimento espliciti dell'interfaccia MCP HTTPS.
- Autenticazione fail-closed condivisa da MCP HTTPS e REST locale.
- Generazione di Agent Skills personalizzate con configurazione MCP protetta.
- Documentazione per configurazione, onboarding, sicurezza e contributi.
- Test concorrenti, CLI, configurazione, onboarding e autenticazione.

### Changed

- Architettura semplificata a un solo wiki e un solo token per processo.
- REST limitata al loopback dagli script ufficiali.
- Operazioni filesystem MCP spostate fuori dall'event loop.
- Licenza aggiornata ad AGPL-3.0-or-later.

### Removed

- Routing e configurazione multi-wiki nello stesso processo.

## [0.2.0]

### Added

- Trasporto MCP Streamable HTTP con autenticazione Bearer.

[Unreleased]: https://github.com/hor-net/llm-wiki-kiss/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/hor-net/llm-wiki-kiss/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/hor-net/llm-wiki-kiss/releases/tag/v0.2.0
