"""Webhook - moc 17/09.

Day la tinh nang DUY NHAT gui du lieu RA NGOAI toi mot dia chi do nguoi dung
nhap, nen phan lon bo test nay la cac duong tan cong chu khong phai duong
chay dung.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.db import get_db
from app.main import app
from app.models import Base
from app.webhook import (
    SIGNATURE_HEADER,
    WebhookTarget,
    deliver,
    dispatch_scan_completed,
    sign,
)


@pytest.fixture()
def system(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wh.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = Settings(_env_file=None, webhook_enabled=True,
                      webhook_max_attempts=2, webhook_timeout_s=1)

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: config
    try:
        yield TestClient(app), factory, config
    finally:
        app.dependency_overrides.clear()


# --- SSRF: dia chi noi bo phai bi chan ------------------------------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/hook",
    "http://localhost/hook",
    "http://192.168.1.10/hook",
    "http://10.0.0.5/hook",
    "http://169.254.169.254/latest/meta-data",     # metadata cua may ao
    "http://[::1]/hook",
    "file:///etc/passwd",
    "ftp://example.com/hook",
    "http://user:pass@example.com/hook",           # co thong tin dang nhap
    "http://example.com:22/hook",                  # cong khong phai web
])
def test_dia_chi_nguy_hiem_bi_tu_choi(system, url):
    client, factory, _ = system
    response = client.post("/api/webhooks", json={"url": url})

    assert response.status_code == 400, url
    assert response.json()["error"]["code"] == "WEBHOOK_URL_REJECTED"
    with factory() as db:
        assert db.query(WebhookTarget).count() == 0


def test_kiem_tra_lai_dia_chi_o_TUNG_LAN_GUI(monkeypatch):
    """DNS rebinding: ten mien tro toi dia chi cong khai luc dang ky roi doi
    sang dia chi noi bo luc gui. Kiem mot lan luc dang ky la KHONG DU."""
    import app.webhook as webhook

    target = WebhookTarget(id="t", url="https://example.com/hook", secret="s")
    config = Settings(_env_file=None, webhook_max_attempts=1)

    from app.services.enrich.fetcher import FetchError
    monkeypatch.setattr(webhook, "resolve_public",
                        lambda *a: (_ for _ in ()).throw(FetchError("BLOCKED_ADDRESS")))

    sent = []
    monkeypatch.setattr(httpx, "Client", lambda **kw: sent.append(kw))

    ok, status = deliver(target, "scan.completed", {}, config)
    assert ok is False
    assert "bi chan" in status
    assert sent == []          # khong he mo ket noi nao


# --- Chu ky de ben nhan xac minh ------------------------------------------

def test_chu_ky_HMAC_dung_chuan():
    payload = b'{"event":"scan.completed"}'
    expected = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    assert sign("secret", payload) == f"sha256={expected}"


def test_chu_ky_doi_khi_noi_dung_doi():
    assert sign("s", b"a") != sign("s", b"b")


def test_chu_ky_doi_khi_bi_mat_doi():
    assert sign("s1", b"a") != sign("s2", b"a")


# --- Bi mat ky khong duoc lo -----------------------------------------------

def test_bi_mat_chi_hien_dung_mot_lan(system):
    client, _, _ = system
    created = client.post("/api/webhooks", json={"url": "https://example.com/hook"})
    assert created.status_code == 201
    assert created.json()["secret"]

    listed = client.get("/api/webhooks").json()["items"]
    assert listed and "secret" not in listed[0]


def test_bi_mat_moi_lan_dang_ky_deu_khac_nhau(system):
    client, _, _ = system
    first = client.post("/api/webhooks", json={"url": "https://a.example.com/h"})
    second = client.post("/api/webhooks", json={"url": "https://b.example.com/h"})
    assert first.json()["secret"] != second.json()["secret"]


# --- Mac dinh tat ----------------------------------------------------------

def test_mac_dinh_tat(tmp_path):
    """App chua co xac thuc, nen bat ky ai goi duoc API deu co the dang ky mot
    URL va nhan toan bo du lieu ban quet. Mac dinh phai la TAT."""
    assert Settings(_env_file=None).webhook_enabled is False


def test_dang_ky_bi_tu_choi_khi_dang_tat(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'off.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = Settings(_env_file=None, webhook_enabled=False)

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: config
    try:
        response = TestClient(app).post("/api/webhooks",
                                        json={"url": "https://example.com/h"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "WEBHOOK_DISABLED"
    finally:
        app.dependency_overrides.clear()


def test_khong_gui_gi_khi_dang_tat(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'off2.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    import app.webhook as webhook
    called = []
    monkeypatch.setattr(webhook, "deliver", lambda *a: called.append(a) or (True, "ok"))

    dispatch_scan_completed("s1", {}, Settings(_env_file=None, webhook_enabled=False),
                            factory)
    assert called == []


# --- Thu lai co gioi han ---------------------------------------------------

def _fake_client(responses, sent):
    class FakeResponse:
        def __init__(self, code):
            self.status_code = code
            self.is_success = 200 <= code < 300

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, content, headers, **kwargs):
            sent.append((url, content, headers))
            return FakeResponse(responses.pop(0))

    return FakeClient


def test_loi_5xx_duoc_thu_lai_trong_gioi_han(monkeypatch):
    import app.webhook as webhook
    monkeypatch.setattr(webhook, "validate_url",
                        lambda url: (url, "example.com", 443))
    monkeypatch.setattr(webhook, "resolve_public", lambda *a: "93.184.216.34")
    monkeypatch.setattr(webhook.time, "sleep", lambda s: None)

    sent = []
    monkeypatch.setattr(httpx, "Client", _fake_client([500, 500, 200], sent))

    target = WebhookTarget(id="t", url="https://example.com/h", secret="s")
    ok, status = deliver(target, "scan.completed", {},
                         Settings(_env_file=None, webhook_max_attempts=3))
    assert ok is True and len(sent) == 3


def test_loi_4xx_KHONG_duoc_thu_lai(monkeypatch):
    """Ben nhan da tu choi noi dung. Gui lai y het chi lam phien ho va khong
    bao gio thanh cong."""
    import app.webhook as webhook
    monkeypatch.setattr(webhook, "validate_url", lambda url: (url, "example.com", 443))
    monkeypatch.setattr(webhook, "resolve_public", lambda *a: "93.184.216.34")
    monkeypatch.setattr(webhook.time, "sleep", lambda s: None)

    sent = []
    monkeypatch.setattr(httpx, "Client", _fake_client([400, 400, 400], sent))

    ok, status = deliver(WebhookTarget(id="t", url="https://e.com/h", secret="s"),
                         "scan.completed", {},
                         Settings(_env_file=None, webhook_max_attempts=3))
    assert ok is False and len(sent) == 1
    assert "khong thu lai" in status


def test_qua_tai_429_VAN_duoc_thu_lai(monkeypatch):
    """429 la loi tam thoi du nam trong day 4xx."""
    import app.webhook as webhook
    monkeypatch.setattr(webhook, "validate_url", lambda url: (url, "e.com", 443))
    monkeypatch.setattr(webhook, "resolve_public", lambda *a: "93.184.216.34")
    monkeypatch.setattr(webhook.time, "sleep", lambda s: None)

    sent = []
    monkeypatch.setattr(httpx, "Client", _fake_client([429, 200], sent))

    ok, _ = deliver(WebhookTarget(id="t", url="https://e.com/h", secret="s"),
                    "scan.completed", {},
                    Settings(_env_file=None, webhook_max_attempts=3))
    assert ok is True and len(sent) == 2


# --- Noi dung gui di -------------------------------------------------------

def test_noi_dung_co_chu_ky_va_giu_nguyen_chu_nhat(monkeypatch):
    import app.webhook as webhook
    monkeypatch.setattr(webhook, "validate_url", lambda url: (url, "e.com", 443))
    monkeypatch.setattr(webhook, "resolve_public", lambda *a: "93.184.216.34")

    sent = []
    monkeypatch.setattr(httpx, "Client", _fake_client([200], sent))

    target = WebhookTarget(id="t", url="https://e.com/h", secret="bi-mat")
    deliver(target, "scan.completed", {"name": "山田 太郎"},
            Settings(_env_file=None, webhook_max_attempts=1))

    url, content, headers = sent[0]
    body = json.loads(content)
    assert body["event"] == "scan.completed"
    assert body["data"]["name"] == "山田 太郎"
    assert headers[SIGNATURE_HEADER] == sign("bi-mat", content)


def test_loi_webhook_khong_lam_hong_ban_quet(monkeypatch, tmp_path):
    """Ban quet DA xong truoc khi gui webhook. Loi gui khong duoc lan nguoc."""
    engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(WebhookTarget(url="https://e.com/h", secret="s"))
        db.commit()

    import app.webhook as webhook
    monkeypatch.setattr(webhook, "deliver",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("no")))

    from app.pipeline import notify_completed
    # Khong duoc nem ngoai le ra ngoai.
    notify_completed("s1", {}, Settings(_env_file=None, webhook_enabled=True), factory)


# --- Quan ly dich -----------------------------------------------------------

def test_khong_dang_ky_trung_URL(system):
    client, _, _ = system
    client.post("/api/webhooks", json={"url": "https://example.com/hook"})
    again = client.post("/api/webhooks", json={"url": "https://example.com/hook"})
    assert again.status_code == 409


def test_tat_va_xoa_dich(system):
    client, factory, _ = system
    target_id = client.post("/api/webhooks",
                            json={"url": "https://example.com/hook"}).json()["id"]

    assert client.patch(f"/api/webhooks/{target_id}",
                        params={"enabled": False}).json()["enabled"] is False
    assert client.delete(f"/api/webhooks/{target_id}").status_code == 204
    with factory() as db:
        assert db.query(WebhookTarget).count() == 0


def test_dich_da_tat_khong_nhan_thong_bao(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(WebhookTarget(url="https://on.example.com/h", secret="s", enabled=True))
        db.add(WebhookTarget(url="https://off.example.com/h", secret="s", enabled=False))
        db.commit()

    import app.webhook as webhook
    called = []
    monkeypatch.setattr(webhook, "deliver",
                        lambda t, *a: (called.append(t.url), (True, "ok"))[1])

    dispatch_scan_completed("s1", {}, Settings(_env_file=None, webhook_enabled=True),
                            factory)
    assert called == ["https://on.example.com/h"]
