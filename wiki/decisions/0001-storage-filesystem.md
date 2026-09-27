# ADR 0001 — Filesystem storage

## Status

Accepted.

## Context

The wiki must stay readable without external services, databases or
proprietary formats. Different agents need to query the same knowledge base
through a stable interface.

## Decision

Pages are UTF-8 Markdown or HTML files under a single configured root.
Indexes are derived deterministically from the files. Writes go through
`WikiStorage`, use a per-root lock and rely on atomic publish.

## Consequences

- backup and migration consist in copying the directory;
- Git can version the content;
- search and indexes stay simple;
- there are no distributed transactions or database queries;
- scripts that write directly to the files bypass the coordination.
