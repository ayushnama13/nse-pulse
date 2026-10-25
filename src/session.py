"""NSESession: cookie warmup + Chrome TLS fingerprint + rate-limited GET with retry/backoff.

NSE sits behind Akamai bot manager. Two checks matter:

  1. **TLS / HTTP-2 fingerprint (JA3)**. Python's stock OpenSSL handshake does not
     look like Chrome. `requests` always gets 403, no matter what HTTP headers we
     send. We use **curl_cffi**, which drives libcurl-impersonate to reproduce
     Chrome's TLS ClientHello + HTTP/2 SETTINGS frame byte-for-byte.

  2. **Header bundle**. The homepage (a navigation request) and the JSON APIs
     (XHR requests) require DIFFERENT header sets:
       Navigation:  Accept: text/html..., Sec-Fetch-Mode: navigate,
                    Sec-Fetch-Dest: document, Upgrade-Insecure-Requests: 1,
                    NO X-Requested-With.
       XHR:         Accept: */*, Sec-Fetch-Mode: cors, Sec-Fetch-Dest: empty,
                    Sec-Fetch-Site: same-origin, X-Requested-With: XMLHttpRequest,
                    Referer.

     Sending XHR-style headers to the homepage is a known 403 trigger.

We hold the common Chrome fingerprint at the session level and overlay
purpose-specific keys per request.
"""
from __future__ import annotations

import time
from typing import Any

from curl_cffi import requests as cffi_requests
from curl_cffi.requests.errors import RequestsError
from loguru import logger

from .utils.config import get_config
from .utils.rate_limiter import RateLimiter


class NSEEndpointError(Exception):
    """Endpoint returned an unexpected status that is not retried (e.g. 404)."""


class NSEAuthError(Exception):
    """Endpoint returned 401/403 even after a session refresh."""


# Chrome version we ask curl_cffi to impersonate. Bump as Chrome ages.
_IMPERSONATE = "chrome"


class NSESession:
    def __init__(self) -> None:
        cfg = get_config()
        s = cfg.get("session", {})
        rl = cfg.get("rate_limit", {})
        rt = cfg.get("retry", {})

        self._homepage = s.get("homepage_url", "https://www.nseindia.com/")
        self._timeout = s.get("request_timeout_seconds", 15)

        ua = s.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        sec_ch_ua = s.get(
            "sec_ch_ua",
            '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        )
        platform = s.get("sec_ch_ua_platform", '"Linux"')

        # Always-sent fingerprint headers.
        self._common_headers: dict[str, str] = {
            "User-Agent": ua,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": s.get("accept_language", "en-US,en;q=0.9"),
            "Connection": "keep-alive",
            "sec-ch-ua": sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": platform,
        }

        # Overlaid for the homepage (HTML navigation).
        self._nav_extras: dict[str, str] = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8,"
                      "application/signed-exchange;v=b3;q=0.7",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

        # Overlaid for every JSON API call.
        self._xhr_extras: dict[str, str] = {
            "Accept": "*/*",
            "Referer": s.get("referer", "https://www.nseindia.com/"),
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
        }

        self._max_retries = int(rt.get("max_retries", 3))
        self._delays = list(rt.get("retry_delays_seconds", [60, 120, 300]))
        self._retry_status = set(rt.get("retry_on_status", [429, 500, 502, 503, 504]))
        self._fatal_status = set(rt.get("do_not_retry_on_status", [400, 401, 403, 404]))
        self._refresh_status = set(rt.get("refresh_session_on_status", [401, 403]))

        self._limiter = RateLimiter(
            requests_per_minute=int(rl.get("requests_per_minute", 30)),
            jitter_min_seconds=float(rl.get("jitter_min_seconds", 1.0)),
            jitter_max_seconds=float(rl.get("jitter_max_seconds", 3.0)),
        )

        # `impersonate` reproduces Chrome's TLS ClientHello + HTTP/2 SETTINGS.
        # Without this NSE returns 403 even with perfect HTTP headers.
        self._session = cffi_requests.Session(impersonate=_IMPERSONATE)
        self._session.headers.update(self._common_headers)
        self.refresh()

    # ---- Public API ----

    def refresh(self) -> None:
        """Hit homepage with NAVIGATION headers to (re)acquire cookies."""
        logger.info("Refreshing NSE session cookies via {}", self._homepage)
        try:
            r = self._session.get(
                self._homepage, headers=self._nav_extras, timeout=self._timeout
            )
        except RequestsError as e:
            raise NSEAuthError(f"Failed to reach NSE homepage: {e}") from e
        if r.status_code != 200:
            raise NSEAuthError(
                f"Homepage returned HTTP {r.status_code} during cookie warmup. "
                "Likely Akamai bot detection — verify TLS impersonation profile and headers."
            )

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        expect_json: bool = True,
    ) -> Any:
        """Rate-limited GET with XHR headers. Returns parsed JSON by default, else raw bytes."""
        attempt = 0
        refreshed_once = False

        while True:
            self._limiter.acquire()
            try:
                r = self._session.get(
                    url, params=params, headers=self._xhr_extras, timeout=self._timeout
                )
            except RequestsError as e:
                if attempt >= self._max_retries:
                    raise NSEEndpointError(f"GET {url} failed after retries: {e}") from e
                self._sleep_for_retry(attempt)
                attempt += 1
                continue

            status = r.status_code

            if status == 200:
                self._limiter.on_success()
                if expect_json:
                    try:
                        return r.json()
                    except ValueError as e:
                        raise NSEEndpointError(
                            f"GET {url} returned non-JSON body: {r.text[:300]}"
                        ) from e
                return r.content

            if status in self._refresh_status and not refreshed_once:
                logger.warning("HTTP {} on {} — refreshing session and retrying once.", status, url)
                self._limiter.on_throttle()
                self.refresh()
                refreshed_once = True
                continue

            if status in self._fatal_status:
                raise NSEEndpointError(
                    f"GET {url} returned non-retriable HTTP {status}: {r.text[:300]}"
                )

            if status in self._retry_status and attempt < self._max_retries:
                logger.warning(
                    "HTTP {} on {} — retry {}/{} (current rpm={})",
                    status, url, attempt + 1, self._max_retries, self._limiter.current_rpm,
                )
                if status == 429:
                    self._limiter.on_throttle()
                self._sleep_for_retry(attempt)
                attempt += 1
                continue

            raise NSEEndpointError(
                f"GET {url} returned HTTP {status} (no retry): {r.text[:300]}"
            )

    def download(self, url: str, params: dict[str, Any] | None = None) -> bytes:
        """Rate-limited GET returning raw bytes (CSV/ZIP/DAT archives)."""
        return self.get(url, params, expect_json=False)

    def _sleep_for_retry(self, attempt: int) -> None:
        delay = self._delays[min(attempt, len(self._delays) - 1)]
        logger.info("Sleeping {}s before retry {}", delay, attempt + 1)
        time.sleep(delay)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "NSESession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
