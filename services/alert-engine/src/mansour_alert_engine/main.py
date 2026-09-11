"""Process entrypoint for `alert-engine`."""

from __future__ import annotations

from mansour_alert_engine.service import AlertEngine
from mansour_alert_engine.settings import get_settings
from mansour_common.lifecycle import run


def main() -> None:
    settings = get_settings()
    run(AlertEngine(settings), grace_seconds=settings.shutdown_grace_seconds)


if __name__ == "__main__":
    main()
