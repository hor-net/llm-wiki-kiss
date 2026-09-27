# Onboarding LLM agents

`scripts/onboard-agent.sh` generates an Agent Skills compliant skill for a
specific single-wiki instance. The skill contains operational instructions
and connection files tailored with root, MCP HTTPS URL and Bearer token.

> The generated skill contains a real credential. Do not commit it, do not
> attach it to tickets or conversations, and do not share it across customers.

## Prerequisites

Configure the instance first:

```bash
scripts/setup.sh --root ~/private-wiki --https off
# or
scripts/configure.sh --root ~/private-wiki --https off
```

For a remote skill also configure HTTPS and the public URL:

```bash
scripts/configure.sh --https on \
  --host 0.0.0.0 \
  --url https://wiki.example.com/mcp \
  --cert /etc/tls/fullchain.pem \
  --key /etc/tls/privkey.pem
```

## Generation

Automatic mode:

```bash
scripts/onboard-agent.sh --name customer-wiki --label "Customer Wiki"
```

- If HTTPS is enabled and `WIKI_MCP_URL` is set, a remote skill is generated.
- Otherwise a local skill based on MCP stdio and the filesystem path is
  generated.

Force the mode:

```bash
scripts/onboard-agent.sh --name customer-wiki --mode local
scripts/onboard-agent.sh --name customer-wiki --mode https
```

The default destination is:

```text
.agents/skills/generated/<skill-name>/
```

It is git-ignored and discovered as a project skill by clients compatible
with Agent Skills, including Pi. For a global install:

```bash
scripts/onboard-agent.sh --name customer-wiki \
  --target ~/.agents/skills
```

For clients using a different directory:

```bash
scripts/onboard-agent.sh --name customer-wiki \
  --target ~/.claude/skills
```

## Generated content

```text
customer-wiki/
├── SKILL.md
└── references/
    ├── connection.json
    └── mcp-config.json
```

- `SKILL.md`: description, triggers, workflow and rules to keep secrets safe.
- `connection.json`: mode, root, URL and token of the instance.
- `mcp-config.json`: ready-to-adapt local or Streamable HTTPS MCP
  configuration.

Directories and files are created with modes `0700` and `0600` respectively.
The token is not printed during onboarding.

## Update and rotation

The script does not overwrite an existing skill without consent:

```bash
scripts/onboard-agent.sh --name customer-wiki --force
```

After a token rotation regenerate every authorised skill:

```bash
scripts/configure.sh --rotate-token
scripts/onboard-agent.sh --name customer-wiki --force
```

A stale skill keeps the revoked token and will fail to connect. This is
intentional.

## Revoking an agent

Because the instance shares a single token, there are no per-agent tokens.
To revoke a skill or an agent:

1. delete the skill directory;
2. rotate the instance token;
3. regenerate only the still-authorised skills.

For customer isolation always use separate containers, roots,
configurations and tokens.
