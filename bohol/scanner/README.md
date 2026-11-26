# 보홀 대시보드 실시간 스캔 (내부서버용)

`bohol/index.html`의 **「지금 가격 스캔」** 버튼이 호출하는 작은 API 서버입니다.
엔조이스카이의 보홀 항공권 페이지에서 **2027년 4월 출발 1인 왕복 최저가 · 관측 건수**를 읽어
`bohol/scan-data.json`을 다시 쓰고, 갱신된 JSON을 그대로 돌려줍니다.

- Python 3.8+ **표준 라이브러리만** 사용합니다. `pip install` 필요 없음.
- 외부에 직접 열지 말고 Nginx 뒤 `127.0.0.1`에만 바인딩하세요.

## 파일

| 파일 | 역할 |
| --- | --- |
| `scan.py` | 스캔 본체. `python3 scan.py`로 단독 실행(크론용), `run_scan()`으로 import 가능 |
| `server.py` | `GET /api/health`, `GET·POST /api/scan` HTTP 서버 (기본 포트 8765) |
| `test_scan.py` | 파서·갱신 로직 단위 테스트 (`python3 test_scan.py`) |

## 1. 먼저 손으로 한 번 돌려보기

```bash
cd /var/www/bohol/scanner          # 저장소의 bohol/scanner 를 서버에 둔 위치
python3 test_scan.py               # 19개 테스트, 네트워크 불필요
python3 scan.py --dry-run          # 실제 페이지를 읽어 값만 확인 (파일 안 씀)
python3 scan.py                    # ../scan-data.json 실제 갱신
```

`--dry-run` 출력 예:

```
[dry-run] 2027-04 1인 왕복 최저 384,809원 · 관측 263건
[dry-run] 현재 파일 값 384,454원 ( ▲ 355원 )
```

데이터 파일 위치는 `--data-path /경로/scan-data.json` 또는 `BOHOL_DATA_PATH` 환경변수로 바꿀 수 있습니다.
(기본값: 이 폴더의 상위 폴더, 즉 `bohol/scan-data.json`)

## 2. systemd 서비스

`/etc/systemd/system/bohol-scanner.service`:

```ini
[Unit]
Description=Bohol dashboard scan API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/bohol/scanner
Environment=HOST=127.0.0.1
Environment=PORT=8765
Environment=BOHOL_DATA_PATH=/var/www/bohol/scan-data.json
ExecStart=/usr/bin/python3 /var/www/bohol/scanner/server.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bohol-scanner
sudo systemctl status bohol-scanner --no-pager
journalctl -u bohol-scanner -f          # 로그
```

**권한**: 서비스가 `scan-data.json`을 직접 덮어써야 하므로 데이터 파일과 그 폴더에 쓰기 권한이 필요합니다.

```bash
sudo chown -R www-data:www-data /var/www/bohol
sudo chmod 755 /var/www/bohol /var/www/bohol/scanner
```

(파일은 원자적 교체 후 `0644`로 저장되므로 Nginx가 그대로 읽을 수 있습니다.)

## 3. Nginx 설정

대시보드가 `https://서버/bohol/` 에 있고 API도 같은 주소 아래에 두는 구성입니다.
`/bohol/api/...` 를 그대로 프록시하면 `index.html`이 호출하는 `./api/scan`(→ `/bohol/api/scan`)이 연결됩니다.

```nginx
server {
    listen 80;
    server_name bohol.example.internal;   # 실제 도메인/IP

    root /var/www/bohol;                  # index.html, scan-data.json 이 있는 곳

    location /bohol/ {
        try_files $uri $uri/ =404;
    }

    location /bohol/api/ {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 120s;          # 스캔이 길어질 때 대비
    }
}
```

- 페이지를 루트(`/`)에 두고 API만 따로 쓰고 싶으면
  `location = /api/scan { proxy_pass http://127.0.0.1:8765; ... }` 처럼 **정확히 같은 경로**로 프록시하세요.
  (`/bohol` 접두사가 붙은 경로도 서버가 함께 받습니다.)
- 설정 후 `sudo nginx -t && sudo systemctl reload nginx`.
- 외부에 공개된 서버라면 스캔 남용을 막기 위해 `allow 192.168.0.0/16; deny all;` 또는
  `auth_basic` 을 `location /bohol/api/` 안에 두는 것을 권합니다.

## 4. (선택) 매일 10시 자동 스캔

지금은 피클 정기 스캔이 기록을 갱신하므로 필수는 아닙니다. 서버에서 직접 돌리고 싶을 때만:

```cron
# sudo crontab -e  (서비스 계정과 같은 사용자로)
0 10 * * * /usr/bin/python3 /var/www/bohol/scanner/scan.py >> /var/log/bohol-scan.log 2>&1
```

## 5. 동작 확인

```bash
curl -s http://127.0.0.1:8765/api/health
# {"ok": true}

curl -s -X POST http://127.0.0.1:8765/api/scan | python3 -m json.tool | head -30
# 갱신된 scan-data.json 전체가 그대로 온다
```

브라우저에서 `https://서버/bohol/` 을 열고 **「지금 가격 스캔」** 을 누르면
버튼이 `스캔 중…` 으로 바뀌었다가, 값·로그가 갱신되고 스캔 카드에 `방금 스캔` 배지가 붙습니다.

## 갱신 규칙 (scan-data.json 스키마 유지)

- `updatedAt`, `latest.scannedAt` → 현재 KST(+09:00) 시각
- `latest.air.perPersonRoundTrip`, `observations` → 새 값
- `prevPerPersonRoundTrip` → 값이 바뀌면 **직전 값**, 같으면 기존 비교값 유지
- `latest.alert` → **1인 30만 원 이하** 또는 **직전 스캔 대비 15% 이상 급락**일 때만 `true`
  (엔조이스카이 값은 4/13~18 고정 날짜가 아니라 4월 전체 최저 조합이라, 평상시 38만 원대에서
  특가 배지가 뜨지 않도록 한 기준입니다.)
- `latest.headline` → `엔조이스카이 4월 최저 384,809원 (4인 추정 154만) · 하계 특가 대기`
- `logs` → 오늘 날짜 항목이 있으면 시각·금액만 갱신(중복 방지), 없으면 추가, 최근 30개 유지
- `hotel`, `deals`, `reference`, `trip`, `goals` → 손대지 않고 그대로 보존
- 저장은 임시 파일 → `os.replace` 원자적 교체

## 문제 해결

| 증상 | 확인 |
| --- | --- |
| 버튼을 누르면 `내부서버 API 연결 필요` | 서버가 안 떠 있거나 Nginx `location` 경로 불일치. `curl http://127.0.0.1:8765/api/health` 로 확인 |
| `502 scan_failed` + `행을 찾지 못했습니다` | 엔조이스카이 페이지 구조 변경. `scan.py`의 `parse_month_price()` 확인 |
| `502` + `요청 실패` | 서버에서 외부 HTTPS(443) 나가는지, 일시 차단(429) 아닌지 확인 |
| `503 scan_in_progress` | 같은 순간에 스캔이 겹침. 잠시 후 다시 |
| 값이 갱신되지 않음 | `BOHOL_DATA_PATH`가 실제로 보이는 파일인지, 서비스 사용자 쓰기 권한 확인 |
