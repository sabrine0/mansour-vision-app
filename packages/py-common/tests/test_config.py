"""Configuration fails fast and never leaks secrets."""

from __future__ import annotations

from pathlib import Path

import pytest

from mansour_common.config import (
    PostgresSettings,
    RedisSettings,
    ServiceSettings,
    load,
    read_secret,
)
from mansour_common.errors import ConfigurationError


class TestServiceSettings:
    def test_loads_with_required_fields(self) -> None:
        settings = load(ServiceSettings, service_name="core-api")
        assert settings.service_name == "core-api"
        assert settings.environment == "development"
        assert settings.log_level == "INFO"

    def test_log_level_is_normalised_to_upper_case(self) -> None:
        assert load(ServiceSettings, service_name="x", log_level="debug").log_level == "DEBUG"

    def test_invalid_log_level_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            load(ServiceSettings, service_name="x", log_level="LOUD")
        assert exc.value.context["fields"] == ["log_level"]
        assert exc.value.retryable is False

    def test_unknown_field_is_rejected(self) -> None:
        """A typo'd env var must not be silently ignored."""
        with pytest.raises(ConfigurationError):
            load(ServiceSettings, service_name="x", loglevel="INFO")

    def test_out_of_range_port_raises(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            load(ServiceSettings, service_name="x", health_port=70000)
        assert exc.value.context["fields"] == ["health_port"]

    def test_settings_are_frozen(self) -> None:
        settings = load(ServiceSettings, service_name="x")
        with pytest.raises(ValueError, match="frozen"):
            settings.service_name = "y"  # type: ignore[misc]

    def test_is_production(self) -> None:
        assert load(ServiceSettings, service_name="x", environment="production").is_production
        assert not load(ServiceSettings, service_name="x", environment="test").is_production


class TestPostgresSettings:
    def test_dsn_includes_credentials(self) -> None:
        settings = PostgresSettings(host="db", port=5432, db="mansour", user="u", password="p")
        assert settings.dsn() == "postgresql+asyncpg://u:p@db:5432/mansour"

    def test_dsn_driver_is_overridable_for_alembic(self) -> None:
        settings = PostgresSettings(user="u", password="p", host="db", db="mansour")
        assert settings.dsn(driver="postgresql+psycopg").startswith("postgresql+psycopg://")

    def test_password_is_not_exposed_by_repr(self) -> None:
        settings = PostgresSettings(user="u", password="topsecret")
        assert "topsecret" not in repr(settings)
        assert "topsecret" not in str(settings)


class TestRedisSettings:
    def test_url_without_password(self) -> None:
        assert RedisSettings(host="cache", port=6379, db=2).url() == "redis://cache:6379/2"

    def test_url_with_password(self) -> None:
        assert RedisSettings(host="cache", password="pw").url() == "redis://:pw@cache:6379/0"

    def test_password_is_not_exposed_by_repr(self) -> None:
        assert "pw" not in repr(RedisSettings(password="pw"))

    def test_db_index_is_bounded(self) -> None:
        with pytest.raises(ConfigurationError):
            load(RedisSettings, db=99)


class TestDockerSecretIntegration:
    """Compose mounts credentials as files and exports `*_FILE`. If settings only
    read the plain variable, the whole stack starts with an empty password and
    fails at the first connection — after the healthcheck has already passed."""

    def test_postgres_password_falls_back_to_the_secret_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret_file = tmp_path / "postgres_password"
        secret_file.write_text("s3cret-from-docker\n", encoding="utf-8")
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.setenv("POSTGRES_PASSWORD_FILE", str(secret_file))

        settings = PostgresSettings()

        assert settings.password.get_secret_value() == "s3cret-from-docker"
        assert "s3cret-from-docker" in settings.dsn()

    def test_plain_environment_variable_still_wins_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("POSTGRES_PASSWORD_FILE", raising=False)
        monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")

        assert PostgresSettings().password.get_secret_value() == "from-env"

    def test_redis_password_is_none_when_neither_form_is_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD_FILE", raising=False)

        settings = RedisSettings(host="cache")

        assert settings.password is None
        assert settings.url() == "redis://cache:6379/0"

    def test_redis_password_falls_back_to_the_secret_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret_file = tmp_path / "redis_password"
        secret_file.write_text("cache-pw\n", encoding="utf-8")
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.setenv("REDIS_PASSWORD_FILE", str(secret_file))

        assert RedisSettings(host="cache").url() == "redis://:cache-pw@cache:6379/0"


class TestReadSecret:
    def test_prefers_the_file_form(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Docker mounts secrets as files; a file is not visible in `docker inspect`."""
        secret_file = tmp_path / "pg_password"
        secret_file.write_text("from-file\n", encoding="utf-8")
        monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))
        monkeypatch.setenv("PG_PASSWORD", "from-env")

        assert read_secret("PG_PASSWORD") == "from-file"

    def test_falls_back_to_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PG_PASSWORD_FILE", raising=False)
        monkeypatch.setenv("PG_PASSWORD", "from-env")

        assert read_secret("PG_PASSWORD") == "from-env"

    def test_returns_default_when_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ABSENT_FILE", raising=False)
        monkeypatch.delenv("ABSENT", raising=False)

        assert read_secret("ABSENT", "fallback") == "fallback"

    def test_unreadable_secret_file_raises_configuration_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PG_PASSWORD_FILE", str(tmp_path / "does-not-exist"))

        with pytest.raises(ConfigurationError) as exc:
            read_secret("PG_PASSWORD")
        assert exc.value.context["variable"] == "PG_PASSWORD_FILE"
