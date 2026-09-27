---
name: "wiki-kiss-bridge"
description: "Integrates a KISS wiki as a stable knowledge source for an AI agent. Invoke when the agent needs to read, search, write or cite wiki content via MCP, or when it needs persistent context between sessions."
---

# Wiki KISS — Bridge for AI agents

This skill explains to an AI agent (Claude Code, Claude Desktop, Open
Cloud, Perplexity, …) how to interact with a KISS wiki instance exposed via
MCP.

## When to invoke this skill

- The user asks to consult, save or organise knowledge in the wiki.
- The user mentions "the wiki", "wiki-kiss", "KISS wiki" or paths that
  start with `wiki/`, `notes/`, `decisions/`, `projects/`, `logs/`.
- The user wants shared information to be **persistent** and not lost
  when the session ends.
- The user asks "remember this", "save this", "jot it down", "search for"
  in a context where the wiki is the canonical source.

Do not invoke when:
- The user only wants ephemeral answers or pure computation.
- The wiki MCP client is not available (no `list_pages` tool, etc.).

## The five available tools

The `wiki-kiss` MCP server exposes:

| Tool          | Purpose                                                   |
| ------------- | --------------------------------------------------------- |
| `list_pages`  | Lists pages (optional `subdir` filter).                   |
| `read_page`   | Reads the content of a page by `path`.                    |
| `search`      | Case-insensitive full-text, returns snippet and line.     |
| `write_page`  | Creates or overwrites a page.                             |
| `append_note` | Quickly appends text (default: today's log).              |

All paths are **relative** to the wiki root and separated by `/`.

## Recommended workflow

### 1. Before writing: understand what exists

```
list_pages  →  search(query="...")  →  read_page(path=...)
```

Never overwrite a page without first reading its content. Before creating a
new page, check whether something similar already exists (use `list_pages`
or `search`).

### 2. Pick the right path

The wiki follows a folder convention. Map the user's intent like this:

| Intent                              | Folder        | Example                              |
| ------------------------------------ | ------------- | ------------------------------------ |
| Project documentation                | `projects/`   | `projects/wiki-kiss.md`              |
| Quick notes, ideas, observations     | `notes/`      | `notes/2026-06-17-idea-x.md`         |
| Technical decisions (ADR)            | `decisions/`  | `decisions/0002-use-fastapi.md`      |
| External links and references        | `references/` | `references/mcp-spec.md`             |
| Append-only log of events/activity   | `logs/`       | `logs/2026-06-17.md` (auto)          |

Conventions:
- **Markdown** files (`.md`), UTF-8.
- `kebab-case` filenames.
- Every page starts with a level-1 title (`# Title`).
- Internal links are **relative**: `[another page](../notes/idea.md)`.

### 3. Writing with `write_page`

```json
{
  "path": "notes/idea-on-indexing.md",
  "content": "# Idea on indexing\n\nText...\n",
  "overwrite": false
}
```

Rules:
- `overwrite: false` by default; set it to `true` only when the user
  explicitly asked, or when you have just read the page and verified its
  content.
- When the extension is missing, `.md` is added automatically.
- Always include a minimal heading: `# Title` as the first line.

### 4. Quick notes with `append_note`

For logs, micro-updates, automatic timestamps:

```json
{ "content": "Decided to postpone the refactor.", "heading": "Blocker" }
```

Without `path`, the content is appended to `logs/YYYY-MM-DD.md` (UTC). Use
it by default for any "remember this" or "jot this down".

### 5. Searching with `search`

```json
{ "query": "MCP", "max_results": 10, "subdir": "notes" }
```

The snippet includes ~60 characters of context to the left and right of
the match. Use `subdir` to scope the search.

## Best practices

- **Always cite the source**: when answering using the wiki, include the
  page path (e.g. "Source: `decisions/0001-storage-filesystem.md`").
- **Do not duplicate**: before writing a new page, check whether one
  semantically equivalent already exists.
- **Write for humans too**: the content must remain useful when opened in
  a plain text editor.
- **Respect the structure**: if the user asks for an ADR, put it in
  `decisions/`, not in `notes/`.
- **Traceability log**: for any significant action, append a note to the
  daily log with `append_note` (specifying a `heading` when useful).

## Common mistakes to avoid

- Passing paths with `..` or a leading slash: they will be rejected.
- Forgetting the extension: the system adds it, but it is better to be
  explicit.
- Overwriting without reading first: you risk losing information.
- Inventing content that does not exist in the wiki: if `search` does not
  find something, say so and do not fill the gap.

## Example interaction

1. The user asks: "Do you remember what we decided about storage?"
2. `search({ "query": "storage" })` → finds
   `decisions/0001-storage-filesystem.md`.
3. `read_page({ "path": "decisions/0001-storage-filesystem.md" })` →
   content.
4. Reply: "Yes, see `decisions/0001-storage-filesystem.md`: we adopted
   filesystem + Markdown, no database."

## Example writing

1. The user asks: "Save a note: today we started the refactor of search."
2. `append_note({ "content": "Started the search refactor.", "heading": "Refactor" })`
   → appends to `logs/2026-06-17.md`.

## Availability

The skill assumes that the `wiki-kiss` MCP tool is already configured in
the user's client. If `list_pages` fails with a connection error, suggest
running `scripts/install-mcp-client.sh` and restarting the client.
