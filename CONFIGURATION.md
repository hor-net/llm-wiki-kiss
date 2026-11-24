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

## OAuth for MCP HTTPS (Gemini / Auth0)

Static Bearer remains the default. OAuth is opt-in and replaces static Bearer
**for that MCP process**. It exposes only `list_pages`, `read_page`, and
`search`; writing and server prompts are disabled. OAuth users can still read
**all pages under the configured root**. Use a separate root with approved
content and a separate HTTPS endpoint for Gemini. Do not switch an existing
Bearer instance if its clients must keep working. REST, stdio and CLI are not
changed.

1. Pick the public HTTPS URL (e.g. `https://wiki-preview.example.com/mcp`).
   Use that exact URL, including the choice of trailing slash, as the API
   identifier in Auth0, `WIKI_MCP_URL` below, and the server URL in Gemini.
2. In Auth0, create a custom API with the **Auth0** access token profile
   (uses the `azp` client claim), **RS256**, and the permission `wiki:read`.
   Enable RBAC and grant `wiki:read` only to approved users; use a private
   connection and disable public sign-ups. Enable Auth0's
   [Resource Parameter Compatibility Profile](https://auth0.com/ai/docs/mcp/guides/resource-param-compatibility-profile)
   and **Include Issuer in Authorization Responses**, per Auth0's guide.
3. Create a **Regular Web Application** for Gemini. Add the exact callback
   shown by Gemini to Allowed Callback URLs, allow Authorization Code with
   PKCE (S256), and do not enable the Client Credentials grant. Use the
   token endpoint authentication method the client supports. Put the
   Client ID and Client Secret in Gemini; the wiki needs only the Client ID.

Set these variables in the dedicated instance's service environment, or
put the three OAuth-specific variables in its git-ignored `.env` when using
the scripts. Set `WIKI_MCP_URL` via `configure.sh --url` when using the scripts
(the managed `.wiki-kiss.env` takes precedence). Configure the separate
`WIKI_ROOT`, TLS certificate/key and HTTPS enable flag as usual, and install
the updated dependencies before starting.

```dotenv
WIKI_MCP_AUTH_MODE=oauth
WIKI_MCP_OAUTH_ISSUER=https://your-tenant.example.auth0.com/
WIKI_MCP_OAUTH_CLIENT_ID=<Gemini application's client ID>
WIKI_MCP_URL=https://wiki-preview.example.com/mcp
```

The public HTTPS endpoint must route both `/mcp` and
`/.well-known/oauth-protected-resource/mcp` to this instance (also route
the well-known URL with a trailing slash if that is how the resource URL
is configured). An unauthenticated request to `/mcp` should return `401`
with a `WWW-Authenticate` resource metadata URL. After connecting Gemini,
verify it can list and read a test page and sees no write tools. Do not
expose REST remotely. To stop serving OAuth, stop the separate instance;
no production Bearer configuration needs to change.

## REST API

The REST API uses `WIKI_MCP_TOKEN`, but the `start-rest.sh` script
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
