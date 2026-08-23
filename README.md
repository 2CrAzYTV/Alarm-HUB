# Alarm Hub

Alarm Hub is a standalone multi-user alarm service. Manual alarms are the core feature; WebComm is an optional integration.

## Features
- User registration and login
- Multiple manual alarms per user
- Repeating weekdays or one-time alarms
- Per-user timezone
- Optional WebComm sync via personal integration token
- Optional direct WebComm import
- API endpoint for upcoming alarms (for iOS Shortcuts / Android automation)
- Embedded PostgreSQL by default
- Optional external PostgreSQL for advanced setups
- Docker deployment behind a reverse proxy

## Configuration principle
Alarm Hub does **not** use a `.env` file. Runtime configuration should be provided directly through the Docker/Unraid template wherever possible.

For a normal installation, only the Alarm-HUB container is required. PostgreSQL is included in the image and stores its persistent database below `/config/postgres`.

## Database modes

### Embedded PostgreSQL (default)

```text
DATABASE_MODE=embedded
```

This is the recommended mode for normal Unraid installations. Alarm-HUB starts its own PostgreSQL instance inside the same container. The database only listens on a local Unix socket and is not exposed on the Docker network.

Persist `/config` on the host, for example:

```text
/mnt/user/appdata/alarm-hub -> /config
```

A container update or Force Update therefore does not delete the database.

If no `SECRET_KEY` is supplied in embedded mode, Alarm-HUB automatically generates a strong random key on first start and stores it persistently as `/config/secret_key`. This avoids extra setup while keeping sessions and encrypted direct-WebComm passwords stable across container updates.

### External PostgreSQL (advanced)

```text
DATABASE_MODE=external
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
```

Use this only if you deliberately want to manage PostgreSQL separately. Existing installations that already define `DATABASE_URL` but do not yet define `DATABASE_MODE` continue to use their external PostgreSQL database for backward compatibility.

A legacy/advanced Unraid PostgreSQL template is retained as documentation at:

```text
unraid/alarm-hub-postgres.xml.example
```

It deliberately does not use the `.xml` extension so Community Apps does not publish it as a separate application. Rename or copy it to an `.xml` file only for a manual advanced deployment.

## Docker
The application image listens on port `8080`.

Recommended settings for a new local Unraid installation:

```text
DATABASE_MODE=embedded
DEFAULT_TIMEZONE=Europe/Berlin
SESSION_HTTPS_ONLY=false
```

`SECRET_KEY` is optional in embedded mode because it is generated persistently under `/config` if omitted. Advanced/external installations may continue supplying their own existing `SECRET_KEY`; changing an established key invalidates sessions and prevents decryption of previously saved direct-WebComm passwords.

For public deployment, place Alarm Hub behind a reverse proxy with a valid public HTTPS certificate and set `SESSION_HTTPS_ONLY=true`.

## WebComm integration
A logged-in user can create an integration token on the Integrations page. WebComm Calendar Sync can then POST future shifts to `/api/v1/integrations/webcomm/shifts` with `Authorization: Bearer <token>`.

Alternatively, users without WebComm Calendar Sync can configure the direct WebComm import inside Alarm-HUB. Direct-import credentials are stored per user, with the password encrypted before it is written to PostgreSQL.

The user's WebComm offsets are configurable and may contain any number of values, e.g. `120,90,45` minutes before shift start.

## Unraid
For a new standard setup, install only `Alarm-HUB`. The normal user only needs the WebUI port and `/config` appdata path; PostgreSQL and the application secret are handled automatically. No second PostgreSQL container and no `.env` file are required.

The canonical Community Apps template is maintained in the central 2CrAzYTV repository:

```text
2CrAzYTV/unraid-community-apps/templates/alarm-hub.xml
```

A synchronized project-local template remains at `templates/alarm-hub.xml` for source review and validation. An older/manual template is retained as `unraid/alarm-hub.xml.example` for reference without being published as a separate Community Apps application. For existing or advanced external-database deployments, set `DATABASE_MODE=external` and keep the existing `DATABASE_URL` and `SECRET_KEY`.

## Community Apps submission
Community Apps metadata for Alarm-HUB is published from the central repository `2CrAzYTV/unraid-community-apps` together with the other 2CrAzYTV applications. This repository remains the source-of-truth for the Alarm-HUB application code, README, support and container build.

- The canonical CA template is `2CrAzYTV/unraid-community-apps/templates/alarm-hub.xml`.
- `templates/alarm-hub.xml` in this repository is a project-local mirror whose `TemplateURL` points to the central canonical file.
- `icon.png` and `icon.svg` remain the Alarm-HUB application artwork.
- `LICENSE` provides the OSI-approved MIT license.
- `.github/workflows/community-apps.yml` validates the local mirror and its reference to the central template.
- Files below `unraid/` use the `.xml.example` suffix so they remain documentation/manual examples and are not published as additional Community Apps entries.

Before publishing changes, run **Validate** and **Scan** in the Unraid Community Apps submission portal against the central repository. The portal is the source of truth for final acceptance and may report requirements that are newer than the repository checks.

## Support
Please use GitHub Issues for bugs and support requests. Do not post passwords, API tokens, database credentials, session secrets, or other private data in issues or logs.

## License
Alarm-HUB is licensed under the MIT License. See `LICENSE`.
