"""Configuration for `vision-worker`."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from mansour_common.config import RedisSettings, ServiceSettings, load


class WorkerSettings(ServiceSettings):
    """A worker owns a set of cameras and publishes aggregated events."""

    model_config = SettingsConfigDict(
        env_prefix="WORKER_",
        env_file=".env",
        extra="forbid",
        frozen=True,
    )

    service_name: str = "vision-worker"

    #: Stable identity of this worker instance. Appears as `producer` on every
    #: event it publishes, and is how the scheduler addresses it.
    worker_id: str = Field(default="worker-1", min_length=1, max_length=64)

    #: Frames analysed per second per camera. Not the camera's native rate.
    #: Crowd counting does not need 30 fps; ByteTrack bridges the skipped frames,
    #: and this is the single largest lever on per-GPU camera capacity (ADR 0005).
    analytic_fps: float = Field(default=10.0, gt=0, le=60)

    #: ONNX Runtime execution provider. Selected by deployment, not by code.
    execution_provider: str = Field(default="CPUExecutionProvider")

    #: Seconds without a decoded frame before a camera is declared offline.
    #: Keyed on frame staleness, never on whether the capture handle looks open:
    #: a dead network stream leaves `read()` blocking while the handle appears
    #: healthy.
    camera_offline_after_seconds: float = Field(default=5.0, gt=0)

    #: Cameras on the charge track are never load-shed (Detection SRS §15.4).
    #: Listed by id so the scheduler and the shed policy agree on which they are.
    priority_camera_ids: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return load(WorkerSettings)


@lru_cache(maxsize=1)
def get_redis_settings() -> RedisSettings:
    return load(RedisSettings)


__all__ = ["WorkerSettings", "get_redis_settings", "get_settings"]
