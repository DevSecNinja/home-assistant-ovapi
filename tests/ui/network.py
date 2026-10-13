"""Pure URL policy for browser requests to the isolated Home Assistant fixture."""

from yarl import URL


def is_test_origin(request_url: str, base_url: str) -> bool:
    try:
        request, base = URL(request_url), URL(base_url)
        return (
            all(
                url.scheme in ("http", "https")
                and url.raw_user is None
                and url.host is not None
                for url in (request, base)
            )
            and request.origin() == base.origin()
        )
    except ValueError:
        return False
