# Single-wiki configuration

llm-wiki-kiss runs **exactly one wiki per process or container**. The
operational configuration is persisted in `.wiki-kiss.env`, which is
git-ignored and created with mode `0600`.

## Initial setup

The setup script installs dependencies and CLI commands, configures the root
and generates a random 256-bit token:

```bash
scripts/setup.sh --with-dev --root ~/private-wiki --https off
```

When it finishes it prints:

```text
WIKI_MCP_TOKEN=<generated-token>
```

Keep the token in a password manager. The same token protects MCP HTTPS and
the local REST API. MCP stdio and the CLI do not use a token because they
communicate locally and rely on filesystem permissions.

If the certificate and key already exist, the setup can also start HTTPS:

```bash
scripts/setup.sh --root /srv/wiki/customer-a --https on \
  --host 0.0.0.0 --port 8766 \
  --url https://wiki.example.com/mcp \
  --cert /etc/tls/wiki.crt --key /etc/tls/wiki.key
```

To skip the configuration step during an upgrade:

```bash
scripts/setup.sh --no-config
```

## Interactive configuration

```bash
scripts/configure.sh
```

The script asks for the root and whether to enable MCP HTTPS. The root is
created if it does not exist. HTTPS is disabled by default and cannot be
enabled without a readable certificate and private key.

Non-interactive configuration:

```bash
scripts/configure.sh --root /srv/wiki/customer-a --https off
```

## Token

Show the configured token:

```bash
scripts/configure.sh --show-token
```

Rotate it at any time:

```bash
scripts/configure.sh --rotate-token
```

Rotation restarts any running HTTP services so that the old token stops
working immediately. The token must never be passed in URLs, committed or
shared between customers.

## Turning MCP HTTPS on and off

### Trusted certificate

For a service reachable from other machines use a PEM certificate and key
issued for the DNS name of the server, or terminate TLS in a reverse proxy.
For direct TLS handled by the project:

```bash
scripts/configure.sh \
  --https on \
  --host 0.0.0.0 \
  --port 8766 \
  --url https://wiki.example.com/mcp \
  --cert /etc/letsencrypt/live/wiki.example.com/fullchain.pem \
  --key /etc/letsencrypt/live/wiki.example.com/privkey.pem
```

The command saves the configuration and starts `mcp-http`. Endpoint:

```text
https://HOST:8766/mcp
```

### Self-signed certificate for local testing

A self-signed certificate is suitable only for tests or controlled networks
and must be explicitly trusted by the client:

```bash
mkdir -p var/tls
chmod 700 var/tls
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -keyout var/tls/wiki-kiss.key \
  -out var/tls/wiki-kiss.crt \
  -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
chmod 600 var/tls/wiki-kiss.key

scripts/configure.sh --https on \
  --host 127.0.0.1 \
  --cert var/tls/wiki-kiss.crt \
  --key var/tls/wiki-kiss.key
```

### Turning it off

```bash
scripts/configure.sh --https off
```

This stops the HTTPS process and prevents `start-mcp-http.sh` from
accidentally restarting it. MCP stdio and the CLI remain available offline:

```bash
scripts/wiki.sh search "local query"
.venv/bin/python -m mcp_server --root /path/wiki
```

To turn it back on using the saved certificate and key:

```bash
scripts/configure.sh --https on
```

Current status:

```bash
scripts/status.sh
```

## REST API

The REST API uses the same `WIKI_MCP_TOKEN`, but the `start-rest.sh` script
only accepts loopback binding (`127.0.0.1`, `localhost`, `::1`). For remote
access use MCP HTTPS. REST also stays fail-closed if the token is not
configured.

## The `.wiki-kiss.env` file

The variables managed are:

```dotenv
WIKI_ROOT=/absolute/path/wiki
WIKI_MCP_TOKEN=<secret>
WIKI_HTTPS_ENABLED=0
WIKI_HTTP_HOST=127.0.0.1
WIKI_HTTP_PORT=8766
WIKI_MCP_URL=https://wiki.example.com/mcp
WIKI_TLS_CERT=/path/cert.pem
WIKI_TLS_KEY=/path/key.pem
```

Do not edit or copy this file between customers. Each container must have an
independent root, token, certificate and configuration.

To generate an LLM skill containing the instance URL/path and credentials,
see [`ONBOARDING.md`](ONBOARDING.md).
