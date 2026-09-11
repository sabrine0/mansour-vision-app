"""Process entrypoint for `core-api`."""

from __future__ import annotations

import uvicorn

from mansour_api.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "mansour_api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        # structlog owns the log pipeline; uvicorn's own config would emit a
        # second, differently-shaped line for every request.
        log_config=None,
        access_log=False,
        server_header=False,
        date_header=False,
    )


if __name__ == "__main__":
    main()
