# Secrets

Compose mounts every credential from this directory as a **file**, not as an
environment variable, and exports a `*_FILE` variable pointing at it.

The reason is not ceremony. An environment variable is visible in
`docker inspect`, in `/proc/<pid>/environ`, and in the output of any process
listing that dumps its environment. A mounted file is visible only to the process
that reads it. `mansour_common.config.read_secret` therefore prefers the `_FILE`
form and falls back to the plain variable only for local development.

**Nothing in this directory is committed.** `.gitignore` excludes `secrets/`.

## Create the secrets before the first `docker compose up`

```bash
mkdir -p infra/secrets

# 32 bytes of entropy, no trailing newline concerns — read_secret strips it.
openssl rand -base64 32 > infra/secrets/postgres_password
openssl rand -base64 32 > infra/secrets/redis_password

chmod 600 infra/secrets/*
```

On Windows, without OpenSSL:

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
[Convert]::ToBase64String($bytes) | Out-File -NoNewline -Encoding ascii infra/secrets/postgres_password
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
[Convert]::ToBase64String($bytes) | Out-File -NoNewline -Encoding ascii infra/secrets/redis_password
```

## In production

This directory is a development convenience. A real deployment uses Docker Swarm
secrets, Kubernetes secrets backed by a KMS, or HashiCorp Vault. The application
code does not change: it reads `POSTGRES_PASSWORD_FILE` and
`REDIS_PASSWORD_FILE` wherever the orchestrator chose to mount them.

## What must never be here

Camera RTSP credentials. The `cameras.source_url` column holds a **reference**
into the secret store, never the credential itself — an RTSP URL with an embedded
password is the single most commonly leaked value in any CCTV deployment
(`docs/architecture/data-model.md`, Operational SRS `CFG-006`).
