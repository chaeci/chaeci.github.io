#!/usr/bin/env python3
"""scan.py 단위 테스트 (네트워크·실제 파일 없이 동작).

실행:  python3 bohol/scanner/test_scan.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scan  # noqa: E402

KST = timezone(timedelta(hours=9))

# enjoysky 실제 페이지의 "출발 월별 최저가" 표 구조를 그대로 축약한 조각
MONTH_TABLE_HTML = """
<div class="table-scroll">
<table class="credit-table">
  <thead><tr><th>출발 월</th><th class="num-cell">최저가</th><th class="num-cell">관측 건수</th></tr></thead>
  <tbody>
    <tr><td>2027년 2월</td><td class="num-cell">379,000원</td><td class="num-cell">1,473</td></tr>
    <tr><td>2027년 3월</td><td class="num-cell">355,400원</td><td class="num-cell">1,249</td></tr>
    <tr><td>2027년 4월</td><td class="num-cell">384,809원</td><td class="num-cell">263</td></tr>
    <tr><td>2027년 5월</td><td class="num-cell">403,672원</td><td class="num-cell">135</td></tr>
  </tbody>
</table>
</div>
"""

AIRPORT_TABLE_HTML = """
<table class="credit-table">
  <thead><tr><th>출발</th><th class="num-cell">최저가</th><th class="num-cell">관측 건수</th></tr></thead>
  <tbody><tr><td>김해(부산)</td><td class="num-cell">218,002원</td><td class="num-cell">2,249</td></tr></tbody>
</table>
"""


def sample_data() -> dict:
    return {
        "schema": 1,
        "updatedAt": "2026-11-26T10:05:00+09:00",
        "source": "🐢 4월 보홀 항공·헤난 리조트 가격 스캔 (매일 오전 10:00)",
        "goals": {"air4Total": 1650000, "hotel4Nights": 1250000},
        "latest": {
            "scannedAt": "2026-11-26T10:05:00+09:00",
            "headline": "4월 하계 특가 오픈 전 · 알림 기준 미달",
            "alert": False,
            "air": {
                "source": "엔조이스카이",
                "url": "https://enjoysky.net/destinations/bohol",
                "perPersonRoundTrip": 384454,
                "prevPerPersonRoundTrip": 381053,
                "observations": 272,
                "basis": "2027년 4월 출발 왕복 최저가 · 4월 중 가장 싼 날짜 조합 기준(1인)",
                "note": "4/13~18처럼 날짜를 고정한 값이 아니라, 4월 안에서 가장 싼 조합의 관측값입니다.",
            },
            "hotel": {"familyRoom4Nights": None, "note": "미포착"},
            "deals": {"jinMarket": "미오픈", "jejuCham": "미오픈", "note": "발표 전"},
        },
        "reference": {"tripComHotel": {"total": 1560878}},
        "logs": [
            {"date": "2026-11-25", "time": "10:03", "title": "일일 스캔", "airPerPerson": 381053,
             "observations": 274, "alert": False, "note": "x"},
            {"date": "2026-11-26", "time": "10:05", "title": "일일 스캔", "airPerPerson": 384454,
             "observations": 272, "alert": False, "note": "y"},
        ],
    }


class ParseTests(unittest.TestCase):
    def test_month_row(self):
        price, obs = scan.parse_month_price(MONTH_TABLE_HTML + AIRPORT_TABLE_HTML, "2027-04")
        self.assertEqual(price, 384809)
        self.assertEqual(obs, 263)

    def test_other_month(self):
        price, obs = scan.parse_month_price(MONTH_TABLE_HTML, "2027-03")
        self.assertEqual((price, obs), (355400, 1249))

    def test_missing_month_raises(self):
        with self.assertRaises(scan.ScanError):
            scan.parse_month_price(MONTH_TABLE_HTML, "2027-06")

    def test_bad_month_format(self):
        with self.assertRaises(scan.ScanError):
            scan.parse_month_price(MONTH_TABLE_HTML, "202704")

    def test_regex_fallback_without_header(self):
        # 헤더(th)가 없는 조각이어도 원문 정규식으로 찾아낸다
        html = '<tr><td class="m">2027년 4월</td><td>384,809원</td><td>263</td></tr>'
        self.assertEqual(scan.parse_month_price(html, "2027-04"), (384809, 263))

    def test_price_helpers(self):
        self.assertEqual(scan._parse_price("384,809원"), 384809)
        self.assertEqual(scan._parse_price("1,473"), 1473)
        self.assertIsNone(scan._parse_price("직항 없음"))


class ApplyTests(unittest.TestCase):
    def when(self):
        return datetime(2026, 11, 26, 17, 30, 0, tzinfo=KST)

    def test_price_change_updates_prev(self):
        out = scan.apply_scan(sample_data(), 384809, 263, self.when())
        air = out["latest"]["air"]
        self.assertEqual(air["perPersonRoundTrip"], 384809)
        self.assertEqual(air["prevPerPersonRoundTrip"], 384454)
        self.assertEqual(air["observations"], 263)
        self.assertEqual(out["updatedAt"], "2026-11-26T17:30:00+09:00")
        self.assertEqual(out["latest"]["scannedAt"], "2026-11-26T17:30:00+09:00")

    def test_same_price_keeps_prev(self):
        out = scan.apply_scan(sample_data(), 384454, 300, self.when())
        air = out["latest"]["air"]
        self.assertEqual(air["perPersonRoundTrip"], 384454)
        self.assertEqual(air["prevPerPersonRoundTrip"], 381053)

    def test_normal_price_no_alert(self):
        out = scan.apply_scan(sample_data(), 384809, 263, self.when())
        latest = out["latest"]
        self.assertFalse(latest["alert"])
        self.assertEqual(
            latest["headline"],
            "엔조이스카이 4월 최저 384,809원 (4인 추정 154만) · 하계 특가 대기",
        )

    def test_cheap_price_alerts(self):
        out = scan.apply_scan(sample_data(), 299000, 300, self.when())
        latest = out["latest"]
        self.assertTrue(latest["alert"])
        self.assertIn("1인 30만 원 이하", latest["headline"])
        self.assertIn("299,000원", latest["headline"])

    def test_big_drop_alerts(self):
        out = scan.apply_scan(sample_data(), 320000, 300, self.when())
        latest = out["latest"]
        self.assertTrue(latest["alert"])  # 384,454 → 320,000 = -16.8%
        self.assertIn("급락", latest["headline"])

    def test_small_drop_no_alert(self):
        out = scan.apply_scan(sample_data(), 340000, 300, self.when())
        self.assertFalse(out["latest"]["alert"])  # -11.6%

    def test_same_day_log_is_updated_not_duplicated(self):
        data = sample_data()
        out = scan.apply_scan(data, 384809, 263, self.when())
        logs = out["logs"]
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[-1]["date"], "2026-11-26")
        self.assertEqual(logs[-1]["time"], "17:30")
        self.assertEqual(logs[-1]["airPerPerson"], 384809)
        self.assertIn("직전 대비 ▲ 355원", logs[-1]["note"])

    def test_new_day_log_appended(self):
        out = scan.apply_scan(
            sample_data(), 384809, 263, datetime(2026, 11, 27, 10, 0, tzinfo=KST)
        )
        self.assertEqual(len(out["logs"]), 3)
        self.assertEqual(out["logs"][-1]["date"], "2026-11-27")

    def test_logs_capped_at_30(self):
        data = sample_data()
        data["logs"] = [
            {"date": f"2026-10-{d:02d}", "time": "10:00", "airPerPerson": 350000}
            for d in range(1, 31)
        ]
        out = scan.apply_scan(
            data, 384809, 263, datetime(2026, 11, 27, 10, 0, tzinfo=KST)
        )
        self.assertEqual(len(out["logs"]), 30)
        self.assertEqual(out["logs"][-1]["date"], "2026-11-27")

    def test_reference_and_deals_preserved(self):
        out = scan.apply_scan(sample_data(), 384809, 263, self.when())
        self.assertEqual(out["reference"]["tripComHotel"]["total"], 1560878)
        self.assertEqual(out["latest"]["deals"]["jinMarket"], "미오픈")


class FileTests(unittest.TestCase):
    def test_atomic_write_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan-data.json"
            data = sample_data()
            scan.write_json_atomic(path, data)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), data)
            self.assertEqual([p.name for p in path.parent.iterdir()], ["scan-data.json"])

    def test_run_scan_with_fake_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan-data.json"
            path.write_text(json.dumps(sample_data(), ensure_ascii=False), encoding="utf-8")
            original = scan.fetch_html
            scan.fetch_html = lambda *a, **k: MONTH_TABLE_HTML  # type: ignore[assignment]
            try:
                out = scan.run_scan(path)
            finally:
                scan.fetch_html = original
            self.assertEqual(out["latest"]["air"]["perPersonRoundTrip"], 384809)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["latest"]["air"]["perPersonRoundTrip"], 384809)

    def test_missing_data_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = scan.fetch_html
            scan.fetch_html = lambda *a, **k: MONTH_TABLE_HTML  # type: ignore[assignment]
            try:
                with self.assertRaises(scan.ScanError):
                    scan.run_scan(Path(tmp) / "nope.json")
            finally:
                scan.fetch_html = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
