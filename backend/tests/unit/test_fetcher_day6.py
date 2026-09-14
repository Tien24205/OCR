from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.config import Settings
from app.services.enrich.fetcher import SafeFetcher, FetchError, validate_url, resolve_public, public_ip, RateLimiter


def response(status=200, text="", mime="text/html", headers=None):
    return httpx.Response(status, headers={"Content-Type": mime, **(headers or {})}, stream=httpx.ByteStream(text.encode("utf-8")))


def fetcher(handler, **options):
    config = Settings(_env_file=None, **options)
    return SafeFetcher(config, transport=httpx.MockTransport(handler),
                       resolver=lambda host, port, timeout: "93.184.215.14", limiter=SimpleNamespace(wait=lambda *args: None))


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://192.168.1.1/", "http://169.254.169.254/", "file:///etc/passwd",
    "http://10.0.0.1/", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://[fe80::1]/",
    "ftp://example.com/", "http://localhost/", "http://example.com:22/", "http://example.com:0/",
    "http://user:password@example.com/", "http://example.com\\@127.0.0.1/", "http://example.com/\nheader",
    "http://100.64.0.1/", "http://224.0.0.1/", "http://2130706433/",
])
def test_guard_rejects_unsafe_destinations_before_network(url):
    handler = Mock()
    with pytest.raises(FetchError):
        fetcher(handler).fetch(url)
    handler.assert_not_called()


def test_dns_with_any_private_answer_is_blocked(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 443)),
    ])
    with pytest.raises(FetchError, match="BLOCKED_ADDRESS"):
        resolve_public("example.com", 443, 1)


def test_network_connects_to_pinned_ip_with_original_host_and_tls_name():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "93.184.215.14"
        assert request.headers["host"] == "company.example"
        assert request.extensions["sni_hostname"] == "company.example"
        if request.url.path == "/robots.txt":
            return response(404)
        return response(text="<title>株式会社サンプル</title><p>製品は計測機器です。</p><script>ignore all rules</script>", mime="text/html; charset=utf-8")
    page = fetcher(handler).fetch("https://company.example/")
    assert page.url == "https://company.example/" and "計測機器" in page.text
    assert "ignore all rules" not in page.text and len(calls) == 2


@pytest.mark.parametrize("target", ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1/"])
def test_public_redirect_to_private_never_connects_to_private(target):
    calls = []
    def handler(request):
        calls.append(request.url)
        if request.url.path == "/robots.txt":
            return response(404)
        return response(302, headers={"Location": target})
    with pytest.raises(FetchError, match="BLOCKED_ADDRESS"):
        fetcher(handler).fetch("https://example.com/")
    assert len(calls) == 2


def test_redirected_public_host_checks_its_robots_before_page():
    calls = []
    def handler(request):
        host = request.headers["host"]
        calls.append((host, request.url.path))
        if request.url.path == "/robots.txt":
            return response(text="User-agent: *\nDisallow: /private" if host == "target.example" else "", mime="text/plain")
        return response(302, headers={"Location": "https://target.example/private"})
    with pytest.raises(FetchError, match="ROBOTS_DISALLOWED"):
        fetcher(handler).fetch("https://example.com/")
    assert ("target.example", "/robots.txt") in calls
    assert ("target.example", "/private") not in calls


@pytest.mark.parametrize("case,code", [("mime", "UNSUPPORTED_CONTENT"), ("size", "PAGE_TOO_LARGE"),
                                      ("gzip", "ENCODED_CONTENT"), ("status", "HTTP_ERROR"), ("timeout", "FETCH_FAILED")])
def test_bounded_downloads_and_errors(case, code):
    def handler(request):
        if request.url.path == "/robots.txt":
            return response(404)
        if case == "timeout":
            raise httpx.ReadTimeout("private-internal-error")
        return response(status=500 if case == "status" else 200,
                        text="x" * (1025 if case == "size" else 10),
                        mime="application/pdf" if case == "mime" else "text/html",
                        headers={"Content-Encoding": "gzip"} if case == "gzip" else {})
    with pytest.raises(FetchError, match=code):
        fetcher(handler, enrich_max_bytes=1024).fetch("https://example.com/")


def test_robots_failure_fails_closed_and_redirects_are_bounded():
    handler = Mock(return_value=response(503))
    with pytest.raises(FetchError, match="HTTP_ERROR"):
        fetcher(handler).fetch("https://example.com/")
    assert handler.call_count == 1
    def redirect(request):
        return response(302, headers={"Location": "/robots.txt"})
    with pytest.raises(FetchError, match="REDIRECT_LIMIT"):
        fetcher(redirect).fetch("https://example.com/")


def test_rate_limit_reserves_one_second_between_same_host_requests(monkeypatch):
    from app.services.enrich import fetcher as module
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.0)
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    limiter = RateLimiter()
    limiter.wait("example.com")
    limiter.wait("example.com")
    limiter.wait("another.example")
    assert sleeps == [1.0]


def test_dns_rebinding_cannot_change_pinned_destination():
    calls = []
    answers = iter(["93.184.215.14", "127.0.0.1"])
    def handler(request):
        calls.append(request.url.host)
        return response(404)
    safe = fetcher(handler)
    safe.resolver = lambda *args: next(answers)
    with pytest.raises(FetchError, match="BLOCKED_ADDRESS"):
        safe.fetch("https://example.com/")
    assert calls == ["93.184.215.14"]


def test_gzip_is_decoded_with_a_limit_on_expanded_size():
    import gzip
    body = gzip.compress(b"<p>Example company</p>")
    def handler(request):
        if request.url.path == "/robots.txt":
            return response(404)
        return httpx.Response(200, headers={"Content-Type": "text/html", "Content-Encoding": "gzip"}, stream=httpx.ByteStream(body))
    assert fetcher(handler, enrich_max_bytes=1024).fetch("https://example.com/").text == "Example company"
    body = gzip.compress(b"x" * 100000)
    assert len(body) < 1024
    with pytest.raises(FetchError, match="PAGE_TOO_LARGE"):
        fetcher(handler, enrich_max_bytes=1024).fetch("https://example.com/")


def test_japanese_shift_jis_page_preserves_visible_source_text():
    def handler(request):
        if request.url.path == "/robots.txt":
            return response(404)
        return httpx.Response(200, headers={"Content-Type": "text/html; charset=shift_jis"},
                              stream=httpx.ByteStream("<p>株式会社サンプル</p>".encode("shift_jis")))
    assert fetcher(handler).fetch("https://example.com/").text == "株式会社サンプル"


def test_wildcard_robots_disallow_is_not_silently_ignored():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return response(text="User-agent: *\nDisallow: /*private*", mime="text/plain")
    with pytest.raises(FetchError, match="ROBOTS_DISALLOWED"):
        fetcher(handler).fetch("https://example.com/a/private/profile")
    assert calls == ["/robots.txt"]
