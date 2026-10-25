"""Pin down the contract that homepage uses navigation headers and APIs use XHR headers.

Akamai bot manager on www.nseindia.com 403s navigation requests that carry XHR-style
headers (Accept: application/json, X-Requested-With). Real Chrome sends two distinct
bundles depending on Sec-Fetch-Mode. We have to do the same.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from requests.structures import CaseInsensitiveDict

from src import session as sess


class _FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"<html></html>", json_data=None):
        self.status_code = status
        self.content = body
        self.text = body.decode("utf-8", "replace")
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


@pytest.fixture
def captured_session(monkeypatch):
    """Spy on requests.Session.get; never hit the network."""
    captured = {"calls": []}

    def fake_get(self, url, params=None, headers=None, timeout=None):
        # Resolve effective headers like the HTTP client would: session defaults
        # merged with per-request override. curl_cffi lowercases on iteration, so
        # use a case-insensitive dict for assertions.
        effective = CaseInsensitiveDict(dict(self.headers))
        if headers:
            effective.update(headers)
        captured["calls"].append({"url": url, "headers": effective})
        if "/api/" in url:
            return _FakeResponse(200, b'{"ok": true}', json_data={"ok": True})
        return _FakeResponse(200, b"<html></html>")

    monkeypatch.setattr("curl_cffi.requests.Session.get", fake_get)
    return captured


def test_homepage_warmup_uses_navigation_headers(captured_session):
    sess.NSESession()
    homepage_call = captured_session["calls"][0]
    assert homepage_call["url"].startswith("https://www.nseindia.com")

    h = homepage_call["headers"]
    assert "text/html" in h.get("Accept", ""), \
        f"Homepage must request text/html (navigation), got {h.get('Accept')!r}"
    assert h.get("Sec-Fetch-Mode") == "navigate"
    assert h.get("Sec-Fetch-Dest") == "document"
    assert h.get("Upgrade-Insecure-Requests") == "1"
    # Critically: NO XHR-only headers on the homepage.
    assert "X-Requested-With" not in h, \
        "Homepage must NOT carry X-Requested-With (Akamai flags it)"


def test_api_call_uses_xhr_headers(captured_session):
    s = sess.NSESession()
    s.get("https://www.nseindia.com/api/marketStatus")
    api_call = captured_session["calls"][-1]

    h = api_call["headers"]
    assert h.get("Sec-Fetch-Mode") == "cors"
    assert h.get("Sec-Fetch-Dest") == "empty"
    assert h.get("Sec-Fetch-Site") == "same-origin"
    assert h.get("X-Requested-With") == "XMLHttpRequest"
    assert h.get("Referer", "").startswith("https://www.nseindia.com")


def test_common_browser_fingerprint_present_everywhere(captured_session):
    s = sess.NSESession()
    s.get("https://www.nseindia.com/api/marketStatus")
    for call in captured_session["calls"]:
        h = call["headers"]
        assert "Chrome" in h.get("User-Agent", ""), "UA must impersonate Chrome"
        assert h.get("Accept-Encoding", "") and "gzip" in h["Accept-Encoding"]
        assert h.get("sec-ch-ua")
        assert h.get("sec-ch-ua-mobile") == "?0"
        assert h.get("sec-ch-ua-platform")
