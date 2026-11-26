#!/usr/bin/env python3
"""보홀 대시보드 실시간 스캔 API (내부서버용).

Python 3 표준 라이브러리만 사용한다. Nginx 뒤에서 127.0.0.1:8765 로 띄우는 것을 전제로 한다.

엔드포인트 (앞에 /bohol 이 붙은 형태도 함께 받는다)
  GET  /api/health  → {"ok": true}
  GET  /api/scan    ┐ 엔조이스카이를 다시 스캔해 scan-data.json 을 갱신하고,
  POST /api/scan    ┘ 갱신된 JSON 전체를 200 으로 돌려준다. 실패 시 502.

환경변수
  PORT              듣는 포트 (기본 8765)
  HOST              바인드 주소 (기본 127.0.0.1 — 외부에 직접 노출하지 않는다)
  BOHOL_DATA_PATH   갱신할 scan-data.json 경로 (기본: 상위 폴더 bohol/scan-data.json)

실행:  python3 server.py            # 또는 PORT=8765 python3 server.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scan import DEFAULT_DATA_PATH, ScanError, run_scan  # noqa: E402

LOG = logging.getLogger("bohol-scanner")

SCAN_LOCK = threading.Lock()
SCAN_LOCK_TIMEOUT = 90  # 초. 같은 시각에 두 번 눌러도 순서대로 처리한다.

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept",
    "Access-Control-Max-Age": "600",
}


def route_path(raw_path: str) -> str:
    """'/bohol/api/scan?x=1' → '/api/scan' 처럼 정규화한다."""
    path = urlsplit(raw_path or "/").path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    for prefix in ("/bohol", "/bohol-dashboard"):
        if path == prefix:
            return "/"
        if path.startswith(prefix + "/"):
            path = path[len(prefix):]
            break
    return path


def data_path() -> Path:
    return Path(os.environ.get("BOHOL_DATA_PATH") or DEFAULT_DATA_PATH).expanduser().resolve()


class Handler(BaseHTTPRequestHandler):
    server_version = "BoholScanner/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 130  # 스캔이 길어져도 응답을 끊지 않는다.

    # ---------- 응답 도우미
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in CORS_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def send_no_content(self) -> None:
        self.send_response(204)
        for key, value in CORS_HEADERS.items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------- 라우팅
    def do_OPTIONS(self):  # noqa: N802
        self.send_no_content()

    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    def do_GET(self):  # noqa: N802
        self._handle(read_only=False)

    def do_POST(self):  # noqa: N802
        self._handle(read_only=False)

    def _handle(self, read_only: bool) -> None:
        path = route_path(self.path)
        if path == "/api/health":
            self.send_json(200, {"ok": True})
            return
        if path == "/api/scan":
            self.scan()
            return
        self.send_json(404, {"ok": False, "error": "not_found", "path": path})

    def scan(self) -> None:
        target = data_path()
        acquired = SCAN_LOCK.acquire(timeout=SCAN_LOCK_TIMEOUT)
        if not acquired:
            self.send_json(
                503,
                {"ok": False, "error": "scan_in_progress", "message": "이미 스캔이 진행 중입니다."},
            )
            return
        LOG.info("스캔 시작 — %s", target)
        try:
            data = run_scan(target)
        except ScanError as exc:
            LOG.warning("스캔 실패: %s", exc)
            self.send_json(502, {"ok": False, "error": "scan_failed", "message": str(exc)})
        except Exception as exc:  # noqa: BLE001 - 서버는 살아 있어야 한다
            LOG.exception("예기치 못한 오류")
            self.send_json(500, {"ok": False, "error": "internal_error", "message": str(exc)})
        else:
            air = (data.get("latest") or {}).get("air") or {}
            LOG.info(
                "스캔 완료 — %s원 / 관측 %s건 / alert=%s",
                air.get("perPersonRoundTrip"),
                air.get("observations"),
                (data.get("latest") or {}).get("alert"),
            )
            self.send_json(200, data)
        finally:
            SCAN_LOCK.release()

    # ---------- 로그
    def log_message(self, fmt, *args):  # noqa: A003
        LOG.info("%s - %s", self.address_string(), fmt % args)


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="보홀 대시보드 스캔 API 서버")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    parser.add_argument("--data-path", default=None, help="scan-data.json 경로")
    args = parser.parse_args(argv)

    if args.data_path:
        os.environ["BOHOL_DATA_PATH"] = str(Path(args.data_path).expanduser().resolve())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    target = data_path()
    if not target.exists():
        LOG.warning("scan-data.json 이 아직 없습니다: %s (첫 스캔은 실패로 응답합니다)", target)

    server = make_server(args.host, args.port)
    LOG.info("보홀 스캔 API 시작 — http://%s:%s  (데이터: %s)", args.host, args.port, target)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("종료 요청")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
