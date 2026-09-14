"""Restart real Uvicorn processes against an isolated SQLite DB; no cloud calls.

Usage from repo root: .venv/Scripts/python.exe backend/scripts/check_day7_restart.py
The OCR response is synthetic. This verifies persistence, not OCR accuracy.
"""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]


def serve(port):
    sys.path.insert(0, str(ROOT / "backend"))
    from types import SimpleNamespace
    import uvicorn
    from app import main, pipeline
    from app.services.ocr.base import OcrResult
    pipeline.build_ocr = lambda config: SimpleNamespace(recognize=lambda *args: OcrResult(
        raw_text="山田 太郎\n株式会社サンプル\ntaro@example.jp\n03-1234-5678",
        provider="mock:synthetic", provider_version="day7-restart", detected_languages=["ja"]))
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="error")


def check(output):
    import httpx
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix="ocr-day7-") as folder:
        folder = Path(folder)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{(folder / 'test.db').as_posix()}",
               "IMAGE_DIR": str(folder / "images"), "OCR_PROVIDER": "mock", "EXTRACTOR": "heuristic",
               "ENRICH_ENABLED": "false", "GEMINI_API_KEY": "", "GEMINI_MODEL": "",
               "GOOGLE_APPLICATION_CREDENTIALS": "", "PYTHONUTF8": "1"}
        process = None
        pids = []
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3, trust_env=False) as client:
            def start():
                nonlocal process
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve", str(port)],
                    cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                pids.append(process.pid)
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Test backend exited before becoming ready")
                    try:
                        if client.get("/api/health").status_code == 200:
                            return
                    except httpx.RequestError:
                        pass
                    time.sleep(0.2)
                raise RuntimeError("Test backend readiness timed out")

            def stop():
                nonlocal process
                if process is not None:
                    process.terminate()
                    process.wait(timeout=10)
                    process = None

            def json_request(method, path, **kwargs):
                response = client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()

            try:
                start()
                image = io.BytesIO()
                Image.new("RGB", (80, 40), "white").save(image, format="PNG")
                sid = json_request("POST", "/api/scans", files={"file": ("synthetic.png", image.getvalue(), "image/png")})["id"]
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    scan = json_request("GET", f"/api/scans/{sid}")
                    if scan["status"] not in {"pending", "processing"}:
                        break
                    time.sleep(0.1)
                assert scan["status"] == "ocr_done", scan
                fields = {field: [{k: x.get(k, "") for k in ("id", "value", "label", "extension")} for x in rows]
                          for field, rows in scan["draft"]["fields"].items()}
                fields["full_names"] = [{"value": "山田 太郎"}, {"value": "Taro Yamada"}]
                fields["company_names"] = [{"value": "株式会社サンプル"}]
                fields["phones"] = [{"value": "03-1234-5678", "label": "tel"}, {"value": "+81 90-1234-5678", "label": "mobile"}]
                scan = json_request("PATCH", f"/api/scans/{sid}/draft", json={"revision": scan["draft_revision"], "fields": fields})
                body = {"scan_id": sid, "revision": scan["draft_revision"]}
                headers = {"Idempotency-Key": "restart-proof"}
                cid = json_request("POST", "/api/contacts", json=body, headers=headers)["id"]
                before = json_request("GET", f"/api/contacts/{cid}")
                stop()
                start()
                after = json_request("GET", f"/api/contacts/{cid}")
                assert before == after
                assert json_request("GET", "/api/contacts", params={"q": "山田"})["total"] == 1
                assert json_request("POST", "/api/contacts", json=body, headers=headers)["id"] == cid
                assert json_request("GET", "/api/export?format=json")["contacts"][0] == after
                exported = client.get("/api/export?format=csv")
                exported.raise_for_status()
                assert exported.content.startswith(b"\xef\xbb\xbf")
                row = next(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
                assert json.loads(row["full_names"]) == ["山田 太郎", "Taro Yamada"]
                assert json.loads(row["phones"])[0] == "03-1234-5678"
                report = {"checked_at": datetime.now(timezone.utc).isoformat(), "result": "passed",
                          "backend_pids": pids, "separate_processes": pids[0] != pids[1],
                          "storage": "isolated temporary SQLite database", "ocr": "mock:synthetic",
                          "checks": ["HTTP upload and draft review", "transactional contact save",
                                     "terminate backend and start another process", "identical profile after restart",
                                     "Japanese search", "idempotency key survives restart", "JSON round-trip",
                                     "CSV BOM and Japanese/leading-zero preservation"],
                          "excel_visual_check": "not performed", "real_ocr_quality": "not evaluated"}
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report, ensure_ascii=False))
            finally:
                stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "Document/Kiem-tra-khoi-dong-lai-ngay-7.json")
    args = parser.parse_args()
    if args.serve:
        serve(args.serve)
    else:
        check(args.output)
