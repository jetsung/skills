# Self-hosting the sync server

Atuin's sync server (`atuin-server`) can be hosted anywhere. It only ever sees ciphertext, but you still want TLS.

## Client side

Point clients at your host by editing `config.toml`:

```toml
sync_address = "https://atuin.example.com"
```

If you run behind a path prefix, set `path` on the server side; the client will use it automatically.

## Server quickstart

Prebuilt binaries and an installer ship with every release:

```sh
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/atuinsh/atuin/releases/latest/download/atuin-server-installer.sh | sh
atuin-server start
```

Server config lives at `~/.config/atuin/server.toml` — separate from the client's `config.toml`.

```toml
host = "0.0.0.0"
port = 8888
open_registration = true
db_uri = "postgres://user:pass@host/db"
```

Or as env vars: `ATUIN_HOST`, `ATUIN_PORT`, `ATUIN_OPEN_REGISTRATION`, `ATUIN_DB_URI`.

| Parameter | Default | Notes |
|---|---|---|
| `db_uri` | (required) | Postgres, MySQL, or SQLite URI |
| `host` | `127.0.0.1` | Bind address |
| `port` | `8888` | TCP port |
| `open_registration` | `false` | `true` accepts new signups |
| `path` | (empty) | URL prefix to prepend to all routes |

Database auto-detects by URI prefix (`postgres://`, `mysql://`, `sqlite://`). SQLite creates the file if it doesn't exist. MySQL is Tier 2; Postgres and SQLite are Tier 1.

## TLS

**Required in practice.** Without TLS, passwords travel plaintext. Put nginx / Caddy / Traefik in front and terminate TLS there.

## Docker

Always use a **tagged release**, not `main` or `latest`. Read the release notes before upgrading.

```sh
CONFIG="$HOME/.config/atuin"
mkdir -p "$CONFIG"
chown 1000:1000 "$CONFIG"
docker run -d -v "$CONFIG:/config" ghcr.io/atuinsh/atuin:<TAGGED-RELEASE> start
```

## Docker Compose with Postgres

`docker-compose.yml`:

```yaml
services:
  atuin:
    restart: always
    image: ghcr.io/atuinsh/atuin:<TAGGED-RELEASE>
    command: start
    volumes:
      - "./config:/config"
    ports:
      - 8888:8888
    environment:
      ATUIN_HOST: "0.0.0.0"
      ATUIN_OPEN_REGISTRATION: "true"
      ATUIN_DB_URI: postgres://${ATUIN_DB_USERNAME}:${ATUIN_DB_PASSWORD}@db/${ATUIN_DB_NAME}
      RUST_LOG: info,atuin_server=debug
    depends_on: [db]
  db:
    image: postgres:18
    restart: unless-stopped
    volumes:
      - "./database:/var/lib/postgresql/"
    environment:
      POSTGRES_USER: ${ATUIN_DB_USERNAME}
      POSTGRES_PASSWORD: ${ATUIN_DB_PASSWORD}
      POSTGRES_DB: ${ATUIN_DB_NAME}
      TZ: Europe/London
      PGTZ: Europe/London
```

`.env` next to it:

```ini
ATUIN_DB_NAME=atuin
ATUIN_DB_USERNAME=atuin
ATUIN_DB_PASSWORD=really-insecure
```

```sh
mkdir -p config && chown 1000:1000 config
docker compose up -d
```

### Daily Postgres backups

Add this service:

```yaml
  backup:
    restart: unless-stopped
    image: prodrigestivill/postgres-backup-local
    env_file: [.env]
    environment:
      POSTGRES_HOST: db
      POSTGRES_DB: ${ATUIN_DB_NAME}
      POSTGRES_USER: ${ATUIN_DB_USERNAME}
      POSTGRES_PASSWORD: ${ATUIN_DB_PASSWORD}
      SCHEDULE: "@daily"
      BACKUP_DIR: /db_dumps
      TZ: Europe/London
    volumes:
      - ./db_dumps:/db_dumps
    depends_on: [db]
```

The `./db_dumps` mount must be on a POSIX FS with hard-link and symlink support — not VFAT, exFAT, or SMB/CIFS.

## Kubernetes

K8s manifests live in `docs/k8s/`:

- `namespaces.yaml` — namespace
- `secrets.yaml` — placeholder for your real secrets
- `atuin.yaml` — Deployment + Service + Ingress + Postgres

Follow the file comments; substitute your own TLS cert and DB password.

## Systemd

A unit file lives at `systemd/atuin-server.service` plus `atuin-server.sysusers`. Install as:

```sh
cp docs/systemd/atuin-server.{service,sysusers} /etc/systemd/system/
systemd-sysusers atuin-server.sysusers
systemctl daemon-reload
systemctl enable --now atuin-server
```

The unit assumes the binary is at `/usr/local/bin/atuin-server` and the config at `/etc/atuin/server.toml`. Adjust `ExecStart` and `WorkingDirectory` as needed.

## China network note

If running on the Chinese network with the `IS_CHINA=1` env var set, replace `docker pull ghcr.io/atuinsh/atuin` with `docker mtrans spull ghcr.io/atuinsh/atuin:<TAG>` (see AGENTS.md).
