"""Service configuration.

Every service subclasses `ServiceSettings`. Values come from the environment;
secrets come from the environment *as references* wherever the deployment
supports it (Docker secrets mount a file, and `*_FILE` variables point at it).

Two deliberate choices:

* **Fail fast.** An invalid configuration raises `ConfigurationError` at import
  of the settings object, before the service binds a port. A service that starts
  with a wrong density threshold is worse than one that refuses to start.
* **Secrets are `SecretStr`.** They do not appear in `repr()`, in a traceback,
  or in a settings dump. The logging pipeline redacts them again on the way out
  (`mansour_common.logging`), because defence in depth is cheap here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import Field, SecretStr, field_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from mansour_common.errors import ConfigurationError

Environment = Literal["development", "test", "staging", "production"]
LogRender = Literal["json", "console"]

SettingsT = TypeVar("SettingsT", bound=BaseSettings)


def read_secret(name: str, default: str | None = None) -> str | None:
    """Resolve a secret from `NAME_FILE` (Docker secret) or `NAME` (environment).

    The file form wins. Docker and Kubernetes both mount secrets as files, and a
    file is not visible in `docker inspect` or in a process's environment, which
    an environment variable is.
    """
    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationError(
                "secret file could not be read", variable=f"{name}_FILE", path=file_path
            ) from exc
    return os.environ.get(name, default)


class ServiceSettings(BaseSettings):
    """Settings common to every service in the platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        validate_default=True,
    )

    service_name: str = Field(min_length=1)
    environment: Environment = "development"

    log_level: str = "INFO"
    log_render: LogRender = "json"

    #: Port on which the service exposes /healthz, /readyz and /metrics.
    health_port: int = Field(default=8080, ge=1, le=65535)
    health_host: str = "0.0.0.0"  # noqa: S104 — containers must bind all interfaces

    #: Seconds to allow in-flight work to finish after SIGTERM before forcing exit.
    shutdown_grace_seconds: float = Field(default=15.0, gt=0, le=300)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return upper

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


class PostgresSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore", frozen=True)

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    db: str = "mansour"
    user: str = "mansour"
    #: Falls back to the Docker-secret file form when `POSTGRES_PASSWORD` is
    #: unset. Compose mounts the password at `/run/secrets/...` and exports
    #: `POSTGRES_PASSWORD_FILE`, precisely so the credential never appears in
    #: `docker inspect` or in a process's environment.
    password: SecretStr = Field(
        default_factory=lambda: SecretStr(read_secret("POSTGRES_PASSWORD") or "")
    )

    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=5, ge=0, le=100)
    #: Seconds to wait for a connection from the pool before failing the request.
    pool_timeout: float = Field(default=5.0, gt=0)
    #: Recycle connections before PgBouncer or the server closes them underneath us.
    pool_recycle_seconds: int = Field(default=1800, gt=0)
    connect_timeout_seconds: int = Field(default=5, gt=0)

    def dsn(self, *, driver: str = "postgresql+asyncpg") -> str:
        """Build a SQLAlchemy DSN. The password is materialised only here."""
        pw = self.password.get_secret_value()
        return f"{driver}://{self.user}:{pw}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """Redis connection settings. Redis is the event spine (ADR 0007)."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore", frozen=True)

    host: str = "localhost"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)
    password: SecretStr | None = Field(
        default_factory=lambda: (
            SecretStr(secret) if (secret := read_secret("REDIS_PASSWORD")) else None
        )
    )

    socket_timeout_seconds: float = Field(default=5.0, gt=0)
    socket_connect_timeout_seconds: float = Field(default=3.0, gt=0)
    max_connections: int = Field(default=20, ge=1)

    def url(self) -> str:
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


def load(settings_cls: type[SettingsT], **overrides: Any) -> SettingsT:
    """Instantiate a settings class, converting pydantic errors into `ConfigurationError`.

    Services call this at startup. The distinction matters: a pydantic
    `ValidationError` in a traceback is noise, whereas `ConfigurationError`
    carries the field name and is what the operator needs to fix.
    """
    try:
        return settings_cls(**overrides)
    except PydanticValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        raise ConfigurationError(
            "invalid configuration",
            settings=settings_cls.__name__,
            fields=fields,
            detail=exc.errors(include_url=False),
        ) from exc


__all__ = [
    "Environment",
    "PostgresSettings",
    "RedisSettings",
    "ServiceSettings",
    "load",
    "read_secret",
]
