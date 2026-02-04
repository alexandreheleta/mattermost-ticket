# Mattermost Ticket

A lightweight FastAPI service that adds a `/ticket` slash command to Mattermost. Users fill out a dialog form and a formatted ticket is posted in the channel as a thread.

## How it works

1. User types `/ticket` in a Mattermost channel
2. A dialog form opens (cluster, VM/resource, problem description, network info)
3. On submit, the service posts a formatted ticket message in the channel
4. The user receives an ephemeral confirmation with the ticket ID

Each ticket gets a unique ID (`Ticket-YYYYMMDD-XXXX`) and is tagged in post metadata for easy identification.

## Setup

### Mattermost configuration

1. Create a **Bot Account** in Mattermost and save its token (`BOT_TOKEN`)
2. Create a **Slash Command** (trigger word: `ticket`, URL: `http://your-host:8080/ticket`, method: POST) and save its token (`SLASH_TOKEN`)
3. In **System Console > Integrations**, enable custom slash commands

### Run with Podman/Docker

```bash
podman build -t mattermost-ticket .

podman run -d \
  --name ticket-service \
  --restart always \
  -p 8080:8080 \
  -e MATTERMOST_URL="https://your-mattermost-instance" \
  -e BOT_TOKEN="bot-token-here" \
  -e SLASH_TOKEN="slash-command-token-here" \
  -e CALLBACK_URL="http://this-service-host:8080" \
  mattermost-ticket
```

### Environment variables

| Variable | Description |
|---|---|
| `MATTERMOST_URL` | Mattermost server URL |
| `BOT_TOKEN` | Bot account access token (service -> Mattermost) |
| `SLASH_TOKEN` | Slash command verification token (Mattermost -> service) |
| `CALLBACK_URL` | Public URL of this service, reachable by Mattermost |

### SSL / internal CA

If your Mattermost uses an internal CA, mount the certificate bundle and set `SSL_CERT_FILE`:

```bash
podman run -d \
  ...
  -v /etc/pki/tls/certs/ca-bundle.crt:/etc/ssl/certs/ca-bundle.crt:ro \
  -e SSL_CERT_FILE="/etc/ssl/certs/ca-bundle.crt" \
  mattermost-ticket
```

## Health check

```
GET /health
```

Returns `{"status": "ok"}`.

## Air-gapped deployment

Build the image on a connected machine, then transfer it:

```bash
podman save -o mattermost-ticket.tar mattermost-ticket
# transfer the .tar file to the target host
podman load -i mattermost-ticket.tar
```
