#!/usr/bin/env python3
"""MONO ATELIER — 토스페이먼츠 결제 승인(confirm) 서버 예제.

브라우저(shop/index.html)는 결제창에서 돌아온 뒤 아래 값을 보냅니다.

    POST /api/payments/confirm
    { "paymentKey": "…", "orderId": "MA20261126-1234", "amount": 578000 }

이 서버가 시크릿 키로 토스페이먼츠 승인 API를 호출하면 그때 실제 결제가 확정됩니다.
정적 데모(GitHub Pages)에서는 이 서버가 없어서 클라이언트가 '테스트 승인'으로 주문만 확정합니다.

------------------------------------------------------------------------------
1) 환경 변수 (절대 코드·저장소에 시크릿 키를 넣지 마세요)
    export TOSS_SECRET_KEY="test_sk_…"     # 테스트
    export TOSS_SECRET_KEY="live_sk_…"     # 실결제
   클라이언트 키와 같은 세트여야 합니다.
     결제창(구버전)  client test_ck_… ↔ secret test_sk_…
     주문서형·결제창형 client test_gck_… ↔ secret test_gsk_…

2) 앱에서 연결
    PAYMENT_CONFIG.confirmApiUrl = '/api/payments/confirm'
    (fashion-shop/src/app.js 상단 PAYMENT_CONFIG)

3) 실행 예 (FastAPI + uvicorn, 선택)
    pip install fastapi uvicorn
    uvicorn payment_confirm_example:app --port 8000
    # GitHub Pages 는 https://chaeci.github.io/shop/ 이므로 CORS 허용 출처를 그 도메인으로 제한하세요.

이 파일은 표준 라이브러리만으로도 승인 API를 호출할 수 있게 작성했습니다.
python3 payment_confirm_example.py --selftest   로 문법·설정만 점검할 수 있습니다.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

TOSS_CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"
DB_PATH = os.environ.get("MONO_DB", os.path.join(os.path.dirname(__file__), "mono-atelier.db"))


# --------------------------------------------------------------------- 공통
def auth_header(secret_key: str) -> str:
    """시크릿 키 + ':' 를 base64 로 인코딩한 Basic 인증 헤더 (콜론 누락 주의)."""
    token = base64.b64encode((secret_key + ":").encode("utf-8")).decode("ascii")
    return "Basic " + token


def confirm_with_toss(payment_key: str, order_id: str, amount: int, secret_key: str | None = None) -> dict:
    """토스페이먼츠 결제 승인 API 호출. 성공 시 Payment 객체(dict)를 돌려줍니다."""
    secret_key = secret_key or os.environ.get("TOSS_SECRET_KEY", "")
    if not secret_key:
        raise RuntimeError("TOSS_SECRET_KEY 환경 변수가 없습니다. 시크릿 키는 서버에만 두세요.")

    body = json.dumps({"paymentKey": payment_key, "orderId": order_id, "amount": int(amount)}).encode("utf-8")
    req = urllib.request.Request(
        TOSS_CONFIRM_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": auth_header(secret_key),
            "Content-Type": "application/json",
            "Idempotency-Key": "confirm-" + order_id,  # 재시도 시 중복 승인 방지
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"토스 승인 실패 HTTP {exc.code}: {detail}") from exc


# ---------------------------------------------------------------- SQLite 저장
def ensure_columns(conn: sqlite3.Connection) -> None:
    """data/schema.sql 의 orders 테이블에 결제 메타 컬럼이 있는지 확인합니다."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
    for name, ddl in (
        ("payment_provider", "TEXT NOT NULL DEFAULT 'demo'"),
        ("payment_key", "TEXT"),
        ("payment_mode", "TEXT NOT NULL DEFAULT 'demo'"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {ddl}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_payment_key ON orders(payment_key)")


def find_order(conn: sqlite3.Connection, order_id: str) -> dict | None:
    cur = conn.execute(
        "SELECT id, order_no, status, total_amount, shipping_fee, payment_key, payment_mode "
        "FROM orders WHERE order_no = ?",
        (order_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = [c[0] for c in cur.description]
    return dict(zip(keys, row))


def mark_confirmed(conn: sqlite3.Connection, order_id: str, payment_key: str, payment: dict) -> None:
    conn.execute(
        "UPDATE orders SET status = 'paid', payment_provider = 'tosspayments', "
        "payment_key = ?, payment_mode = 'server' WHERE order_no = ?",
        (payment_key, order_id),
    )
    conn.commit()


# ------------------------------------------------------------- 서버 핸들러 본문
def handle_confirm(payment_key: str, order_id: str, amount: int, db_path: str | None = None) -> dict:
    """브라우저가 보낸 paymentKey·orderId·amount 를 검증하고 승인까지 수행합니다.

    반드시 서버에 저장해 둔 주문 금액과 대조한 뒤 승인하세요.
    (클라이언트가 보낸 amount 를 그대로 믿으면 금액 조작이 가능합니다.)
    """
    conn = sqlite3.connect(db_path or DB_PATH)
    try:
        ensure_columns(conn)
        order = find_order(conn, order_id)
        if not order:
            return {"ok": False, "message": "주문을 찾을 수 없습니다."}
        if order["status"] == "cancelled":
            return {"ok": False, "message": "취소된 주문입니다."}
        if order["payment_key"]:
            # 같은 paymentKey 로 다시 요청 → 이미 승인된 결제(멱등 응답)
            if order["payment_key"] == payment_key:
                return {"ok": True, "duplicate": True, "orderId": order_id}
            return {"ok": False, "message": "이미 다른 결제로 확정된 주문입니다."}
        if int(order["total_amount"]) != int(amount):
            return {"ok": False, "message": "결제 금액이 주문 금액과 다릅니다."}

        payment = confirm_with_toss(payment_key, order_id, amount)
        mark_confirmed(conn, order_id, payment_key, payment)
        return {
            "ok": True,
            "orderId": order_id,
            "paymentKey": payment_key,
            "method": payment.get("method"),
            "totalAmount": payment.get("totalAmount"),
            "approvedAt": payment.get("approvedAt"),
        }
    finally:
        conn.close()


# --------------------------------------------------- 선택: FastAPI 라우트 예제
def build_app():  # pragma: no cover - 문서용 예제
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="MONO ATELIER 결제 승인")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://chaeci.github.io", "http://localhost:8000"],
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )

    class ConfirmBody(BaseModel):
        paymentKey: str
        orderId: str
        amount: int

    @app.post("/api/payments/confirm")
    def confirm(body: ConfirmBody):
        result = handle_confirm(body.paymentKey, body.orderId, body.amount)
        if not result.get("ok"):
            raise HTTPException(status_code=402, detail=result.get("message", "승인 실패"))
        return result

    return app


try:  # uvicorn payment_confirm_example:app
    app = build_app()
except Exception:  # fastapi 미설치 시에도 순수 함수는 사용 가능
    app = None


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        assert auth_header("test_sk_abc") == "Basic dGVzdF9za19hYmM6"
        print("selftest ok · TOSS_SECRET_KEY 설정:", bool(os.environ.get("TOSS_SECRET_KEY")))
        print("DB:", DB_PATH)
        sys.exit(0)
    print(__doc__)
