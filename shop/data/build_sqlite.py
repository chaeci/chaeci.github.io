#!/usr/bin/env python3
"""Build a real SQLite database from schema.sql + schema-seed.json.

Usage:
    python3 fashion-shop/data/build_sqlite.py [--out fashion-shop/data/mono-atelier.db]
"""
import argparse
import json
import pathlib
import sqlite3

HERE = pathlib.Path(__file__).resolve().parent
ORDER = ["users", "products", "product_images", "product_variants", "orders", "order_items",
         "order_claims", "cart_items", "coupons"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=str(HERE / "schema-seed.json"))
    ap.add_argument("--sql", default=str(HERE / "schema.sql"))
    ap.add_argument("--out", default=str(HERE / "mono-atelier.db"))
    args = ap.parse_args()

    seed = json.loads(pathlib.Path(args.seed).read_text(encoding="utf-8"))
    out = pathlib.Path(args.out)
    if out.exists():
        out.unlink()

    con = sqlite3.connect(out)
    con.row_factory = sqlite3.Row
    con.executescript(pathlib.Path(args.sql).read_text(encoding="utf-8"))

    for table in ORDER:
        rows = seed.get(table) or []
        if not rows:
            continue
        cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table})")]
        payload = []
        for row in rows:
            values = []
            for c in cols:
                v = row.get(c)
                if isinstance(v, bool):
                    v = int(v)
                values.append(v)
            payload.append(values)
        placeholders = ",".join("?" * len(cols))
        con.executemany(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", payload)
    con.commit()

    # 쿠폰 발급 대상(coupons.target_user_ids JSON 배열) → coupon_targets 정규화 테이블
    target_rows = []
    for c in seed.get("coupons") or []:
        for uid in (c.get("target_user_ids") or []):
            target_rows.append((f"ct_{c['id']}_{uid}", c["id"], uid, c["created_at"]))
    if target_rows:
        con.executemany(
            "INSERT INTO coupon_targets (id, coupon_id, user_id, created_at) VALUES (?,?,?,?)",
            target_rows)
    con.commit()

    print(f"→ {out} ({out.stat().st_size // 1024} KB)")
    for table in ORDER:
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<17} {n} rows")

    print("\n검증 쿼리")
    bad_fk = con.execute("""
        SELECT COUNT(*) FROM order_items oi
        LEFT JOIN product_variants v ON v.id = oi.variant_id
        WHERE v.id IS NULL""").fetchone()[0]
    print("  order_items → product_variants 누락:", bad_fk)
    bad_total = con.execute("""
        SELECT COUNT(*) FROM v_order_summary
        WHERE subtotal + shipping_fee - discount_amount <> total_amount""").fetchone()[0]
    print("  주문 금액 불일치(합계+배송비−할인):", bad_total)
    print("  쿠폰:", ", ".join(
        f"{r[0]} {'%d%%' % r[1] if r[2] == 'percent' else '%d원' % r[1]}"
        for r in con.execute("SELECT code, discount_value, discount_type FROM coupons ORDER BY code"))
          or "(없음)")
    print("  전용 쿠폰 발급 대상:", ", ".join(
        f"{r[0]} → {r[1]}({r[2]})" for r in con.execute(
            "SELECT code, user_name, email FROM v_coupon_targets ORDER BY code")) or "(전체 공용만)")
    print("  갤러리 이미지/상품:", con.execute(
        "SELECT ROUND(AVG(c), 1) FROM (SELECT COUNT(*) c FROM product_images GROUP BY product_id)"
    ).fetchone()[0])
    top = con.execute("""
        SELECT p.name, s.stock_total FROM v_product_stock s
        JOIN products p ON p.id = s.product_id
        ORDER BY s.stock_total DESC LIMIT 3""").fetchall()
    print("  재고 상위:", ", ".join(f"{r[0]} {r[1]}개" for r in top))
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    print("  foreign_key_check:", "OK" if not fk else fk)
    print("  coupon_targets:", con.execute("SELECT COUNT(*) FROM coupon_targets").fetchone()[0], "rows")
    print("  교환/반품 접수:", ", ".join(
        f"{r[0]} {r[1]} {'무료' if r[2] == 0 else str(r[2]) + '원 결제'} ({r[3]})"
        for r in con.execute(
            "SELECT claim_type, reason_category, shipping_fee, claim_status FROM v_order_claims ORDER BY created_at"))
          or "(없음)")
    print("  한 주문당 클레임 1건:", "OK" if not con.execute(
        "SELECT COUNT(*) FROM (SELECT order_id FROM order_claims GROUP BY order_id HAVING COUNT(*) > 1)"
    ).fetchone()[0] else "중복 있음")
    con.close()


if __name__ == "__main__":
    main()
