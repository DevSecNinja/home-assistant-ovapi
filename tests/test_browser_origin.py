"""Exercise adversarial URL strings without making requests to those addresses."""

import pytest

from tests.ui.network import is_test_origin

BASE = "http://127.0.0.1:8123"


@pytest.mark.parametrize(
    "url",
    [
        BASE,
        BASE + "/",
        BASE + "/frontend_latest/module.js",
        BASE + "/api/states?entity_id=sensor.example",
        BASE + "/asset?next=https://example.invalid/#fragment",
        "HTTP://127.0.0.1:8123/frontend_latest/module.js",
    ],
)
def test_accept_exact_test_origin(url):
    assert is_test_origin(url, BASE)


@pytest.mark.parametrize(
    "url",
    [
        BASE + "@example.invalid/steal",
        "http://127.0.0.1.example.invalid:8123/asset",
        "http://127.0.0.1:81234/asset",
        "http://127.0.0.1:8124/asset",
        "https://127.0.0.1:8123/asset",
        "http://user:password@127.0.0.1:8123/asset",
        "ws://127.0.0.1:8123/api/websocket",
        "wss://127.0.0.1:8123/api/websocket",
        "ftp://127.0.0.1:8123/asset",
        "data:text/plain,hello",
        "file:///etc/hosts",
        "about:blank",
        "/relative",
        "//127.0.0.1:8123/asset",
        "not a URL",
        "",
        "http://",
        "http://127.0.0.1:invalid/asset",
        "http://127.0.0.1:99999/asset",
        "http://[invalid]/asset",
    ],
)
def test_reject_other_or_invalid_origins(url):
    assert not is_test_origin(url, BASE)


@pytest.mark.parametrize(
    "base", ["", "/relative", "file:///tmp", "http://", "http://[bad]"]
)
def test_invalid_base_fails_closed(base):
    assert not is_test_origin(BASE + "/asset", base)
