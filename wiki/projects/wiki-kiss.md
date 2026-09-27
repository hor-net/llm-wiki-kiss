# llm-wiki-kiss

Example project page for this repository.

## Goal

Provide LLM agents and other agents with a persistent knowledge base made
of text files, accessible locally through a CLI or MCP stdio, and optionally
through authenticated MCP HTTPS.

## Principles

- one wiki per process;
- no database;
- parallel reads and coordinated writes;
- configuration and backup must remain understandable;
- different customers are isolated through distinct processes and
  filesystems.

## Decisions

- [Filesystem storage](../decisions/0001-storage-filesystem.md)
