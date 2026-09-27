# Changelog

All notable changes are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0]

### Added

- Local CLI for listing, reading, searching, writing, appending, statistics
  and indexes.
- Per-root write lock shared by threads and processes.
- Atomic writes for pages and indexes.
- Persistent setup and configuration of root, token and HTTPS.
- Explicit on/off control of the MCP HTTPS interface.
- Fail-closed authentication shared by MCP HTTPS and the local REST API.
- Generation of personalised Agent Skills with protected MCP configuration.
- Documentation for configuration, onboarding, security and contributions.
- Concurrent, CLI, configuration, onboarding and authentication tests.

### Changed

- Architecture simplified to one wiki and one token per process.
- REST limited to the loopback by the official scripts.
- MCP filesystem operations moved out of the event loop.
- Licence updated to AGPL-3.0-or-later.

### Removed

- Multi-wiki routing and configuration inside the same process.

## [0.2.0]

### Added

- MCP Streamable HTTP transport with Bearer authentication.

[Unreleased]: https://github.com/hor-net/llm-wiki-kiss/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/hor-net/llm-wiki-kiss/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/hor-net/llm-wiki-kiss/releases/tag/v0.2.0
