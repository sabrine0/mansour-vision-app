"""Process entrypoint for `analytics-consumer`."""

from __future__ import annotations

from mansour_analytics.service import AnalyticsConsumer
from mansour_analytics.settings import get_settings
from mansour_common.lifecycle import run


def main() -> None:
    settings = get_settings()
    run(AnalyticsConsumer(settings), grace_seconds=settings.shutdown_grace_seconds)


if __name__ == "__main__":
    main()
