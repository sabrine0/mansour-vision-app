"""Process entrypoint for `vision-worker`."""

from __future__ import annotations

from mansour_common.lifecycle import run
from mansour_vision_worker.service import VisionWorker
from mansour_vision_worker.settings import get_settings


def main() -> None:
    settings = get_settings()
    run(VisionWorker(settings), grace_seconds=settings.shutdown_grace_seconds)


if __name__ == "__main__":
    main()
