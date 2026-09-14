"""Public HTTP(S) only, DNS-pinned requests, bounded HTML, robots and rate limits."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
import ipaddress
import re
import socket
from threading import BoundedSemaphore, Lock
import time
import zlib
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup


class FetchError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class Page:
    url: str
    title: str
    text: str
    links: list[str]
    fetched_at: str


def public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
        return (ip.is_global and not ip.is_multicast and not ip.is_reserved
                and not ip.is_loopback and not ip.is_link_local
                and not getattr(ip, "ipv4_mapped", None)
                and not getattr(ip, "sixtofour", None) and not getattr(ip, "teredo", None))
    except ValueError:
        return False


def validate_url(url: str) -> tuple[str, str, int]:
    try:
        if len(url) > 4096 or re.search(r"[\s\x00-\x1f\\]", url):
            raise ValueError()
        parsed = urlsplit(url)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
        if (parsed.scheme not in {"http", "https"} or not host or parsed.username is not None
                or parsed.password is not None or "%" in host):
            raise ValueError()
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in host.split(".")):
                raise ValueError()
        else:
            if not public_ip(host):
                raise FetchError("BLOCKED_ADDRESS")
        authority = f"[{host}]" if ":" in host else host
        if parsed.port:
            authority += f":{port}"
        normalized = urlunsplit((parsed.scheme, authority, parsed.path or "/", parsed.query, ""))
        return normalized, host, port
    except (ValueError, UnicodeError) as exc:
        raise FetchError("INVALID_URL") from exc


_dns_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="enrich-dns")
_dns_slots = BoundedSemaphore(4)


def resolve_public(host: str, port: int, timeout: float) -> str:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not _dns_slots.acquire(blocking=False):
            raise FetchError("DNS_BUSY")
        future = _dns_pool.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
        future.add_done_callback(lambda _: _dns_slots.release())
        try:
            answers = {row[4][0] for row in future.result(timeout=timeout)}
        except (OSError, FutureTimeout) as exc:
            raise FetchError("DNS_FAILED") from exc
    else:
        answers = {host}
    # Reject the complete DNS result when even one address is non-public.
    if not answers or not all(public_ip(address) for address in answers):
        raise FetchError("BLOCKED_ADDRESS")
    return sorted(answers)[0]


class RateLimiter:
    def __init__(self):
        self.lock = Lock()
        self.next_request = {}

    def wait(self, host: str, delay: float = 1.0, budget: float = 8.0):
        with self.lock:
            now = time.monotonic()
            target = max(now, self.next_request.get(host, now))
            if target - now > budget or delay > budget:
                raise FetchError("RATE_LIMIT_WAIT")
            self.next_request[host] = target + max(1.0, delay)
            # Remove expired domains to bound long-lived bookkeeping.
            self.next_request = {key: value for key, value in self.next_request.items() if value >= now}
        if target > now:
            time.sleep(target - now)


LIMITER = RateLimiter()


class RobotsPolicy(RobotFileParser):
    """Keep stdlib rules and enforce all applicable Disallow rules conservatively.

    Python 3.11 RobotFileParser treats '*' and '$' as literal path characters.
    A deny may overrule an Allow exception here: fail closed, not open.
    """
    def can_fetch(self, useragent, url):
        if not super().can_fetch(useragent, url):
            return False
        parts = urlsplit(url)
        path = unquote(parts.path + ("?" + parts.query if parts.query else ""))
        entries = self.entries + ([self.default_entry] if self.default_entry else [])
        for entry in entries:
            if not entry.applies_to(useragent):
                continue
            for rule in entry.rulelines:
                pattern = unquote(rule.path)
                if not rule.allowance and pattern:
                    anchored = pattern.endswith("$")
                    pattern = pattern[:-1] if anchored else pattern
                    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + ("$" if anchored else "")
                    if re.search(regex, path):
                        return False
        return True


class SafeFetcher:
    def __init__(self, config, *, transport=None, resolver=resolve_public, limiter=LIMITER):
        self.timeout = min(max(config.enrich_timeout_s, 1), 8)
        self.max_bytes = min(max(config.enrich_max_bytes, 1), 2 * 1024 * 1024)
        self.user_agent = config.enrich_user_agent
        self.transport = transport  # Test-only injection; production uses verified TLS.
        self.resolver = resolver
        self.limiter = limiter
        self.robots = {}

    def _request(self, url: str, *, robots=False):
        for redirect in range(4):
            url, host, port = validate_url(url)
            delay = 1.0
            if not robots:
                parser = self._robots(url)
                if not parser.can_fetch(self.user_agent, url):
                    raise FetchError("ROBOTS_DISALLOWED")
                delay = parser.crawl_delay(self.user_agent) or 1.0
                rate = parser.request_rate(self.user_agent)
                if rate and rate.requests:
                    delay = max(delay, rate.seconds / rate.requests)
            self.limiter.wait(host, delay, self.timeout)
            address = self.resolver(host, port, self.timeout)
            if not public_ip(address):
                raise FetchError("BLOCKED_ADDRESS")
            original = httpx.URL(url)
            pinned = original.copy_with(host=address)
            # A fresh client prevents TLS connection reuse across unrelated names
            # sharing a CDN IP. HTTP Host and TLS SNI retain the original hostname.
            try:
                with httpx.Client(transport=self.transport, trust_env=False, follow_redirects=False,
                                  timeout=self.timeout) as client:
                    with client.stream("GET", pinned, headers={
                        "Host": original.netloc.decode("ascii"), "User-Agent": self.user_agent,
                        "Accept-Encoding": "identity", "Accept": "text/plain" if robots else "text/html",
                    }, extensions={"sni_hostname": host}) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            if redirect == 3 or "location" not in response.headers:
                                raise FetchError("REDIRECT_LIMIT")
                            url = urljoin(url, response.headers["location"])
                            continue
                        if robots and response.status_code in {404, 410}:
                            return url, b"", "text/plain"
                        if response.status_code != 200:
                            raise FetchError("HTTP_ERROR")
                        mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        if mime not in ({"text/plain"} if robots else {"text/html"}):
                            raise FetchError("UNSUPPORTED_CONTENT")
                        encoding = response.headers.get("content-encoding", "identity").lower()
                        if encoding not in {"identity", "gzip", "deflate"}:
                            raise FetchError("ENCODED_CONTENT")
                        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS) if encoding != "identity" else None
                        limit = min(self.max_bytes, 256 * 1024) if robots else self.max_bytes
                        length = response.headers.get("content-length", "")
                        if length.isdigit() and int(length) > limit:
                            raise FetchError("PAGE_TOO_LARGE")
                        content = bytearray()
                        wire_bytes = 0
                        deadline = time.monotonic() + self.timeout
                        for chunk in response.iter_raw(chunk_size=16384):
                            if time.monotonic() > deadline:
                                raise FetchError("FETCH_TIMEOUT")
                            wire_bytes += len(chunk)
                            if wire_bytes > limit:
                                raise FetchError("PAGE_TOO_LARGE")
                            try:
                                content.extend(decoder.decompress(chunk, limit - len(content) + 1) if decoder else chunk)
                            except zlib.error as exc:
                                raise FetchError("ENCODED_CONTENT") from exc
                            if len(content) > limit:
                                raise FetchError("PAGE_TOO_LARGE")
                            if decoder and decoder.unconsumed_tail:
                                raise FetchError("PAGE_TOO_LARGE")
                        if decoder and (not decoder.eof or decoder.unused_data):
                            raise FetchError("ENCODED_CONTENT")
                        return url, bytes(content), response.headers.get("content-type", "")
            except httpx.HTTPError as exc:
                raise FetchError("FETCH_FAILED") from exc
        raise FetchError("REDIRECT_LIMIT")

    def _robots(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        if origin not in self.robots:
            _, data, _ = self._request(origin + "/robots.txt", robots=True)
            parser = RobotsPolicy()
            parser.parse(data.decode("utf-8", errors="replace").splitlines())
            self.robots[origin] = parser
        return self.robots[origin]

    def fetch(self, url: str) -> Page:
        from app.models import utcnow
        final_url, data, content_type = self._request(url)
        charset = re.search(r"charset=([^;\s]+)", content_type, re.I)
        soup = BeautifulSoup(data, "html.parser", from_encoding=charset.group(1).strip('"') if charset else None)
        title = soup.title.get_text(" ", strip=True)[:500] if soup.title else ""
        links = [urljoin(final_url, anchor.get("href", "")) for anchor in soup.find_all("a", href=True)]
        for node in soup(["script", "style", "noscript", "template"]):
            node.decompose()
        text = soup.get_text("\n", strip=True)
        return Page(final_url, title, text, links, utcnow())
