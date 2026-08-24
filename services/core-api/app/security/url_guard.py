"""Blueprint §25 SSRF/URL validation — block private/localhost/metadata.

Any tool that fetches a URL must validate before making the request.
This is the single enforcement point; tools call is_url_allowed() first.
"""

import ipaddress
import re
from urllib.parse import urlparse

PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local + metadata 169.254.169.254
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
]

BLOCKED_HOSTS_RE = re.compile(
    r"(localhost|127\.0\.0\.1|0\.0\.0\.0|metadata\.google|instance-data|169\.254\.169\.254|\.internal$)",
    re.I,
)

ALLOWED_SCHEMES = {"http", "https"}

def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    for net in PRIVATE_RANGES:
        if ip in net:
            return True
    return False

def is_url_allowed(url: str) -> tuple[bool, str]:
    """Return (allowed, reason). Never raises."""
    if not url or not isinstance(url, str):
        return False, "empty url"
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "malformed url"
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"scheme '{parsed.scheme}' not allowed (only http/https)"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing host"
    if BLOCKED_HOSTS_RE.search(host) or BLOCKED_HOSTS_RE.search(url):
        return False, f"host '{host}' is blocked (localhost/metadata/internal)"
    # literal IP check
    if _is_private_ip(host):
        return False, f"host '{host}' is a private/link-local IP"
    # try DNS resolve for hostname that *looks* like private after resolve — best-effort
    # We do a lightweight check: if hostname resolves to private IP, block.
    # This is optional and may be skipped if DNS is unavailable.
    # For MVP we do a simple string check above; full DNS check is V2 (needs async dns).
    if host.endswith(".local") or host.endswith(".internal"):
        return False, f"host '{host}' internal TLD blocked"
    return True, "ok"

def assert_url_allowed(url: str) -> None:
    allowed, reason = is_url_allowed(url)
    if not allowed:
        from app.tools.base import ToolError
        raise ToolError(f"URL blocked by SSRF guard: {reason}")
