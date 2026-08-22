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

## Configuration principle
Alarm Hub does **not** use a `.env` file. Runtime configuration should be provided directly through the Docker/Unraid template wherever possible.

The included Unraid template is located at:

```text
unraid/alarm-hub.xml
```

It contains the relevant container settings and environment variables, including the WebUI port, database connection, application secret, timezone and secure-session setting.

## Architecture
Alarm Hub never needs direct access to a private WebComm instance. WebComm pushes shift data outbound to Alarm Hub using a per-user token.

## Docker
The application image listens on port `8080`. For Unraid, use the included template. For another Docker host, pass the required environment variables directly to the container or through your orchestration platform rather than using a `.env` file.

Required runtime settings:

```text
DATABASE_URL
SECRET_KEY
```

Optional/defaulted settings:

```text
DEFAULT_TIMEZONE=Europe/Berlin
SESSION_HTTPS_ONLY=true
```

For public deployment, place Alarm Hub behind a reverse proxy with a valid public HTTPS certificate and keep `SESSION_HTTPS_ONLY=true`.

## WebComm integration
A logged-in user creates an integration token on the Integrations page. WebComm can then POST future shifts to `/api/v1/integrations/webcomm/shifts` with `Authorization: Bearer <token>`.

The user's WebComm offsets are configurable and may contain any number of values, e.g. `120,90,45` minutes before shift start.

## Agenda
- Add an optional **All-in-One / embedded PostgreSQL mode** for simpler Unraid installation.
- Default mode should allow Alarm Hub and PostgreSQL to run from one container while keeping the database persistent outside the disposable container filesystem.
- Keep the current external PostgreSQL setup available as an advanced mode.
- Planned configuration concept: `DATABASE_MODE=embedded` by default, with `DATABASE_MODE=external` plus `DATABASE_URL` for external databases.
- Update the Unraid template accordingly so normal users do not need to install and configure a separate PostgreSQL container.
