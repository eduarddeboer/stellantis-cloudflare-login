"""Explicitly trusted, self-hosted Cloudflare Workers OAuth login client.

Never logs credentials, OAuth codes, request/response bodies or redirects.
Only self-hosted *.workers.dev endpoints (one worker + one account label)
are supported in this experimental beta; custom domains are intentionally off.
"""
from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit


class WorkerOAuthError(Exception):
    """Only fixed non-sensitive errors are emitted from this module."""


_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalized_worker_url(value: str) -> str | None:
    """Return canonical HTTPS workers.dev root or None; never echo an input URL.

    A workers.dev name must be NAME.ACCOUNT.workers.dev. Explicit host consent
    is handled in the HA config flow. DNS ownership is not provable here.
    """
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    try:
        u = urlsplit(value)
        if (u.scheme != "https" or u.username is not None or
                u.password is not None or u.query or u.fragment or
                u.path not in ("", "/") or u.port not in (None, 443)):
            return None
        hostname = u.hostname
    except (ValueError, TypeError):
        return None
    if not hostname or not hostname.isascii():
        return None
    parts = hostname.lower().split(".")
    if len(parts) != 4 or parts[-2:] != ["workers", "dev"]:
        return None
    if not all(_LABEL.fullmatch(p) for p in parts[:2]):
        return None
    return "https://" + ".".join(parts) + "/"


def is_workers_dev_url(value: str) -> bool:
    """Also detect malformed Workers URLs; prevent silent legacy fallback."""
    if not isinstance(value, str):
        return False
    try:
        host = urlsplit(value).hostname
    except ValueError:
        return False
    return bool(host and (host == "workers.dev" or host.endswith(".workers.dev")))


async def get_code_from_worker(
    session, *, email: str, password: str, authorize_url: str,
    api_key: str, worker_url: str, confirmed: bool,
) -> str:
    """One credential-bearing POST to the explicitly confirmed Worker.

    Do not use the generic Stellantis HTTP client: its legacy error/debug path
    can log sensitive request context and may treat Worker 401 as token expiry.
    """
    endpoint = normalized_worker_url(worker_url)
    if endpoint is None:
        raise WorkerOAuthError("Only an HTTPS NAME.ACCOUNT.workers.dev root URL is supported")
    if not confirmed:
        raise WorkerOAuthError("Confirm that this Worker belongs to your Cloudflare account")
    if not all(isinstance(x, str) and x for x in (email, password, authorize_url, api_key)):
        raise WorkerOAuthError("Missing OAuth Worker parameters")
    if len(api_key) < 24 or len(api_key) > 2048 or any(c.isspace() for c in api_key):
        raise WorkerOAuthError("Invalid OAuth Worker API key")
    try:
        async with asyncio.timeout(240):
            async with session.post(
                endpoint,
                json={"url": authorize_url, "email": email, "password": password},
                headers={"Authorization": "Bearer " + api_key,
                         "Accept": "application/json"},
                allow_redirects=False,
            ) as response:
                if response.status == 401:
                    raise WorkerOAuthError("Worker API key rejected (HTTP 401)")
                if response.status != 200:
                    # Do not echo arbitrary response status, body, URL or headers.
                    raise WorkerOAuthError("Worker authentication request failed")
                data = await response.json()
                if not isinstance(data, dict):
                    raise WorkerOAuthError("Invalid OAuth Worker response")
                code = data.get("code")
                if not isinstance(code, str) or not (1 <= len(code) <= 4096):
                    raise WorkerOAuthError("Invalid OAuth Worker response")
                return code
    except WorkerOAuthError:
        raise
    except Exception:
        raise WorkerOAuthError("OAuth Worker communication failed") from None
