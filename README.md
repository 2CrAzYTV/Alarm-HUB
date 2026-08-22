# Alarm Hub

Alarm Hub is a standalone multi-user alarm service. Manual alarms are the core feature; WebComm is an optional integration.

## Features
- User registration and login
- Multiple manual alarms per user
- Repeating weekdays or one-time alarms
- Per-user timezone
- Optional WebComm sync via personal integration token
- API endpoint for upcoming alarms (for iOS Shortcuts / Android automation)
- PostgreSQL backend
- Docker deployment behind a reverse proxy

## Architecture
Alarm Hub never needs direct access to a private WebComm instance. WebComm pushes shift data outbound to Alarm Hub using a per-user token.

## Quick start
```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8080` locally. For public deployment, place Alarm Hub behind a reverse proxy with a valid public HTTPS certificate.

## Environment
See `.env.example`.

## WebComm integration
A logged-in user creates an integration token on the Integrations page. WebComm can then POST future shifts to `/api/v1/integrations/webcomm/shifts` with `Authorization: Bearer <token>`.

The user's WebComm offsets are configurable and may contain any number of values, e.g. `120,90,45` minutes before shift start.
