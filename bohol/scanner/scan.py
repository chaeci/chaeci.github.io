#!/usr/bin/env python3
"""보홀 대시보드용 항공권 가격 스캔.

enjoysky.net 의 보홀 목적지 페이지에서 "출발 월별 최저가" 표의 2027년 4월 행
(1인 왕복 최저가 · 관측 건수)을 읽어 bohol/scan-data.json 을 갱신한다.

알림은 1인 30만 원 이하이거나 직전 스캔 대비 15% 이상 급락했을 때만 켠다.
(월 최저 조합을 고정 날짜 특가로 오해하지 않도록 하기 위함)

- Python 3 표준 라이브러리만 사용한다(pip install 불필요).
- 단독 실행:  python3 scan.py [--dry-run] [--data-path PATH]
- 서버에서 import:  from scan import run_scan

환경변수
  BOHOL_DATA_PATH   갱신할 scan-data.json 경로(기본: 이 파일의 상위 폴더 = bohol/)
  BOHOL_TARGET_MONTH 대상 월 YYYY-MM (기본 2027-04)
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

KST = timezone(timedelta(hours=9))

DEFAULT_URL = "https://enjoysky.net/destinations/bohol"
DEFAULT_TARGET_MONTH = "2027-04"
DEFAULT_GOAL_AIR4 = 1650000

# 알림(alert) 기준 — 엔조이스카이 값은 4월 전체 최저 조합이라 고정 날짜 특가와 다르다.
# 그래서 목표가(4인 165만) 도달만으로는 알림을 띄우지 않는다.
#   · 1인 30만 원 이하로 급락했거나
#   · 직전 스캔 대비 15% 이상 떨어졌을 때만 특가로 본다.
ALERT_PRICE_CEILING = 300000
ALERT_DROP_RATIO = 0.15

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
ACCEPT_LANGUAGE = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"

TIMEOUT = 25
FETCH_RETRIES = 2
MAX_LOGS = 30

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = BASE_DIR.parent / "scan-data.json"


class ScanError(RuntimeError):
    """스캔 실패(네트워크·파싱·데이터 파일 문제)를 나타낸다."""


# ---------------------------------------------------------------- HTML 파싱


class _TableParser(HTMLParser):
    """표를 [(헤더 셀들, [행별 셀들])] 로 모으는 최소 파서."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict] = []
        self._table: dict | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._cell_is_header = False

    # -- 태그
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._table = {"header": [], "rows": []}
        elif tag == "tr":
            if self._table is not None:
                self._row = []
        elif tag in ("td", "th"):
            if self._row is not None:
                self._cell = []
                self._cell_is_header = tag == "th"
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_startendtag(self, tag, attrs):
        # <br /> 처럼 스스로 닫히는 태그
        if tag.lower() == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            text = _clean("".join(self._cell))
            self._row.append(text)
            if self._cell_is_header and self._table is not None:
                self._table["header"].append(text)
            self._cell = None
            self._cell_is_header = False
        elif tag == "tr":
            if self._table is not None and self._row:
                self._table["rows"].append(self._row)
            self._row = None
        elif tag == "table":
            if self._table is not None:
                self.tables.append(self._table)
            self._table = None
            self._row = None
            self._cell = None


def _clean(text: str) -> str:
    """셀 텍스트 정리: 공백·줄바꿈·nbsp 압축."""
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_price(text: str) -> int | None:
    """'384,809원' → 384809. 숫자가 없으면 None."""
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits) if digits else None


def _parse_count(text: str) -> int | None:
    return _parse_price(text)


# 폴백용: 표 파서가 깨져도 동작하도록 원문에서 직접 찾는 정규식
_MONTH_ROW_RE = re.compile(
    r"<tr>\s*<td[^>]*>\s*(\d{4})\s*년\s*(\d{1,2})\s*월\s*</td>\s*"
    r"<td[^>]*>\s*([0-9][0-9,]*)\s*원\s*</td>\s*"
    r"<td[^>]*>\s*([0-9][0-9,]*)\s*</td>",
    re.S,
)


def parse_month_price(html: str, target_month: str = DEFAULT_TARGET_MONTH) -> tuple[int, int]:
    """페이지 HTML 에서 대상 월의 (1인 왕복 최저가, 관측 건수) 를 돌려준다."""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", target_month.strip())
    if not m:
        raise ScanError(f"대상 월 형식이 잘못되었습니다: {target_month!r} (YYYY-MM)")
    year, month = int(m.group(1)), int(m.group(2))

    parser = _TableParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - 깨진 HTML 이라도 폴백으로 시도한다
        parser.tables = []

    for table in parser.tables:
        header = " ".join(table.get("header") or [])
        if "출발 월" not in header:
            continue
        for row in table.get("rows") or []:
            if len(row) < 3:
                continue
            hit = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월", row[0])
            if not hit:
                continue
            if int(hit.group(1)) != year or int(hit.group(2)) != month:
                continue
            price = _parse_price(row[1])
            if price is None:
                continue
            return price, _parse_count(row[2]) or 0

    for hit in _MONTH_ROW_RE.finditer(html):
        if int(hit.group(1)) == year and int(hit.group(2)) == month:
            return int(hit.group(3).replace(",", "")), int(hit.group(4).replace(",", ""))

    raise ScanError(
        f"페이지에서 '{year}년 {month}월' 최저가 행을 찾지 못했습니다. "
        "enjoysky 페이지 구조가 바뀌었는지 확인해 주세요."
    )


# ---------------------------------------------------------------- 네트워크


def fetch_html(url: str = DEFAULT_URL, timeout: int = TIMEOUT, retries: int = FETCH_RETRIES) -> str:
    """브라우저와 같은 헤더로 페이지를 받아온다. 실패 시 ScanError."""
    last_error = ""
    for attempt in range(retries + 1):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": ACCEPT_LANGUAGE,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, "replace")
        except HTTPError as exc:
            last_error = f"HTTP {exc.code} {exc.reason}"
            if exc.code < 500 and exc.code != 429:
                break
        except (URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"
        if attempt < retries:
            time.sleep(2 + attempt * 2)
    raise ScanError(f"{url} 요청 실패 — {last_error}")


# ---------------------------------------------------------------- 데이터 갱신


def now_kst() -> datetime:
    return datetime.now(KST).replace(microsecond=0)


def _delta_text(price: int, prev: int | None) -> str:
    if prev is None:
        return "비교값 없음"
    diff = price - prev
    if diff == 0:
        return "직전과 동일"
    return ("▲ " if diff > 0 else "▼ ") + f"{abs(diff):,}원"


def apply_scan(
    data: dict,
    price: int,
    observations: int,
    when: datetime,
    target_month: str = DEFAULT_TARGET_MONTH,
) -> dict:
    """스캔 결과를 기존 JSON 구조에 반영한 새 dict 를 돌려준다(파일 쓰기 없음)."""
    data = copy.deepcopy(data)
    data.setdefault("schema", 1)
    latest = data.setdefault("latest", {})
    air = latest.setdefault("air", {})
    goals = data.setdefault("goals", {})
    if not isinstance(goals.get("air4Total"), (int, float)):
        goals["air4Total"] = DEFAULT_GOAL_AIR4
    goal_air4 = int(goals["air4Total"])

    old_price = air.get("perPersonRoundTrip")
    old_prev = air.get("prevPerPersonRoundTrip")
    if isinstance(old_price, int) and old_price != price:
        prev = old_price
    elif isinstance(old_price, int):
        prev = old_prev if isinstance(old_prev, int) else old_price
    else:
        prev = old_prev if isinstance(old_prev, int) else None

    iso = when.isoformat()
    year, month = target_month.split("-")

    air["source"] = air.get("source") or "엔조이스카이"
    air["url"] = air.get("url") or DEFAULT_URL
    air["perPersonRoundTrip"] = price
    if prev is not None:
        air["prevPerPersonRoundTrip"] = prev
    air["observations"] = observations
    air.setdefault(
        "basis",
        f"{year}년 {int(month)}월 출발 왕복 최저가 · 그 달에서 가장 싼 날짜 조합 기준(1인)",
    )
    air.setdefault(
        "note",
        "여행 날짜를 고정한 값이 아니라, 그 달 안에서 가장 싼 조합의 관측값입니다.",
    )

    total4 = price * 4
    man4 = round(total4 / 10000)

    # 급락 판정은 '직전 스캔 값'과 비교한다.
    base_for_drop = old_price if isinstance(old_price, int) else prev
    drop_ratio = 0.0
    if isinstance(base_for_drop, int) and base_for_drop > 0:
        drop_ratio = (base_for_drop - price) / base_for_drop

    if price <= ALERT_PRICE_CEILING:
        alert = True
        reason = "1인 30만 원 이하 특가 포착"
    elif drop_ratio >= ALERT_DROP_RATIO:
        alert = True
        reason = f"직전 대비 {drop_ratio * 100:.1f}% 급락"
    else:
        alert = False
        reason = ""

    head = f"엔조이스카이 {int(month)}월 최저 {price:,}원 (4인 추정 {man4}만)"
    latest["headline"] = f"{head} · {reason}" if alert else f"{head} · 하계 특가 대기"
    latest["alert"] = alert
    # 수동 스캔은 항공가만 갱신한다. 숙소·특가 오픈 정보는 그대로 둔다.
    latest.setdefault("hotel", {"familyRoom4Nights": None, "note": "숙소 가격은 매일 스캔에서 별도 확인."})
    latest.setdefault("deals", {"jinMarket": "확인 전", "jejuCham": "확인 전", "note": ""})

    data["updatedAt"] = iso
    latest["scannedAt"] = iso

    logs = data.get("logs")
    if not isinstance(logs, list):
        logs = []
    entry = {
        "date": when.strftime("%Y-%m-%d"),
        "time": when.strftime("%H:%M"),
        "title": "일일 스캔",
        "airPerPerson": price,
        "observations": observations,
        "alert": alert,
        "note": (
            f"{air['source']} {int(month)}월 최저가 {price:,}원"
            f"(직전 대비 {_delta_text(price, prev)}). 관측 {observations}건."
        ),
    }
    today = entry["date"]
    for index, old in enumerate(logs):
        if isinstance(old, dict) and old.get("date") == today:
            old.update(entry)
            old["title"] = old.get("title") or entry["title"]
            break
    else:
        logs.append(entry)

    logs.sort(key=lambda g: (str(g.get("date", "")), str(g.get("time", ""))))
    data["logs"] = logs[-MAX_LOGS:]
    return data


def write_json_atomic(path: Path, data: dict) -> None:
    """임시 파일에 쓴 뒤 os.replace 로 원자적 교체."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o644)  # nginx 가 읽을 수 있도록
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def resolve_data_path(data_path: str | os.PathLike | None = None) -> Path:
    raw = data_path or os.environ.get("BOHOL_DATA_PATH") or DEFAULT_DATA_PATH
    return Path(raw).expanduser().resolve()


def run_scan(
    data_path: str | os.PathLike | None = None,
    *,
    url: str = DEFAULT_URL,
    target_month: str | None = None,
    timeout: int = TIMEOUT,
) -> dict:
    """페이지를 스캔해 scan-data.json 을 갱신하고, 갱신된 전체 JSON 을 돌려준다."""
    path = resolve_data_path(data_path)
    month = target_month or os.environ.get("BOHOL_TARGET_MONTH") or DEFAULT_TARGET_MONTH

    if not path.exists():
        raise ScanError(f"scan-data.json 을 찾을 수 없습니다: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ScanError(f"scan-data.json 을 읽지 못했습니다: {exc}") from exc
    if not isinstance(data, dict):
        raise ScanError("scan-data.json 형식이 올바르지 않습니다(최상위가 객체가 아님).")

    html = fetch_html(url, timeout=timeout)
    price, observations = parse_month_price(html, month)
    updated = apply_scan(data, price, observations, now_kst(), month)
    write_json_atomic(path, updated)
    return updated


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="보홀 항공권 가격 스캔 → scan-data.json 갱신")
    parser.add_argument("--data-path", default=None, help="scan-data.json 경로(기본: 상위 폴더)")
    parser.add_argument("--url", default=DEFAULT_URL, help="스캔할 페이지 URL")
    parser.add_argument("--month", default=None, help="대상 월 YYYY-MM (기본 2027-04)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="요청 타임아웃(초)")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 파싱 결과만 출력")
    parser.add_argument("--quiet", action="store_true", help="성공 시 출력 최소화")
    args = parser.parse_args(argv)

    path = resolve_data_path(args.data_path)
    month = args.month or os.environ.get("BOHOL_TARGET_MONTH") or DEFAULT_TARGET_MONTH

    try:
        html = fetch_html(args.url, timeout=args.timeout)
        price, observations = parse_month_price(html, month)
    except ScanError as exc:
        print(f"[실패] {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"[dry-run] {month} 1인 왕복 최저 {price:,}원 · 관측 {observations:,}건")
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                old = ((data.get("latest") or {}).get("air") or {}).get("perPersonRoundTrip")
                if isinstance(old, int):
                    print(f"[dry-run] 현재 파일 값 {old:,}원 ( {_delta_text(price, old)} )")
                print(f"[dry-run] 파일을 쓰지 않았습니다: {path}")
            except (OSError, ValueError) as exc:
                print(f"[dry-run] 기존 파일을 읽지 못했습니다: {exc}", file=sys.stderr)
        else:
            print(f"[dry-run] 기존 파일 없음: {path}")
        return 0

    try:
        updated = run_scan(path, url=args.url, target_month=month, timeout=args.timeout)
    except ScanError as exc:
        print(f"[실패] {exc}", file=sys.stderr)
        return 1

    air = (updated.get("latest") or {}).get("air") or {}
    if not args.quiet:
        print(
            f"[완료] {updated.get('updatedAt')} · {air.get('perPersonRoundTrip'):,}원"
            f" (관측 {air.get('observations'):,}건, alert={updated.get('latest', {}).get('alert')})"
        )
        print(f"[완료] 저장: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
