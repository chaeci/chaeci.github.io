# MONO ATELIER — 백엔드 이관 · 보안 아키텍처 인수인계서

**버전 기준: v1.9.16 (2026-11-28) · 대상 저장소: `github.com/chaeci/chaeci.github.io` → `shop/`**

> **이 문서의 목적**
> 지금 `shop/index.html` 은 브라우저 `localStorage` 만 쓰는 **프론트 단독 정적 프로토타입**입니다.
> 기능은 완성되어 있지만 **모든 데이터·권한·금액 계산이 클라이언트에 있어 그대로는 운영할 수 없습니다.**
> 이 문서는 **Ubuntu 내부서버에서 이 저장소를 읽는 Gemini가, 이 문서 + `src/app.js` + `data/schema.sql` 세 가지로
> 곧바로 FastAPI + SQLite 보안 백엔드를 구현·배포**할 수 있도록 쓴 인수인계서입니다.
>
> **읽는 순서**
> 1. **§0 요약** (5분) → 무엇이 있고 무엇을 만들면 되는지
> 2. **§1 현재 상태** → 옮겨야 할 기능의 정확한 목록과 규칙(숫자 포함)
> 3. **§2 보안 취약점과 서버 원칙** → **반드시** 먼저 읽고 설계에 반영
> 4. **§3 API 명세** → 구현할 엔드포인트 전체
> 5. **§4 스택·배포** → Ubuntu + Nginx + systemd + `.env`
> 6. **§5 구현 순서·수용 기준** → 완료 판정 방법
>
> **같이 읽을 파일**
> | 파일 | 왜 필요한가 |
> |---|---|
> | `shop/src/app.js` (13,076줄) | 화면·계산·검증 로직의 **단일 원본**. 모든 규칙은 이 파일이 기준입니다. |
> | `shop/data/schema.sql` (455줄) | SQLite 스키마 21테이블 + 뷰 6종. DDL은 그대로 쓰면 됩니다. |
> | `shop/data/schema-seed.json` | 초기 데이터 21테이블(회원 5 · 상품 13 · 주문 21 …). 데모/테스트 데이터. |
> | `shop/data/build_sqlite.py` | 위 두 파일로 `mono-atelier.db` 를 만드는 스크립트 |
> | `shop/data/payment_confirm_example.py` | 토스페이먼츠 **서버 승인** 예제(그대로 이식 가능) |
> | `shop/.env.example` | 필수 환경변수 목록(값 없음) |
>
> 이 문서의 모든 줄 번호는 **v1.9.16 `shop/src/app.js` 기준**입니다. 코드가 바뀌면 함수명으로 다시 찾으세요.

---

## 0. 5분 요약

### 0.1 지금 상태

- `shop/index.html` **1,046,097 bytes** 단일 파일. 안에 CSS·JS·**시드 데이터 전체**가 인라인되어 있고, 브라우저 `localStorage` 에 21테이블 JSON을 저장하며 동작합니다.
- 정적 데모: <https://chaeci.github.io/shop/index.html> (GitHub Pages, 서버 없음)
- 그래서 지금은 **누구나 개발자도구로 관리자 권한·모든 회원 정보·모든 주문을 볼 수 있고, 금액을 바꿔 결제를 확정할 수 있습니다.** (§2 참조)

### 0.2 만들어야 할 것

같은 저장소의 `shop/` 을 **정적 프론트 + API 백엔드**로 나눕니다.

```
[브라우저]  shop/index.html (또는 src 로 재빌드한 화면)
              │  fetch('/api/...')   ← localStorage 계층을 교체 (§4.8)
              ▼
[Nginx]  shop.example.com  ── /        → 정적 파일
                           ── /api/    → 127.0.0.1:8000 (FastAPI, uvicorn)
                           ── /media/  → /var/lib/mono-atelier/media
              ▼
[FastAPI]  세션·권한·금액 재계산·재고 트랜잭션·토스 승인·메일/SMS 발송
              ▼
[SQLite]  /var/lib/mono-atelier/mono-atelier.db  (schema.sql 21테이블)
```

**끝났다고 판정하는 기준(요약)**
1. 로그인 세션이 `HttpOnly` 쿠키이고 `bcrypt`/`argon2` 해시로 검증된다.
2. `GET /api/products` 응답에 회원·주문·관리자 설정이 **한 글자도** 섞이지 않는다.
3. 결제 금액·쿠폰·포인트·재고가 **서버에서 재계산·트랜잭션**으로 확정되고, 클라이언트가 보낸 `amount` 를 신뢰하지 않는다.
4. 타인의 주문·비밀글 Q&A·회원 목록·관리자 API 접근이 **403/404** 로 막힌다.
5. 시크릿 키가 저장소·브라우저 번들에 **0건**이고 `.env` 에만 있다.
6. §5.2 수용 체크리스트(보안 26항목 + 기능 회귀 40항목)를 모두 통과한다.

### 0.3 절대 하지 말 것

- 시드(회원 이메일·전화·주소·주문)를 **HTML/JS 번들에 다시 인라인**하지 말 것 → §1.4, §2 V1
- `TOSS_SECRET_KEY`·`MAIL_API_KEY`·`SMS_API_KEY`·`SESSION_SECRET` 을 코드/저장소/프론트 응답에 넣지 말 것 → §2 V13
- 클라이언트가 보낸 `amount`·`discount`·`points_used`·`role`·`user_id` 를 **그대로 믿지 말 것** → §2 V7
- 관리자 판정을 **프론트 조건문**에만 두지 말 것 → §2 V4

---

## 1. 현재 상태 (v1.9.16)

### 1.1 파일 지도

| 경로 | 크기 | 역할 | 백엔드 이관 관점 |
|---|---|---|---|
| `shop/index.html` | 1,046,097 B (1,021.6 KB) | **빌드 산출물**. CSS+JS+시드 인라인. 실제 배포되는 화면 | 시드 인라인 제거 대상 (§1.4) |
| `shop/src/app.js` | 754,534 B / 13,076줄 | 화면 렌더 + 도메인 로직 **전부** | **이관의 원본 명세** |
| `shop/src/styles.css` | 219,304 B / 3,559줄 | 스타일 (412px 모바일 최적화, 다크모드 대응) | 변경 없음 |
| `shop/src/index.template.html` | 1,908 B | HTML 껍데기 + `/*__STYLES__*/`·`/*__APP_JS__*/` 자리표시자 + 토스 SDK `<script>` | 변경 없음 |
| `shop/build.py` | 111,390 B | 시드 생성 → `data/*.json`·`schema.sql` → `index.html` 조립 + **개인정보 검사** | 재빌드에 사용 |
| `shop/data/schema.sql` | 27,205 B / 455줄 | SQLite 21테이블 + 뷰 6종 + 인덱스 | **DB 초기화에 그대로 사용** |
| `shop/data/schema-seed.json` | 95,305 B | 21테이블 초기 데이터(JSON) | 시드 적재 |
| `shop/data/build_sqlite.py` | 6,425 B | `schema.sql` + `schema-seed.json` → `mono-atelier.db` | **DB 초기화 명령 (§4.3)** |
| `shop/data/payment_confirm_example.py` | 8,059 B | 토스 승인 + 금액 대조 + 멱등 처리 예제 | `/api/payments/confirm` 구현 시 |
| `shop/data/mono-atelier.db` | 385,024 B | 미리 빌드된 SQLite (편의용) | 없으면 §4.3으로 생성 |
| `shop/assets/*.webp` | 37개 | 상품/히어로 이미지 | 정적 서빙 |
| `shop/README.md` | — | 프론트 기능 문서(v1.2~v1.9.16 변경 이력) | 참고용 |
| `shop/BACKEND_HANDOFF.md` | — | **이 문서** | — |

**`shop/` 에 없는 것**: `tests/`(E2E·스크린샷 3MB+), `downloads/fashion-shop-preview.html`(단일 파일 미리보기 3.2MB). 필요하면 저장소 밖 원본(`fashion-shop/tests/`)에서만 쓰고, **공개 저장소에는 올리지 않습니다.**

**빌드 재현성 검증(2026-11-28 실측)**: `shop/` 에서 `python3 build.py` 실행 → `index.html`·`schema.sql`·`schema-seed.json` 이 **커밋본과 바이트 단위로 동일**(`git diff` 0). 즉 `src/` 와 배포본은 어긋나지 않았습니다. 빌드 로그의 개인정보 검사도 `ok (실명·연락처·실주소 0건)`.

### 1.2 빌드 파이프라인

```
build.py
 ├─ 시드 파이썬 리터럴(users·products·orders·reviews·qnas …) → data/schema-seed.json
 ├─ 같은 파일 안 SCHEMA_SQL 문자열 → data/schema.sql, mono-atelier.db
 └─ src/index.template.html
      ├─ /*__STYLES__*/  ← src/styles.css
      └─ /*__APP_JS__*/  ← src/app.js 에서
             __SEED__            ← schema-seed.json 한 줄 압축 JSON   ← ★ 클라이언트 시드
             __EMBEDDED_IMAGES__ ← {} (index.html) / 이미지 base64 (preview)
             __APP_VERSION__     ← '1.9.16'
```

- `APP_VERSION = "1.9.16"` (build.py 상단), `schema_version = 14` (`seed.meta`)
- build.py 는 마지막에 산출물(`schema-seed.json`·`index.html`·preview)을 검사하고 걸리면 **빌드를 실패**시킵니다. 검사 항목: ① `MONO_PRIVATE_PATTERNS` 환경변수로 주입한 금지 문자열(실명·연락처·실주소 — **저장소에 값을 두지 않음**) ② 주민등록번호 패턴 ③ 예시값(`010-0000-0000`)이 아닌 휴대전화 번호. 시드의 회원 이름은 `홍길동`, 연락처는 `010-0000-0000`, 주소는 `서울특별시 송파구 올림픽로 300 101동 1203호` 같은 **예시값**입니다.
- **서버로 옮긴 뒤**: `build.py` 는 "시드 JSON + 스키마" 생성기로만 쓰고, `index.html` 조립 시 `__SEED__` 를 **`null` 또는 `{meta:{}}`** 로 바꿔 인라인을 없앱니다(§2 V1). `app.js` 는 시드가 없으면 부팅 시 API에서 받아오도록 §4.8 어댑터로 교체합니다.

### 1.3 데이터 모델 — 21개 테이블 (`STORE_TABLES`, app.js 44–66줄)

JSON(`STORE_TABLES`) ↔ SQLite(`schema.sql`)는 **1:1** 입니다. 화면의 「데이터 관리 > 테이블 현황」과 「JSON 내보내기」도 같은 레지스트리를 읽습니다.

| # | 테이블 | 한국어 라벨 | 시드 행 | 핵심 컬럼 |
|---|---|---|---|---|
| 1 | `users` | 회원 | 5 | email UNIQUE · password_hash · role(customer/admin) · grade(NORMAL/SILVER/GOLD/VIP) · points · postcode |
| 2 | `categories` | 카테고리 | 5 | label · en · sort_order · size_codes(JSON) · is_active |
| 3 | `products` | 상품 | 13 | product_code(MA-0001) UNIQUE · category FK · price · original_price · badge · image · model_info · free_shipping_threshold · is_active |
| 4 | `product_images` | 상품 갤러리 | 39 | product_id FK · image · alt · sort_order · UNIQUE(product_id, image) |
| 5 | `product_variants` | 상품 옵션·재고 | 88 | product_id · color · color_hex · size · stock · sku UNIQUE · UNIQUE(product_id,color,size) |
| 6 | `cart_items` | 장바구니 | 0 | user_id · variant_id · quantity · UNIQUE(user_id, variant_id) |
| 7 | `orders` | 주문 | 21 | order_no UNIQUE · status · total_amount · shipping_fee · coupon_code · discount_amount · points_used · postcode · recipient_* · shipping_address · payment_method · payment_provider · **payment_key** · payment_mode |
| 8 | `order_items` | 주문 항목 | 22 | order_id · variant_id · product_name(스냅샷) · color · size · unit_price · quantity · confirmed_at · confirm_points · photo_bonus · photo_bonus_at · review_attempts(0~2) · rewrite_used |
| 9 | `order_claims` | 교환/반품 | 2 | order_id **UNIQUE** · claim_type · reason_category · shipping_fee · payment_status(free/paid/pending) · payment_key · exchange_option · status · **stock_restored** · admin_memo |
| 10 | `coupons` | 쿠폰 | 4 | code UNIQUE · discount_type(percent/fixed) · discount_value · min_order_amount · expires_at · is_active · target_grades(JSON) · target_categories(JSON) · target_badges(JSON) |
| 11 | `coupon_targets` | 쿠폰 발급 대상 | 1 | coupon_id · user_id · UNIQUE(coupon_id,user_id) — **행 없으면 전체 공용** |
| 12 | `product_reviews` | 상품 리뷰 | 14 | product_id · user_id · **order_item_id** · attempt(1~2) · rating(1~5) · content · media(JSON) · status(published/rejected) · rejected_reason · reclaimed_points · UNIQUE(order_item_id, attempt) |
| 13 | `product_qnas` | 상품 Q&A | 15 | product_id · user_id · user_name(마스킹) · qna_type · title · content · **is_secret** · answer · answered_by · status |
| 14 | `review_votes` | 리뷰 추천/비추천 | 21 | review_id · user_id · vote(up/down) · UNIQUE(review_id,user_id) |
| 15 | `point_policies` | 포인트 정책 | 4 | grade PK · confirm_rate(%) · photo_rate(%) |
| 16 | `point_logs` | 포인트 내역 | 4 | user_id · type · amount(±) · base_amount · rate · order_id · order_item_id · review_id · description |
| 17 | `faqs` | FAQ | 8 | category · question · answer · sort_order · is_active |
| 18 | `sms_logs` | SMS 로그 | 1 | order_id · phone · message · kind · status(test/sent/failed/skipped) · mode · sender |
| 19 | `dispatch_logs` | 발송 로그 | 3 | channel(sms/email) · **`to_addr`** · kind · summary · status(test/sent/blocked/failed) · mode · order_id |
| 20 | `site_settings` | 사이트 설정 | 1 | **단일 행(`id='default'`)**, 45컬럼 — 히어로/스토리/타이틀/푸터/사업자/배지/사이트미디어/등급기준/알림모드 |
| 21 | `help_topics` | HELP 항목 | 3 | title · body · sort_order |

**뷰 6종**: `v_product_stock`, `v_order_summary`, `v_order_claims`, `v_coupon_targets`, `v_member_points`, `v_product_reviews`

**실측 검증(현재 `mono-atelier.db`)**: `PRAGMA integrity_check` → `ok`, `PRAGMA foreign_key_check` → `[]`(0건).

#### JSON ↔ SQLite 변환 시 주의(실측 차이)

| 항목 | JSON(앱) | SQLite | 처리 |
|---|---|---|---|
| 상품 갤러리 | `products[].images` 배열(대표 포함 3장) | `product_images` 행 | API 응답에서 조합해 `images` 로 내려주고, 저장은 `product_images` 에 |
| 쿠폰 발급 대상 | `coupons[].target_user_ids` 배열 | `coupon_targets` 행 | 저장 시 행으로 분해 |
| 발송 로그 수신자 | `dispatch_logs[].to` | `dispatch_logs.to_addr` | SQL 예약어 회피. `build_sqlite.py` 가 alias 처리 |
| `users.address_detail` | 회원가입 시 상세주소를 **별도 필드**로 보관하고 `address` 에 합쳐 저장 | **컬럼 없음** | 서버에서 `ALTER TABLE users ADD COLUMN address_detail TEXT NOT NULL DEFAULT ''` 로 **추가 권장** (§4.3) |
| 불리언 | `true/false` · `0/1` 혼용 | `INTEGER CHECK IN (0,1)` | 서버에서 0/1 정규화 |
| 시각 | ISO-8601 `+09:00` | `TEXT` | `Asia/Seoul` 고정, 문자열 그대로 저장 |
| 금액 | 원 단위 정수 | `INTEGER` | 소수점 없음. `1P = 1원` |
| `cart_items` | 시드 0건(회원별 실데이터) | 동일 | 테스트 시 장바구니는 직접 담아 확인 |

### 1.4 현재 "DB 계층" = localStorage

| 키 | 값 | 쓰는 곳 |
|---|---|---|
| `mono_atelier_db_v1` | **21테이블 + meta 전체 JSON** | `loadDB()` 654 · `save()` 848 · `migrateDB()` 664 · `mergeSeedRows()` 824 |
| `mono_atelier_session_v1` | `{userId, logged_in_at}` | `loadSession()` 855 · `saveSession()` 859 — **세션 조작 가능** |
| `mono_atelier_pending_checkout_v1` | 결제 대기 주문(주문번호·금액·상품) | `savePending()` 2010 · `loadPending()` 2013 — **금액 조작 가능** |
| `mono_atelier_pending_claim_v1` | 교환/반품 대기(신청번호·배송비) | `savePendingClaim()` 1167 |
| `mono_atelier_payment_customer_key_v1` | 토스 `customerKey`(무작위 22자+) | `customerKey()` 2023 |
| `mono_atelier_payment_config_v1` | 관리자 화면에서 저장한 결제 설정 | `loadPaymentConfig()` 163 · `savePaymentConfig()` 182 |
| `mono_atelier_store_view_v1` | 썸네일/목록 보기 | 순수 UI |

**부팅 순서 (`boot()` 12824)**: `loadDB()` → 없으면 `clone(SEED)` → `migrateDB/마이그레이션 3종` → `loadSession()` → `loadPaymentConfig()` → `applyHashRoute()` → `renderAll()` → `handlePaymentReturn()` → `handleClaimReturn()` → `syncRoute()`.

**시드 인라인 위치**: `var SEED = __SEED__;` (app.js **8줄**) ← build.py 가 `schema-seed.json` 전체를 압축 JSON으로 치환. 즉 **지금 배포본에는 회원 5명의 이메일·연락처·주소, 주문 21건, 리뷰·Q&A 29건이 전부 들어 있습니다**(예시값이지만 "타인 데이터가 클라이언트에 있다"는 구조 자체가 문제). → §2 V1

### 1.5 인증·세션 현재 구현 (서버에서 전면 교체)

| 함수 | 줄 | 현재 동작 | 서버에서 |
|---|---|---|---|
| `sha256Hex()` / `hashPw()` | 609 / 646 | `sha256('mono-atelier$' + pw)` — **salt 없음**, 클라이언트 계산 | `bcrypt`(cost 12) 또는 `argon2id`. pepper는 서버 `.env` |
| `login()` | 1768 | `db.users` 에서 email 비교 + 해시 비교 → `session={userId}` 저장 | 이메일 정규화(lower) → 해시 검증 → **세션 레코드 발급 + HttpOnly 쿠키** |
| `signup()` | 1777 | 이메일 형식 → 비밀번호 정책 → **클라이언트 OTP 검증 상태** → 중복 → `users` push | 서버 OTP 토큰 검증, 비밀번호 정책 재검증, UNIQUE 위반 처리 |
| `passwordCheckOf()` | 1838 | 8자+ · 대/소문자 · 숫자 · 특수문자 · 연속숫자 3자리 금지 | **동일 규칙 서버 강제** |
| `currentUser()` | 865 | `session.userId` → `db.users` 조회 | 세션 → `users` 조인 |
| `isAdmin()` | 869 | `user.role === 'admin'` (클라이언트 판정) | **모든 관리자 엔드포인트에서 재검증** |
| `applyHashRoute()` | 1575 | `#/admin/...` 은 `isAdmin()` 일 때만 (화면 가드일 뿐) | 서버가 403 |
| `logout()` | 1890 | 세션 삭제 | 세션 레코드 삭제 + 쿠키 만료 |

**데모 계정**(시드, 테스트용): `demo@mono.kr / demo1234` (GOLD·4,725P) · `admin@mono.kr / admin1234` (admin) · `member1~3@mono.kr / demo1234` (SILVER/NORMAL/SILVER)

### 1.6 도메인별 함수 지도 (줄 번호 = v1.9.16)

`app.js` 는 IIFE 안에 **도메인 순서대로** 쌓여 있습니다. 서버로 옮길 때 이 순서대로 옮기면 누락이 적습니다.

| 도메인 | 함수(줄) | 비고 |
|---|---|---|
| 설정/유틸 | `normalizePaymentConfig` 149 · `esc` 552 · `won` 557 · `nowISO` 570 · `newId` 596 | `esc()` 는 XSS 방어의 유일한 수단(§2 V12) |
| 카테고리 | `categories` 205 · `storeCategories` 212 · `sizeCodesOf` 476 | 숨김 카테고리는 스토어에서만 제외 |
| 등급 | `GRADES` 216 · `gradeOf` 223 | NORMAL/SILVER/GOLD/VIP |
| 색상 | `normalizeHex` 258 · `nearestColorName` 324 · `sampleImageColors` 367 | 이미지에서 색 추출(클라이언트 canvas) |
| 인증 | `login` 1768 · `signup` 1777 · `logout` 1890 · `openAuth` 9895 | |
| 상품 조회 | `productById` 872 · `variantsOf` 899 · `stockOf` 902 · `colorsOf` 905 · `sizesOf` 918 · `findVariant` 923 · `productImages` 956 · `freeShipThresholdOf` 968 | |
| 상품 저장 | `saveProduct` 2533 · `toggleProductActive` 2646 · `soldoutProduct` 2653 · `nextProductCode` 877 · `productCodeTaken` 885 | 관리자 전용 |
| 장바구니 | `cartRows` 1334 · `addToCart` 1911 · `setCartQty` 1933 · `removeCartItem` 1947 · `removeCartItems` 1955 · `removeSelectedCartItems` 1970 | |
| 금액 | `totalsOf` 1352 · `shippingOf` 981 · `couponEligibleBase` 1238 · `couponDiscount` 1288 · `couponCheck` 1295 · `pointUseApplied` 5695 | **§1.7.1 숫자 그대로 재현** |
| 주문 | `makeOrderNo` 1986 · `buildPending` 2055 · `stockProblem` 2045 · `finalizeOrder` 2085 · `cancelOrder` 2431 · `updateOrderStatus` 2452 · `applyOrderStatus` 2463 · `bulkUpdateOrderStatus` 2484 | |
| 결제 | `PAYMENT_CONFIG` 131 · `tossAvailable` 2001 · `requestTossPayment` 2208 · `confirmPayment` 2316 · `handlePaymentReturn` 2346 · `customerKey` 2023 | 승인은 서버로 |
| 교환/반품 | `claimFeeOf` 1011 · `claimBlockReason` 1020 · `buildClaim` 1057 · `finalizeClaim` 1096 · `updateClaimStatus` 1131 · `bulkUpdateClaimStatus` 1150 · `requestTossClaimPayment` 2252 · `handleClaimReturn` 2384 | |
| 쿠폰 | `couponForUser` 1259 · `couponsForUser` 1281 · `couponUsable` 1318 · `applyCouponCode` 5562 · `createCoupon` 8330 · `updateCoupon` 8348 · `toggleCoupon` 8371 | |
| 포인트 | `pointPolicyMap` 3586 · `pointPolicyOf` 3600 · `userPoints` 3607 · `addPointLog` 3623 · `confirmOrderItem` 3677 · `savePointPolicies` 3637 · `adjustMemberPoints` 7808 | |
| 리뷰 | `addReview` 3872 · `updateReview` 3948 · `rejectReview` 3981 · `approveReview` 7900 · `bulkReclaimReviews` 7936 · `toggleReviewVote` 3769 · `reviewStats` 3740 · `reviewAttemptsOf` 3716 · `reviewRewriteAvailable` 3723 | |
| Q&A | `submitQna` 4931 · `answerQna` 4957 · `deleteQna` 4971 · `qnaCanRead` 4838 · `productQnas` 4831 | 비밀글 필터가 **서버로** |
| FAQ/HELP | `saveFaqs` 4122 · `saveFaqItem` 7089 · `deleteFaqItems` 7139 · `saveFaqCategories` 4061 · `saveHelpTopics` 3214 | |
| 사이트 설정 | `siteSettings` 3057 · `saveSiteSettings` 3177 · `addSiteMedia` 6696 · `removeSiteMedia` 6712 · `selectSiteMedia` 6727 · `saveGradeRulesFromForm` 7632 · `applyMembershipTargets` 7658 | |
| 알림 | `notifySettings` 3236 · `saveNotifySettings` 3253 · `sendEmailCode` 3287 · `verifyEmailCode` 3324 · `emailCooldownLeft` 3378 · `dispatchAnomalies` 3394 · `sendOrderSms` 3420 · `addDispatchLog` 3359 | 서버 발송 + 레이트리밋 |
| 관리자 목록 | `adminPagerInfo` 6442 · `adminSeqCellHTML` 6456 · `adminOrderListOf` 9304 · `adminClaimListOf` 8806 · `adminReviewList` 7287 · `adminQnaList` 7371 · `memberList` 7572 · `adminProductList` 6571 | **10건 페이징 + 순번** |
| 매출 | `revenueBuckets` 9067 · `revenueSummaryHTML` 9107 · `revenueTrendChartHTML` 9135 · `revenueDetailTableHTML` 9196 | 취소 제외 실매출 |
| 데이터 관리 | `storeTableSummary` 2863 · `exportPayload` 2663 · `resetDB` 2694 · `runIntegrity` 2705 | 내보내기=개인정보 → 관리자 전용 |
| 이벤트 위임 | `document click` **10430** · `change` **12522** · `__MONO__` 12849 | `data-action` 195종 → 화면→API 호출 지점 |

### 1.7 서버에서 그대로 재현해야 하는 비즈니스 규칙

#### 1.7.1 금액 계산 (`totalsOf` 1352)

```
subtotal = Σ (products.price × cart_items.quantity)            # 쿠폰 전 상품 합계
base     = 쿠폰 조건이 없으면 subtotal
           조건이 있으면 "카테고리 AND 뱃지"를 모두 만족하는 상품 금액만 합산   # couponEligibleBase
discount = percent ? floor(base × discount_value / 100)
                    : min(discount_value, base)                 # base 를 넘지 않음
shipping = 배송비 규칙(아래)
total    = max(0, subtotal − discount + shipping)
points_used = min(요청값, 보유 포인트, total)                      # pointUseApplied
amount   = max(0, total − points_used)                          # 토스에 청구할 금액
```

- 상품 판매가는 `products.price`(정가 `original_price` 는 표시용 취소선일 뿐 계산에 쓰지 않음).
- **할인은 상품 금액에만** 적용되고 배송비에는 적용되지 않습니다.

#### 1.7.2 배송비 (`shippingOf` 981)

- 상품별 무료배송 기준 `free_shipping_threshold`: `NULL` → 스토어 기본 **100,000원**, `0` → **무조건 무료**, `N` → 그 상품 합계가 N원 이상이면 무료.
- **상품별로 묶어** 판정: 한 주문 안에 기준 미달 상품이 하나라도 있으면 배송비 **3,000원 1회**. 모든 상품군이 기준을 넘으면 **0원**.
- 표시용 `remaining` = 미달 상품군 중 "기준까지 가장 적게 남은 금액".

#### 1.7.3 쿠폰 (`couponCheck` 1295 · `couponForUser` 1259 · `couponEligibleBase` 1238)

검증은 **AND** 입니다. 하나라도 어긋나면 사유 문자열을 그대로 사용자에게 보여줍니다.

| 조건 | 판정 |
|---|---|
| 존재 | 코드 일치(대소문자 무시) |
| 활성 | `is_active = 1` — 아니면 "사용이 중지된 쿠폰입니다." |
| 기간 | `expires_at` NULL 이면 무기한, 지났으면 "사용 기간이 만료된 쿠폰입니다." |
| 발급 대상 | `coupon_targets` 행이 있으면 **그 회원만**, `target_grades` 가 있으면 **그 등급만**, 둘 다 있으면 **둘 다 만족**. 없으면 전체 공용 |
| 최소 주문금액 | `subtotal ≥ min_order_amount` |
| 상품 조건 | `target_categories`·`target_badges` 가 있으면 **모두 만족하는 상품 금액 > 0** 이어야 함. 0이면 "사용 조건(…)에 해당하는 상품이 장바구니에 없습니다." |

> **설계 공백(서버에서 보완 권장)**: 현재 스키마에는 **쿠폰 사용 이력 테이블이 없습니다.** `orders.coupon_code` 로 흔적만 남아 ① 같은 쿠폰의 **재사용/다중 사용** ② 회원별 1회 제한 을 표현할 수 없습니다. → `coupon_redemptions(id, coupon_id, user_id, order_id UNIQUE, created_at)` 를 추가하고, **결제 확정 트랜잭션에서 `UNIQUE(coupon_id, user_id, order_id)` 로 중복 사용을 차단**하세요. (요구사항에 없던 신규 테이블이므로 기본 정책은 "1인 1회" 로 두고, 관리자가 `reusable` 플래그를 켤 수 있게 하는 것을 권장)

#### 1.7.4 포인트 (`point_policies` · `point_logs` · `users.points`)

| 이벤트 | 시점/조건 | 계산 |
|---|---|---|
| 구매확정 (`confirmOrderItem` 3677) | 주문 `delivered` + `order_items.confirmed_at IS NULL` + 진행 중 클레임 없음 | `floor(상품 실결제금액 × confirm_rate%)`. `confirmed_at` 으로 **1회만** |
| 상품 실결제금액 (`orderItemNetAmount` 3663) | — | `상품금액 − 주문할인 × (상품금액 / 주문 상품합계)` (배송비 제외, 반올림) |
| 포토·영상 리뷰 (`addReview` 3872) | 리뷰에 media 있고 `order_items.photo_bonus = 0` | `floor(실결제금액 × photo_rate%)`. 주문항목당 **1회**(재작성 포함 중복 지급 없음) |
| 사용 (`finalizeOrder` 2085) | 결제 확정 | `−points_used` (`use`) |
| 환급 (`applyOrderStatus` 2463) | **취소로 전이할 때 1회** | `+points_used` (`refund`) |
| 리뷰 반려 회수 (`rejectReview` 3981) | 관리자 반려 | `−min(보너스, 보유 포인트)` (`review_reclaim`), `product_reviews.reclaimed_points` 에 누적 |
| 관리자 조정 (`adjustMemberPoints` 7808) | 사유 필수 | `±amount` (`adjust`) |

- **기본 적립률**(`DEFAULT_POINT_POLICIES` 70): 구매확정 NORMAL 0.5 / SILVER 0.7 / GOLD 1.0 / VIP 1.5 %, 포토·영상 1.0 / 1.2 / 1.5 / 2.0 %. 상한 10%.
- `users.points` 는 **`point_logs.amount` 합계와 항상 일치**해야 합니다(`v_member_points` 뷰로 검증 가능). 서버에서는 `users.points` 를 **캐시로만** 쓰고 원장 합계로 재계산하세요.

#### 1.7.5 재고 (`product_variants.stock`)

| 전이 | 동작 | 중복 방지 |
|---|---|---|
| 주문 확정 (`finalizeOrder` 2085) | `stock -= quantity` (품절 판정 `stockProblem` 2045) | `orders.order_no` UNIQUE + `payment_key` UNIQUE (§2 V7) |
| 주문 취소 (고객 `cancelOrder` 2431 / 관리자 `applyOrderStatus` 2463) | `stock += quantity` | 상태가 `cancelled` 면 재전이 금지 → **2회 복구 없음** |
| 반품 완료 (`updateClaimStatus` 1131) | `stock += 수량` | `order_claims.stock_restored = 1` 플래그로 **1회만** |
| 관리자 품절 처리 (`soldoutProduct` 2653) | 해당 상품 모든 옵션 `stock = 0` | — |

#### 1.7.6 교환/반품 (`order_claims`)

| 구분 | 사유 | 배송비 | `payment_status` |
|---|---|---|---|
| 판매자 귀책 | `defect`(제품 하자·파손), `wrong_item`(오배송) | **0원** | `free` |
| 고객 귀책 | `change_of_mind`(단순 변심) | 반품 **3,000원** | `paid`(결제 후 접수) |
| 고객 귀책 | `size_color`(사이즈·색상 변경) | 교환 **6,000원**(왕복) | `paid` |

- 신청 가능: 주문 상태 `shipping`·`delivered` (`claimBlockReason` 1020). 배송 전은 **주문 취소**로 처리. 이미 클레임이 있으면 차단(주문당 1건, DB UNIQUE).
- 상태: `requested`(접수됨) → `approved`(수거중/승인) → `completed`(완료) / `rejected`(반려).
- 교환은 `exchange_option`(예: `카멜 / L`)을 저장하고 **재고 있는 옵션만** 선택 가능.
- 관리자 처리 메모 `admin_memo` 는 **고객 화면·고객 API 응답에 절대 포함하지 않습니다.**

#### 1.7.7 리뷰 (`addReview` 3872 · `rejectReview` 3981)

- 작성 자격: **배송완료(`delivered`) + 구매확정(`confirmed_at`) + 진행 중 클레임 없음 + 본인 주문항목**.
- 주문항목당 리뷰 **차수 1~2**: 최초 1회, 반려되면 **1회 재작성**(`attempt=2`, `rewrite_used=1`), 2차 반려는 최종 차단.
- 첨부: 사진·동영상 최대 **6개**, 동영상 **4MB 이하**, 사진은 긴 변 900px JPEG 로 축소(서버에서는 원본 저장 + 썸네일 권장).
- 표시 이름은 **마스킹**(`maskUserName` 3653: 첫 글자 + `*`).
- 추천/비추천: 리뷰당 회원 1명 **1표**(`review_votes` UNIQUE), **본인 리뷰 투표 불가**(서버 차단), 선택/취소/전환 가능. 정렬 `top` = 추천−비추천 내림차순, 동률 최신순.
- 페이지당 **5건**.

#### 1.7.8 Q&A (`submitQna` 4931 · `qnaCanRead` 4838)

- 로그인 회원만 작성. 유형 `product`·`delivery`·`claim`·`etc`. 제목 **2~60자**, 내용 **≤500자**, 답변 **≤1000자**.
- `is_secret = 1` 이면 **작성자 본인과 관리자만** 제목·본문·답변을 볼 수 있고, 다른 사람에게는 제목도 `🔒 비밀글입니다` 로 마스킹.
- `answer` 가 비면 `pending`(미답변), 채우면 `answered`. 페이지당 **5건**.

#### 1.7.9 이메일 인증 / 발송 제한 (`sendEmailCode` 3287)

- 6자리 코드, **유효 5분**(`EMAIL_CODE_TTL` 3235), **같은 이메일 60초 쿨다운**(차단 시도도 `dispatch_logs` 에 `blocked` 로 기록).
- 테스트 모드(`email_auth_mode='test'`)에서는 **화면에 코드가 표시**됩니다(내부망 데모용). **운영에서는 코드를 응답에 넣지 마세요.**
- 이상 징후 감지(`dispatchAnomalies` 3394): 같은 수신자 10분 내 **3회 이상**, 전체 5분 내 **12건 이상** → 관리자 화면 경고.
- 인증번호 자체는 로그에 남기지 않습니다(`summary` 만 저장).

#### 1.7.10 멤버십 등급 (`membershipTargets` 7623 · `applyMembershipTargets` 7658)

- 기준 기간 **최근 6개월**(`member_grade_rules.months`), 최근 구매액(취소 제외) 임계값 **0 / 200,000 / 400,000 / 800,000원** (일반/실버/골드/VIP).
- 관리자 「대상자 조회」 → 「일괄 자동 적용」. **관리자 계정은 제외**. 임계값은 **오름차순**이어야 저장됨.

#### 1.7.11 상태값 사전

| 구분 | 값 (한국어 라벨) |
|---|---|
| 주문 `orders.status` | `paid` 결제완료 · `preparing` 배송준비 · `shipping` 배송중 · `delivered` 배송완료 · `cancelled` 취소됨 |
| 클레임 `order_claims.status` | `requested` 접수됨 · `approved` 수거중/승인 · `completed` 완료 · `rejected` 반려 |
| 클레임 유형/사유 | `return` 반품 · `exchange` 교환 / `defect` · `wrong_item` · `change_of_mind` · `size_color` |
| 결제수단 | `card` 신용카드 · `easypay` 간편결제 · `bank` 무통장입금 |
| 결제 주체/모드 | `payment_provider`: `demo`·`tosspayments` / `payment_mode`: `demo`·`demo-fallback`·`test-client`·`server` |
| 리뷰 | `published` 게시중 · `rejected` 반려 |
| 포인트 유형 | `signup`·`confirm`·`photo_review`·`review`·`use`·`refund`·`adjust`·`review_reclaim` |
| 발송 로그 | `test`·`sent`·`blocked`·`failed` (SMS 는 `skipped` 포함) |

### 1.8 관리자 콘솔 구조 (14탭) — 프론트를 그대로 두려면 필요한 API

`products` 상품 · `orders` 주문 · `revenue` 매출 · `claims` 반품/교환 · `coupons` 쿠폰 · `points` 포인트 · `members` 회원 · `reviews` 리뷰 · `qnas` Q&A · `categories` 코드 관리(카테고리/뱃지) · `site` 메인/사이트 · `faqs` FAQ · `logs` 발송 로그 · `data` 데이터 관리

공통 UI 규칙: 목록형 표는 **10건 페이징 + 연속 순번(`번호`)**, 검색·필터가 바뀌면 1페이지로 리셋, 마지막 페이지가 비면 자동 보정. 서버는 **`page`·`limit`·`total`** 만 정확히 주면 됩니다(`adminPagerInfo` 6442).

---

## 2. 보안 — 반드시 해결해야 할 취약점과 서버 구현 원칙

> **전제**: 이 앱은 "화면이 곧 서버"인 구조라서 아래 V1~V20 이 **모두 실재**합니다. 서버를 붙여도 **클라이언트 계산을 그대로 신뢰하면 취약점은 그대로 남습니다.** 각 항목의 "서버 대책"이 곧 수용 기준입니다.

### 2.0 위협 모델 요약

| # | 취약점 | 현재 코드 근거 | 서버 대책(요약) |
|---|---|---|---|
| V1 | **클라이언트 시드 인라인** — 회원·주문·리뷰·Q&A 전체가 배포 HTML에 포함 | `app.js:8 var SEED = __SEED__` / `build.py` 치환 | 시드 인라인 제거, API로만 |
| V2 | **권한별 데이터 미분리** — localStorage 전체를 누구나 열람 | `loadDB()` 654, `getDB()` 12851 | 엔드포인트별 화이트리스트 응답 |
| V3 | **타인 주문·회원 목록 노출** | `orders`·`users` 전부 클라이언트에 존재 | 소유권·관리자 검사(V16) |
| V4 | **관리자 기능 클라이언트 게이트** — `isAdmin()` 만 확인, 함수는 브라우저에서 실행 | `applyHashRoute` 1591, `saveProduct` 2533 등 | 모든 관리자 API에서 `role='admin'` 재검증 |
| V5 | **비밀번호 해시 취약** — 무salt SHA-256 + 고정 pepper, 클라이언트 계산 | `hashPw()` 646 | bcrypt/argon2 + 서버 계산 |
| V6 | **세션 위조** — `{userId}` 를 localStorage에 저장 | `saveSession()` 859 | 서명된 HttpOnly 세션 쿠키 |
| V7 | **금액 신뢰** — 클라이언트가 보낸 amount 로 승인, 서버 검증 없음 | `confirmPayment()` 2316 (confirmApiUrl 없으면 "테스트 승인") | 서버 재계산 + DB 금액 대조 + 멱등 |
| V8 | **재고 경쟁/음수** — 확인과 차감이 분리, 트랜잭션 없음 | `stockProblem` 2045 → `finalizeOrder` 2085 | `BEGIN IMMEDIATE` + 조건부 UPDATE |
| V9 | **포인트 조작** — `users.points` 를 클라이언트가 수정 | `addPointLog` 3623 | 원장 기반, 서버만 기록 |
| V10 | **쿠폰 재사용** — 사용 이력 테이블 없음 | §1.7.3 | `coupon_redemptions` + 트랜잭션 |
| V11 | **이미지 Data URL** — 업로드가 localStorage(5MB)에 저장, 서버 검증 없음 | `resizeImageFile` 9801, `handleImageUploads` 9830 | 서버 저장 + MIME/크기/시그니처 검증 |
| V12 | **XSS** — `innerHTML` 광범위, 사용자 입력이 속성·HTML에 삽입 | `esc()` 552, 렌더 함수 전반 | 서버 저장 시 정규화 + CSP + `textContent` 원칙 |
| V13 | **발송 API 키 노출** — 관리자 설정의 API URL을 브라우저가 직접 호출 | `sendEmailCode` 3287, `sendOrderSms` 3420 | 키는 `.env`, 서버 발송 |
| V14 | **OTP 우회** — 코드·검증 상태가 클라이언트 메모리 | `verifyEmailCode` 3324, `emailVerifiedFor` 3334 | 서버 저장(해시)·시도 제한·1회 토큰 |
| V15 | **CSRF** — 쿠키 세션 전환 시 위험 | (현재 세션 없음) | SameSite=Lax + CSRF 토큰 or SameSite=Strict + Origin 검사 |
| V16 | **IDOR** — `order_id`·`claim_id`·`review_id`·`qna_id`·`uid` 를 파라미터로 받음 | `orderById` 1004, `claimById` 1007 등 | 모든 조회·변경에 소유권 검사 |
| V17 | **민감 필드 노출** — 관리자 메모·발송 로그·회원 연락처 | `admin_memo`, `dispatch_logs.to_addr` | 관리자 전용 필드 분리 응답 |
| V18 | **무차별 대입·과다 요청** | 로그인/OTP/발송 제한 없음(쿨다운만) | IP·계정 레이트리밋, 잠금, CAPTCHA(필요 시) |
| V19 | **결제 취소 미구현** — 주문 취소가 DB 상태만 변경 | `cancelOrder` 2431 | 토스 취소 API + 부분취소 정책 |
| V20 | **개인정보 보관·감사 부재** | localStorage | 암호화/최소수집/보존기간/감사 로그 |

### 2.1 V1 — 클라이언트 시드 인라인 제거

- **현재**: `index.html` 안에 `SEED` 전체(회원 5명·주문 21건·리뷰/Q&A 29건·사이트 설정)가 문자열로 들어 있습니다. 소스 보기만으로 전체 DB를 얻습니다.
- **서버 대책**
  1. `build.py` 산출 시 `__SEED__` 를 `{"meta":{}}` 로 치환하는 **프로덕션 빌드 모드**(`--prod`)를 추가합니다.
  2. 프론트는 부팅 시 `/api/bootstrap` 으로 **공개 데이터만**(카테고리·상품·사이트 설정·FAQ·HELP) 받습니다.
  3. **`users`·`orders`·`order_items`·`point_logs`·`sms_logs`·`dispatch_logs`·`coupon_targets` 는 어떤 공개 응답에도 넣지 않습니다.**
- **수용**: `curl https://<host>/ | grep -c "demo@mono.kr"` → **0**

### 2.2 V2/V3 — 응답 화이트리스트 (권한별 필터링)

| 대상 | 비로그인 | 본인 | 관리자 |
|---|---|---|---|
| 상품·카테고리·FAQ·HELP·사이트 공개 설정 | 전체 | 전체 | 전체 |
| 리뷰(게시중) | 조회 | 조회 | 조회 |
| **비밀글 Q&A** | 제목/본문/답변 **미포함** | 전체 | 전체 |
| 공개글 Q&A | 제목·본문·답변 | 전체 | 전체 |
| 회원 정보 | **없음** | 본인 것만 | 목록(마스킹 없음) |
| 주문·주문항목 | **없음** | 본인 것만 | 전체 |
| 쿠폰 | **없음** | 사용 가능한 것만 | 전체 |
| `admin_memo`·발송 로그·`payment_key` | 절대 금지 | 본인 주문의 `payment_key` 도 **마스킹/생략 권장** | 필요 시 |

- **반드시 지킬 것**: "필터링은 서버에서 응답을 만들 때" 합니다. 프론트에서 숨기는 것은 보안이 아닙니다.
- **금지**: `GET /api/users` 같은 "전체 회원" 엔드포인트를 고객 권한에 열지 마세요. 관리자 목록은 `/api/admin/members` 로 분리하고 `role` 검사 + 검색·페이징 필수.

### 2.3 V4 — 관리자 권한은 매 요청마다 서버에서 판정

```python
# deps.py 예
def require_admin(user: User = Depends(current_user)) -> User:
    if user is None or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="관리자만 접근할 수 있습니다.")
    return user
```

- **모든** `POST/PUT/PATCH/DELETE /api/admin/*`, `/api/products`(쓰기), `/api/codes/*`(쓰기), `/api/site`(쓰기)에 `Depends(require_admin)`.
- 화면의 `#/admin` 가드(`applyHashRoute` 1591)는 **UX용**일 뿐입니다. 관리자 API는 **역할이 customer 인 세션으로 호출하면 403** 이어야 합니다(§5.2 S-4).
- 관리자 계정 스스로 등급/권한을 낮춰 잠기는 상황을 막기 위해 **마지막 관리자 강등 차단**을 권장합니다.

### 2.4 V5/V6 — 비밀번호·세션

| 항목 | 규칙 |
|---|---|
| 해시 | `bcrypt` cost ≥ 12 또는 `argon2id` (`memory=64MB, time=3, parallelism=2`). **salt 자동 포함**. 기존 `sha256` 시드는 **첫 로그인 시 자동 재해시**(마이그레이션) |
| 정책 | 8자 이상 + 영문 대/소문자 + 숫자 + 특수문자 + 연속숫자 3자리 금지 (`passwordCheckOf` 1838 과 동일). **서버에서 강제** |
| 비교 | `hmac.compare_digest` 계열 상수시간 비교 |
| 세션 | 서버 세션 테이블(`sessions(id, user_id, csrf_token, created_at, expires_at, ip, ua)`), 쿠키 `HttpOnly; Secure; SameSite=Lax; Path=/` |
| 만료/갱신 | 기본 72시간(`SESSION_TTL_HOURS`), 로그인 시 기존 세션 회전(id 재발급) |
| 로그아웃 | 세션 행 삭제 + 쿠키 만료 |
| 로그인 실패 | 5회/5분 → 429, 계정 잠금은 관리자 해제. **응답 메시지는 "이메일 또는 비밀번호가 올바르지 않습니다"로 통일**(현재는 "등록되지 않은 이메일"로 계정 존재 여부가 새어나감) |

### 2.5 V7 — 결제 금액: 서버 재계산 + 대조 + 멱등

**현재 흐름의 문제**: `buildPending`(2055)이 브라우저에서 `amount` 를 계산해 localStorage에 넣고, `handlePaymentReturn`(2346)이 그 값과 토스 응답을 비교한 뒤 `confirmApiUrl` 이 비어 있으면 **"테스트 승인"으로 주문을 확정**합니다. 즉 금액·재고·포인트 전부 클라이언트 신뢰입니다.

**서버 흐름(반드시 이 순서)**

```
① POST /api/orders/prepare
   - 장바구니/선택상품 + coupon_code + points_to_use 를 받아
   - 서버가 DB 가격으로 subtotal·discount·shipping·points_used·amount 재계산
   - orders 행을 status='pending_payment'(또는 별도 payments 테이블)로 저장, order_no 발급, 만료 10~20분
   - 응답: {order_no, amount, order_name, customer_key}      ← 브라우저는 이 값으로 결제창만 연다
② 브라우저가 토스 결제창 호출 (clientKey, successUrl=?tossResult=success)
③ POST /api/payments/confirm {paymentKey, orderId, amount}
   - 세션 사용자와 order.user_id 일치 확인
   - order.status == 'pending_payment' && order.total_amount == amount  (불일치면 402, 승인 호출 금지)
   - 재고/쿠폰/포인트를 트랜잭션으로 재검증 (부족하면 409 → 승인 호출 전 중단)
   - 토스 승인 API 호출(TOSS_SECRET_KEY, Idempotency-Key: confirm-<order_no>)
   - 성공 시 한 트랜잭션: orders.status='paid' + payment_key + payment_mode='server',
     order_items 생성, 재고 차감, 쿠폰 redemption, 포인트 차감(point_logs), cart 비우기
   - 실패 시: 402 + 사유. 토스 승인 실패는 저장하지 않음
④ 멱등: orders.payment_key UNIQUE + order_no UNIQUE. 같은 paymentKey 재요청은 200 + duplicate=true
```

`data/payment_confirm_example.py` 에 **금액 대조 · 중복 승인 방지 · Basic 인증 헤더(`secret + ':'` base64)** 가 이미 구현되어 있습니다. 그대로 이식하고, 위 ③의 재고/쿠폰/포인트 트랜잭션만 추가하세요.

- **`ALLOW_DEMO_PAYMENT_FALLBACK=0`** 으로 두고, 데모 결제(서버 승인 없는 확정) 경로를 **운영에서 제거**합니다.
- 결제 금액이 0원(전액 포인트)인 경우는 토스 결제창을 열지 않고 **서버에서 즉시 확정**하는 별도 경로(`POST /api/orders/free`)로 처리하세요.

### 2.6 V8 — 재고 트랜잭션

```python
# SQLite: 쓰기 트랜잭션은 BEGIN IMMEDIATE 로 잡고, 조건부 UPDATE 로 음수 재고를 원천 차단
with tx(conn):                      # BEGIN IMMEDIATE
    for it in items:
        cur = conn.execute(
            "UPDATE product_variants SET stock = stock - ? WHERE id = ? AND stock >= ?",
            (it.qty, it.variant_id, it.qty))
        if cur.rowcount != 1:
            raise Conflict("재고가 부족합니다: " + it.label)   # 전체 롤백
```
- `stock >= qty` 조건이 **원자적 차감**입니다. `SELECT 후 UPDATE` 두 단계로 하지 마세요.
- 복구(취소/반품 완료)는 **상태 전이와 같은 트랜잭션**에서, `cancelled` 전이·`stock_restored=1` 플래그로 **1회성**을 보장합니다.
- SQLite 는 `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, 단일 uvicorn worker(또는 `--workers 1` + 스레드) 권장. 다중 서버가 필요해지면 PostgreSQL 로 이전하되 스키마는 그대로 씁니다.

### 2.7 V9/V10 — 포인트·쿠폰

- 포인트 잔액은 **`SUM(point_logs.amount)`** 로 계산하고, `users.points` 는 트랜잭션 안에서만 갱신(음수 금지 `CHECK points >= 0`).
- 사용 포인트는 `min(요청, 보유, 결제금액)` 을 **서버가 다시 계산**하고, 클라이언트 값은 "희망값"으로만 취급합니다.
- 쿠폰은 §1.7.3 규칙 재현 + **`coupon_redemptions` 로 사용 이력**을 남겨 재사용을 막습니다(§1.7.3 설계 공백).
- 쿠폰 검증 엔드포인트(`POST /api/coupons/validate`)는 **부작용 없이** 사유 문자열만 돌려줍니다.

### 2.8 V11 — 이미지 업로드 (Data URL → 서버 스토리지)

| 현재 | 서버 대책 |
|---|---|
| Canvas 로 900px JPEG Data URL → localStorage/DB JSON | `POST /api/media` 로 **파일 업로드**. 서버가 저장하고 `URL` 만 돌려줌 |
| 검증 없음(브라우저 `file.type` 만) | ① 확장자 화이트리스트(`jpg/jpeg/png/webp/mp4`) ② **매직바이트로 실제 MIME 확인** ③ 크기 제한(이미지 5MB·동영상 20MB, `.env`) ④ 이미지 재인코딩(Pillow)으로 EXIF/스크립트 제거 ⑤ 파일명 **무작위 UUID**(원본명 미보존) |
| DB에 base64 | `MEDIA_ROOT` 디스크 + `product_images.image`·`reviews.media[].src` 에 **상대 경로**만 저장 |
| — | 서빙: `X-Content-Type-Options: nosniff`, `Content-Disposition: inline; filename="..."`, 이미지 외 확장자 실행 금지 |

**금지**: 업로드 파일을 웹 루트에서 **직접 실행 가능한 위치**에 두지 마세요. `/media/` 는 정적 서빙 전용(스크립트 실행 불가)이어야 합니다.

### 2.9 V12 — XSS

- 서버는 **저장 시** `<`, `>`, `"`, `'`, `&` 를 이스케이프하거나(가장 단순) HTML 을 **허용하지 않는 필드**로 취급합니다. `description`·`review.content`·`qna.content`·`faq.answer`·`site_settings.*` 는 **평문**입니다.
- 프론트 `esc()`(552)는 이미 있으나, `innerHTML` 조합이 많아 **한 곳이라도 빠지면 뚫립니다.** 서버에서 태그를 제거(`bleach`/`nh3` 로 allowlist)하는 편이 안전합니다.
- **CSP**(Nginx, §4.7): `default-src 'self'; img-src 'self' data: https:; script-src 'self' https://js.tosspayments.com; connect-src 'self' https://api.tosspayments.com; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'`
- 사용자 입력을 `href`/`src` 로 받는 곳(사이트 미디어 URL, 리뷰 미디어)은 **`https:` 또는 상대경로만** 허용(`javascript:`·`data:text/html` 차단).

### 2.10 V13/V14 — 메일·SMS 키 격리와 OTP

- **키는 `.env` 에만**: `MAIL_API_KEY`, `SMS_API_KEY`, `TOSS_SECRET_KEY`, `SESSION_SECRET`.
- 현재 `sendEmailCode`(3287)·`sendOrderSms`(3420)는 브라우저에서 `site_settings.email_api_url`/`sms_api_url` 로 **직접 POST** 합니다. 서버로 옮기면 ① 키가 브라우저에 없다 ② 발송 로그를 서버가 강제로 남긴다 ③ 레이트리밋이 실제로 작동한다 는 세 가지가 동시에 해결됩니다.
- `site_settings.email_api_url`·`sms_api_url` 은 **공개 설정 응답에서 제외**(서버 내부 값). 관리자 화면에서도 **URL 을 되돌려주지 말고**(마스킹 `https://…(설정됨)`) 필요하면 `.env` 로만 관리하세요.
- **OTP**: 6자리 숫자, `OTP_TTL_SECONDS=300`, `OTP_COOLDOWN_SECONDS=60`, `OTP_MAX_TRIES=5`(초과 시 폐기), 코드는 **해시로 저장**, 검증 성공 시 **1회용 가입 토큰**(10분) 발급. `verifyEmailCode` 의 "verified 플래그" 같은 클라이언트 상태를 **절대 신뢰하지 않습니다**.
- 발송 실패/차단도 `dispatch_logs` 에 남기고, **인증번호 원문은 로그에 남기지 않습니다**(현재 구현과 동일 원칙).

### 2.11 V15 — CSRF / CORS

- 쿠키 세션이므로 상태 변경 요청은 **CSRF 방어**가 필요합니다: `SameSite=Lax` + (권장) 세션별 `csrf_token` 을 `X-CSRF-Token` 헤더로 요구. `Origin`/`Referer` 화이트리스트 검사도 함께.
- CORS: 프론트가 **같은 오리진**(`/api/`)이면 CORS 불필요. GitHub Pages(`https://chaeci.github.io`)에서 내부서버 API를 직접 호출하는 구성이면 `CORS_ORIGINS` 에 그 도메인만 허용하고 **`allow_credentials=True` + wildcard 금지**.

### 2.12 V16 — IDOR(객체 참조) 검사표

| 엔드포인트 | 검사 |
|---|---|
| `GET /api/orders/{id}` | `order.user_id == session.user_id` or admin |
| `POST /api/orders/{id}/cancel` | 본인 + 상태 `paid`/`preparing` 만 |
| `GET /api/claims/{id}` | 본인 or admin |
| `PATCH /api/claims/{id}/status` | admin |
| `POST /api/reviews` | `order_item` 의 주문 소유자 == 세션 사용자 |
| `PATCH /api/reviews/{id}` | 작성자 or admin |
| `POST /api/reviews/{id}/vote` | 본인 리뷰 아님 + UNIQUE |
| `DELETE /api/qnas/{id}` | admin |
| `GET /api/admin/members/{id}` | admin |
| `GET /api/media/{file}` | 경로 조작(`../`) 차단, 업로더/공개 정책 확인 |

**원칙**: URL 파라미터로 받은 id 는 **항상 "내 것인가"를 먼저 묻고**, 아니면 **404**(존재 여부도 숨김) 를 돌려줍니다.

### 2.13 V17~V20 — 운영 보안

- **민감 필드 분리**: `admin_memo`(클레임), `dispatch_logs.to_addr`, `sms_logs.phone`, 회원 연락처·주소는 **관리자 응답에만**. 고객 응답은 마스킹(`010-****-2219`) 또는 생략.
- **레이트리밋**: 로그인 5/5분(IP+계정), OTP 발송 60초/이메일 + 20/일/IP, 쓰기 30/분/사용자, 업로드 10/분.
- **감사 로그**: 관리자 로그인·권한 변경·회원 정보 열람·데이터 내보내기·주문 상태 변경·포인트 조정을 `audit.log`(JSONL)에 남깁니다. `users` 삭제·수정 전후 값 포함.
- **개인정보**: 수집 항목 최소화(이름·연락처·주소·이메일), **주민번호·카드정보 저장 금지**(카드는 토스가 처리, `payment_key` 만 보관), 보존기간·파기 정책 문서화, DB 파일 권한 `600`.
- **백업**: `sqlite3 .backup` 또는 `VACUUM INTO` 로 일 1회, 14일 보관(§4.10).
- **비밀 관리**: `.env` 는 `600`, git 에는 `.env.example` 만. **배포 후 `git log -p | grep -i "sk_\|api_key"`** 로 유출 이력을 점검.

### 2.14 서버 공통 원칙(체크리스트)

1. 모든 입력은 **Pydantic 모델로 타입·길이·범위 검증**(`price ≥ 0`, `rating 1~5`, `quantity 1~99`, `title ≤ 60`).
2. 모든 출력은 **명시적 응답 모델**(`response_model=`) — `SELECT *` 를 그대로 돌려주지 않습니다.
3. 모든 상태 변경은 **트랜잭션** — 부분 성공 금지(주문·재고·포인트·쿠폰이 한 몸).
4. 모든 4xx 응답은 **사유만** 주고 내부 경로·SQL·스택을 노출하지 않습니다(로그에만).
5. `ORDER BY`/`LIMIT` 은 **화이트리스트**로만 받습니다(SQL 인젝션·과도한 조회 방지).
6. 에러 로그에 **비밀번호·OTP·토큰·카드정보** 를 남기지 않습니다.

---

## 3. API 명세 (전체)

### 3.0 공통 규칙

| 항목 | 규칙 |
|---|---|
| Base | `https://<host>/api` (Nginx → `127.0.0.1:8000`) |
| 형식 | 요청·응답 `application/json; charset=utf-8` (파일 업로드만 `multipart/form-data`) |
| 금액 | **원 단위 정수**(소수 없음), 포인트 `1P = 1원` |
| 시각 | ISO-8601 문자열, `Asia/Seoul` (`2026-11-28T23:53:30+09:00`) |
| ID | 문자열. 시드 id(`u_001`, `p_001`, `o_006`, `oi_012`, `rv_003` …)를 그대로 쓰고 신규는 서버 발급 |
| 인증 | 세션 쿠키 `mono_session` (HttpOnly). 권한 열: `공개` / `회원` / `관리자` |
| 페이징 | `?page=1&limit=10` → `{items, page, limit, total, pages}`. 관리자 목록 기본 `limit=10`(`ADMIN_PAGE_SIZE` 6441) |
| 정렬 | `?sort=new\|old\|price_asc\|price_desc`(상품), `?sort=new\|top`(리뷰) — **화이트리스트**만 허용 |
| 성공 | `2xx` + 본문. 생성 `201`, 삭제/로그아웃 `204` |
| 실패 | `{"ok": false, "code": "OUT_OF_STOCK", "message": "재고가 부족합니다.", "field": "quantity"}` — HTTP 상태와 별개로 `code` 항상 포함(부록 B) |
| 멱등 | `POST /api/payments/confirm` 은 `paymentKey`/`orderId` 기준 멱등. 중복 요청은 `200 + {duplicate:true}` |
| 레이트리밋 | 429 + `Retry-After` 헤더 |

> **프론트 호환 메모**: 현재 `app.js` 의 도메인 함수는 모두 **동기**(`return {ok, message, ...}`)입니다. API 로 바꾸면 `Promise` 가 되므로, 응답을 **`{ok, ...}` 규약으로 유지**하면 호출부 수정이 최소화됩니다(§4.8).

### 3.1 인증 `/api/auth/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 함수 |
|---|---|---|---|---|---|
| POST | `/api/auth/signup` | 공개 | `{email, password, password2, name, phone, postcode, address, address_detail, email_token}` | `201 {user}` + 쿠키 | `signup` 1777 |
| POST | `/api/auth/login` | 공개 | `{email, password}` | `200 {user}` + 쿠키 | `login` 1768 |
| POST | `/api/auth/logout` | 회원 | — | `204` | `logout` 1890 |
| GET | `/api/auth/me` | 공개 | — | `{user: {...} \| null}` | `currentUser` 865 |
| POST | `/api/auth/email-code` | 공개 | `{email}` | `{ok, expires_in:300}` (`ALLOW_TEST_OTP_ECHO=1` 이면 `dev_code`) | `sendEmailCode` 3287 |
| POST | `/api/auth/email-code/verify` | 공개 | `{email, code}` | `{ok, email_token}` (10분·1회용) | `verifyEmailCode` 3324 |
| POST | `/api/auth/password` | 회원 | `{current_password, new_password}` | `204` | (신규 권장) |

**규칙**

- `email` 은 `trim().lower()` 정규화 후 저장·조회.
- `signup` 순서: ① `email_token` 유효 + 토큰의 이메일 일치 ② 비밀번호 정책(§1.5) ③ `password == password2` ④ 이름·연락처·주소 필수 ⑤ 이메일 UNIQUE. 실패 시 **필드별 `field` 를 함께 반환**해 입력값을 잃지 않게 합니다.
- 기본값: `role='customer'`, `grade='NORMAL'`, `points=0`. **관리자 승격 API 는 만들지 않습니다**(DB 직접 변경만).
- `login` 실패는 **"이메일 또는 비밀번호가 올바르지 않습니다"** 로 통일(계정 존재 여부 노출 금지).
- 로그인 성공 시 응답 `user` 에서 **`password_hash` 를 절대 포함하지 않습니다**(모든 사용자 응답 공통).

### 3.2 상품 `/api/products/*`

| 메서드 | 경로 | 권한 | 요청/쿼리 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/products` | 공개 | `category, q, sort, page, limit, in_stock` | `{items:[ProductCard], total}` | `visibleProducts` 2959 · `sortedProducts` 2967 |
| GET | `/api/products/{id}` | 공개 | — | `{product: ProductDetail}` | `productById` 872 · `productModalHTML` 4632 |
| GET | `/api/products/by-code/{code}` | 공개 | — | `{product}` (대소문자 무시) | `productByCode` 893 |
| GET | `/api/bootstrap` | 공개 | — | `{categories, site, help, faqs_meta, badges, point_policies_public}` | `boot` 12824 |
| POST | `/api/products` | 관리자 | `multipart: fields + images[]` | `201 {product}` | `saveProduct` 2533 |
| PUT | `/api/products/{id}` | 관리자 | 동일 | `{product}` | `saveProduct` 2533 |
| PATCH | `/api/products/{id}/active` | 관리자 | `{is_active: 0\|1}` | `{product}` | `toggleProductActive` 2646 |
| PATCH | `/api/products/{id}/soldout` | 관리자 | — | `{product}` | `soldoutProduct` 2653 |
| DELETE | `/api/products/{id}` | 관리자 | — | `204` (주문 스냅샷은 보존) | (신규) |

**ProductCard(공개 응답)**

```json
{
  "id": "p_001", "product_code": "MA-0001", "name": "울 더블 브레스티드 코트",
  "category": "outer", "price": 289000, "original_price": 349000,
  "badge": "BEST", "image": "coat.webp", "images": ["coat.webp", "coat-detail.webp", "coat-fabric.webp"],
  "stock_total": 24, "is_active": 1, "free_shipping_threshold": null,
  "colors": [{"color": "차콜", "hex": "#35353A"}], "sizes": ["S", "M", "L", "XL"],
  "rating": {"avg": 4.6, "count": 12}
}
```

- **공개 목록은 `is_active = 1` 만** 반환합니다. 관리자 목록은 `?include_hidden=1`(관리자 권한 필요).
- `q` 는 **상품명·제품번호·설명** 부분일치. 관리자 검색은 카테고리·판매상태·등록일 범위(`from`,`to`) 추가(`adminProductMatches` 6566).
- `ProductDetail` 은 여기에 `description`, `model_info`, `variants[{id,color,color_hex,size,stock,sku}]`, `reviews_summary` 를 더합니다. **`cost`·내부 메모 같은 필드는 만들지 않습니다.**
- 상품 저장 규칙(`saveProduct` 2533): `product_code` 는 `MA-####` 자동 채번(`nextProductCode` 877), **대소문자 무시 중복 금지**(`productCodeTaken` 885), `original_price ≥ price`, `badge` 는 **등록된 코드만**(§3.4), 옵션 `UNIQUE(product_id,color,size)`, `sku` UNIQUE, 이미지 최소 1장.
- **`product_variants.size` CHECK 주의**: 스키마는 `S/M/L/XL/FREE` 만 허용하지만 관리자 화면은 카테고리별 사이즈 코드(`95`,`100`,`28`,`FREE` …)를 추가할 수 있습니다. 사이즈 코드를 자유롭게 쓰려면 `ALTER` 로 CHECK 를 완화하거나(권장: `size_codes` 를 참조하는 별도 검증) 상품 저장 시 **허용 목록 검사**를 서버에서 하세요.

### 3.3 카테고리 `/api/categories/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/categories` | 공개 | `?include_hidden=0` | `{items}` (sort_order 순, 숨김 제외) | `storeCategories` 212 |
| POST | `/api/categories` | 관리자 | `{label, en, size_codes}` | `201 {category}` | `addCategory` 8420 |
| PUT | `/api/categories/{id}` | 관리자 | `{label, en, sort_order, is_active, size_codes}` | `{category}` | `updateCategory` 8436 · `saveCategoryDetail` 8455 |
| DELETE | `/api/categories/{id}` | 관리자 | — | `204` — **상품이 있으면 409** | `deleteCategory` 8473 |
| PATCH | `/api/categories/order` | 관리자 | `{ids:[...]}` | `{items}` | `moveCategory` 8539 |
| PATCH | `/api/categories/{id}/size-codes` | 관리자 | `{size_codes:[...]}` | `{category}` | `saveCategorySizeCodes` 8496 |

- 숨김(`is_active=0`)은 **스토어 필터에서만** 빠지고 상품 등록 드롭다운에는 남습니다.
- 삭제 시 연결 상품이 있으면 차단(409) — 현재 프론트와 동일.

### 3.4 코드 관리(뱃지) `/api/codes/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/codes/badges` | 공개 | — | `{items:[{code, product_count, coupon_count}]}` | `badgeList` 3019 · `badgeUsageCount` 8671 |
| POST | `/api/codes/badges` | 관리자 | `{code}` | `201 {items}` | `addBadge` 8687 |
| PUT | `/api/codes/badges/{code}` | 관리자 | `{code: "NEWCODE"}` | `{items, updated:{products, coupons}}` | `renameBadge` 8697 |
| DELETE | `/api/codes/badges/{code}` | 관리자 | — | `{items}` — **상품 연결 시 409** | `deleteBadge` 8718 |
| PATCH | `/api/codes/badges/order` | 관리자 | `{codes:[...]}` | `{items}` | `moveBadge` 8730 |

- 뱃지 코드 변경은 **`products.badge` 와 `coupons.target_badges` 에 트랜잭션으로 전파**해야 합니다(현재 `renameBadge` 가 하는 일).
- 기본 코드 `BEST/NEW/SALE/LIMITED`, 최대 16개(`BADGE_CUSTOM_MAX`).

### 3.5 장바구니 `/api/cart/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/cart` | 회원 | — | `{items:[{id, variant, product, quantity}], totals}` | `cartRows` 1334 |
| POST | `/api/cart` | 회원 | `{variant_id, quantity}` | `201 {item}` (같은 옵션이면 수량 합산) | `addToCart` 1911 |
| PATCH | `/api/cart/{id}` | 회원 | `{quantity}` | `{item}` | `setCartQty` 1933 |
| DELETE | `/api/cart/{id}` | 회원 | — | `204` | `removeCartItem` 1947 |
| POST | `/api/cart/delete` | 회원 | `{ids:[...]}` | `{deleted}` | `removeCartItems` 1955 |
| POST | `/api/cart/select-all` | 회원 | `{selected:true\|false}` | `{items}` | `setAllSelected` 1980 |

- `UNIQUE(user_id, variant_id)` 로 중복 담기를 막고, 담을 때 **재고 0 이면 409**(프론트의 품절 안내와 동일).
- `totals` 는 **서버 계산값**(§1.7.1)을 그대로 내려 표시와 결제가 어긋나지 않게 합니다. 쿠폰·포인트는 `POST /api/cart/quote` 로 미리보기.

### 3.6 주문·결제 `/api/orders/*`, `/api/payments/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| POST | `/api/cart/quote` | 회원 | `{items?:[{variant_id,quantity}], coupon_code?, points_to_use?}` | `{subtotal, discount, shipping, total, points_used, amount, coupon:{ok,message}}` | `totalsOf` 1352 · `couponCheck` 1295 |
| POST | `/api/orders/prepare` | 회원 | `{cart_ids?:[...], items?:[...], coupon_code?, points_to_use, recipient_name, recipient_phone, postcode, shipping_address, payment_method}` | `201 {order_no, amount, order_name, customer_key, expires_at}` | `buildPending` 2055 |
| POST | `/api/orders/free` | 회원 | `{order_no}` (amount 가 0원인 준비 주문) | `200 {order}` | (신규 — 전액 포인트 결제) |
| GET | `/api/orders` | 회원 | `?status=&page=&limit=` | `{items:[Order], total}` (본인 것만) | `mypageHTML` 5800 · `ordersHTML` 6018 |
| GET | `/api/orders/{id}` | 회원/관리자 | — | `{order, items:[OrderItem], claim?, sms_logs?}` | `orderDetailHTML` 6083 |
| POST | `/api/orders/{id}/cancel` | 회원 | `{reason?}` | `{order, restored, refunded}` | `cancelOrder` 2431 |
| POST | `/api/orders/{id}/confirm-items` | 회원 | `{order_item_id}` | `{item, points, balance, rate}` | `confirmOrderItem` 3677 |
| PATCH | `/api/orders/{id}/status` | 관리자 | `{status}` | `{order, restored, refunded}` | `applyOrderStatus` 2463 |
| POST | `/api/admin/orders/bulk-status` | 관리자 | `{ids:[...], status}` | `{changed, skipped, skippedCancelled, skippedSame, restored, refunded}` | `bulkUpdateOrderStatus` 2484 |
| GET | `/api/admin/orders` | 관리자 | `?status=&from=&to=&q=&page=` | `{items, total}` | `adminOrderListOf` 9304 |
| POST | `/api/payments/confirm` | 회원 | `{paymentKey, orderId, amount}` | `{ok, orderId, paymentKey, method, totalAmount, approvedAt}` | `confirmPayment` 2316 |
| POST | `/api/payments/cancel` | 관리자 | `{orderId, cancelReason, cancelAmount?}` | `{ok, canceledAt}` | `cancelOrder` 2431(현재 DB만) |
| POST | `/api/payments/webhook` | 공개(Toss) | Toss webhook payload | `200` (서명 검증) | (신규 권장) |

**`POST /api/orders/prepare` 상세**

1. 로그인 확인 → `cart_ids` 또는 `items` 로 주문 상품 확정(둘 다 없으면 400).
2. **서버가 가격·재고·쿠폰·포인트를 재계산**(§1.7.1). 클라이언트가 보낸 금액은 **받지 않습니다**(받아도 무시).
3. 재고가 부족하면 409 `OUT_OF_STOCK` + 부족 상품 목록.
4. `orders` 에 **`status='pending_payment'`** 로 저장(운영 스키마에 상태 추가 필요 — 부록 C 참조), `order_no = "MA" + YYYYMMDD + "-" + 4자리`(`makeOrderNo` 1986), `expires_at = now + 20분`.
5. `order_name` 은 `첫 상품명 외 N건`(최대 100자, `orderNameOf` 2040).
6. `customer_key` 는 **무작위 22자 이상**(`customerKey` 2023 원칙) — 이메일·전화번호를 쓰지 않습니다.

**`POST /api/payments/confirm` 상세(가장 중요)**

```
1) 세션 사용자 == order.user_id 확인
2) order.status == 'pending_payment' 확인 (이미 paid → 200 {duplicate:true})
3) order.total_amount == amount 확인 (불일치 → 402 AMOUNT_MISMATCH, 토스 승인 호출 금지)
4) 재고·쿠폰·포인트 재검증 (BEGIN IMMEDIATE)
5) 토스 승인: POST https://api.tosspayments.com/v1/payments/confirm
   Authorization: Basic base64(TOSS_SECRET_KEY + ":")
   Idempotency-Key: confirm-<order_no>
6) 성공 → 같은 트랜잭션에서
   orders(status='paid', payment_key, payment_provider='tosspayments', payment_mode='server')
   order_items 생성(상품명·색·사이즈·단가 스냅샷)
   product_variants.stock -= qty  (stock >= qty 조건부)
   coupon_redemptions INSERT (있으면)
   point_logs INSERT (type='use', amount=-points_used)
   cart_items 삭제(주문한 항목)
7) 실패 → 402 PAYMENT_FAILED + 토스 메시지(그대로 노출하지 말고 요약)
```

- ④와 ⑥ 사이에서 예외가 나면 **재고를 되돌리고 402**. 절대 부분 커밋하지 않습니다.
- `payment_key` UNIQUE 인덱스(`payment_confirm_example.py` 의 `ensure_columns` 참고)로 **이중 승인**을 막습니다.
- 승인 성공 후 `dispatch_logs`/`sms_logs` 에 주문 완료 알림을 기록(`sendOrderSms` 3420, 테스트 모드는 `status='test'`).

**주문 상태 전이 규칙**

| From → To | 허용 주체 | 부수 효과 |
|---|---|---|
| `pending_payment` → `paid` | 결제 확정만 | 재고 차감·포인트 사용·쿠폰 사용 |
| `paid`/`preparing` → `cancelled` | 본인·관리자 | **재고 복구 1회 + 사용 포인트 환급** |
| `paid` → `preparing` → `shipping` → `delivered` | 관리자 | 없음 |
| `shipping`/`delivered` → `cancelled` | **불가** | 고객은 교환/반품으로 처리 |
| `cancelled` → 그 외 | **불가** | 중복 복구·환급 방지 |

### 3.7 반품/교환 `/api/claims/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| POST | `/api/claims/prepare` | 회원 | `{order_id, claim_type, reason_category, reason_detail, exchange_option?}` | 판매자 귀책 → `201 {claim}` / 고객 귀책 → `{claim_id, shipping_fee, order_name}` | `buildClaim` 1057 · `claimFeeOf` 1011 |
| POST | `/api/claims/{id}/confirm-payment` | 회원 | `{paymentKey, amount}` | `{claim}` | `finalizeClaim` 1096 · `handleClaimReturn` 2384 |
| GET | `/api/claims` | 회원 | `?page=` | `{items}` (본인 것) | `claimOfOrder` 1008 |
| GET | `/api/claims/{id}` | 회원/관리자 | — | `{claim}` (**`admin_memo` 는 관리자만**) | `adminClaimSheetHTML` 8878 |
| PATCH | `/api/claims/{id}/status` | 관리자 | `{status, admin_memo?}` | `{claim, restored}` | `updateClaimStatus` 1131 |
| POST | `/api/admin/claims/bulk-status` | 관리자 | `{ids:[...], status}` | `{changed, skipped, restored}` | `bulkUpdateClaimStatus` 1150 |
| GET | `/api/admin/claims` | 관리자 | `?status=&from=&to=&q=&page=` | `{items, total}` | `adminClaimListOf` 8806 |

- 신청 자격: 주문 `shipping`/`delivered`, **주문당 1건**(`UNIQUE(order_id)`), 진행 중 클레임 있으면 409.
- 판매자 귀책(`defect`,`wrong_item`)은 **결제 없이 즉시 `requested`**, 고객 귀책은 **배송비 결제 후** `requested`(`payment_status='paid'`).
- 교환 옵션은 **해당 상품의 재고 있는 옵션**만 허용. 서버에서 `exchange_option` 을 파싱해 재고 확인.
- `completed` 전이 시 **재고 1회 복구**(`stock_restored` 플래그). `rejected` 는 복구 없음.

### 3.8 리뷰 `/api/reviews/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/products/{id}/reviews` | 공개 | `?sort=new\|top&page=&limit=5` | `{items, total, pages, stats:{avg,count}}` | `sortedProductReviews` 3805 · `reviewStats` 3740 |
| GET | `/api/reviews/reviewable` | 회원 | `?product_id=` | `{items:[{order_item_id, order_id, can_write, rewrite, reason}]}` | `reviewableItems` 3844 |
| POST | `/api/reviews` | 회원 | `{order_item_id, rating, content, media:[{type,url}]}` | `201 {review, bonus, balance}` | `addReview` 3872 |
| PATCH | `/api/reviews/{id}` | 회원(작성자) | `{rating, content, media}` | `{review}` | `updateReview` 3948 |
| POST | `/api/reviews/{id}/vote` | 회원 | `{vote: "up"}` / `{vote: "down"}` / `{vote: null}` | `{counts, my_vote}` | `toggleReviewVote` 3769 |
| GET | `/api/admin/reviews` | 관리자 | `?status=&q=&page=` | `{items, total}` | `adminReviewList` 7287 |
| PATCH | `/api/admin/reviews/{id}/approve` | 관리자 | — | `{review, restored_points}` | `approveReview` 7900 |
| PATCH | `/api/admin/reviews/{id}/reject` | 관리자 | `{reason}` (필수) | `{review, reclaimed}` | `rejectReview` 3981 |
| POST | `/api/admin/reviews/bulk-reject` | 관리자 | `{ids:[...], reason}` | `{changed, skipped, reclaimed}` | `bulkReclaimReviews` 7936 |
| GET | `/api/admin/reviews/reclaims` | 관리자 | `?page=` | `{items}` (포인트 회수 내역) | `adminReclaimHTML` 7253 |

- 공개 목록은 **`status='published'` 만**. `user_name` 은 마스킹된 값만.
- 작성 검증(§1.7.7)은 **서버에서 전부 재검증**: 본인 주문항목·배송완료·구매확정·클레임 없음·차수 제한.
- `reject` 는 **사유 필수**(빈 문자열 400), 회수액은 **보유 포인트 한도 내**(`min(보너스, 보유)`), 이미 반려된 리뷰는 409.
- `approve`(반려 취소)는 회수 포인트를 **1회 복원**.

### 3.9 Q&A `/api/qnas/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/products/{id}/qnas` | 공개 | `?page=&limit=5` | `{items, total, pages, unanswered}` | `productQnas` 4831 · `qnaCanRead` 4838 |
| POST | `/api/products/{id}/qnas` | 회원 | `{qna_type, title, content, is_secret}` | `201 {qna}` | `submitQna` 4931 |
| GET | `/api/admin/qnas` | 관리자 | `?status=&q=&page=` | `{items, total}` | `adminQnaList` 7371 |
| GET | `/api/admin/qnas/{id}` | 관리자 | — | `{qna}` (원문 전체) | `adminQnaDetailHTML` 7449 |
| PATCH | `/api/admin/qnas/{id}/answer` | 관리자 | `{answer}` (≤1000자, 비우면 미답변) | `{qna}` | `answerQna` 4957 |
| DELETE | `/api/admin/qnas/{id}` | 관리자 | — | `204` | `deleteQna` 4971 |

> **비밀글 응답 규칙(핵심)** — 다른 사람에게는 **`title`·`content`·`answer` 키를 아예 내려주지 않습니다.**
> `{"id","qna_type","is_secret":1,"status","user_name":"홍길*","created_at","locked":true}`
> 프론트의 `qnaItemHTML`(4856)이 `locked` 를 보고 `🔒 비밀글입니다` 를 그리도록 수정하세요(§4.8).

- 유형 `product|delivery|claim|etc`, 제목 2~60자, 내용 ≤500자.
- `user_name` 은 `maskUserName`(3653) 과 동일하게 저장·표시.

### 3.10 쿠폰 `/api/coupons/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/coupons/mine` | 회원 | — | `{items}` (공용+등급+본인 전용, 활성만) | `couponsForUser` 1281 · `couponsHTML` 5877 |
| POST | `/api/coupons/validate` | 회원 | `{code, items?:[...]}` | `{ok, discount, base, coupon?, message}` | `couponCheck` 1295 |
| GET | `/api/admin/coupons` | 관리자 | `?page=` | `{items, total}` | `adminCouponsHTML` 8229 |
| POST | `/api/admin/coupons` | 관리자 | `{code, name, discount_type, discount_value, min_order_amount, expires_at?, target_grades[], target_user_ids[], target_categories[], target_badges[]}` | `201 {coupon}` | `createCoupon` 8330 |
| PUT | `/api/admin/coupons/{id}` | 관리자 | 동일 | `{coupon}` | `updateCoupon` 8348 |
| PATCH | `/api/admin/coupons/{id}/active` | 관리자 | `{is_active}` | `{coupon}` | `toggleCoupon` 8371 |
| DELETE | `/api/admin/coupons/{id}` | 관리자 | — | `204` — **사용 이력 있으면 409 권장** | (신규) |

- `code` 는 **대문자 정규화 + UNIQUE**. `discount_value > 0`, `percent` 는 1~100.
- 발급 대상은 `coupon_targets` 로 분해 저장(§1.3). 등급·회원 둘 다 있으면 **AND**.
- `validate` 는 **부작용 없는** 사전 검사이며, 실패 사유 문자열은 §1.7.3 표의 문구를 그대로 씁니다(화면이 그대로 노출).

### 3.11 회원·멤버십 `/api/members/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/members/me` | 회원 | — | `{user, summary:{points, spent, orders, reviews, avg_rating}}` | `profileHTML` 5844 |
| PATCH | `/api/members/me` | 회원 | `{name, phone, postcode, address, address_detail}` | `{user}` | `save-profile` 10738 |
| GET | `/api/members/me/points` | 회원 | `?page=` | `{items:[point_logs], balance}` | `pointsHTML` 5933 |
| GET | `/api/members/me/reclaims` | 회원 | — | `{items}` (리뷰 반려 회수 안내) | `pointReclaimsHTML` 5912 |
| GET | `/api/admin/members` | 관리자 | `?q=&page=` | `{items, total}` | `memberList` 7572 |
| GET | `/api/admin/members/{id}` | 관리자 | — | `{user, orders_count, reviews_count, avg_rating, recent_points}` | `adminMemberHTML` 7737 |
| POST | `/api/admin/members/{id}/points` | 관리자 | `{amount, reason}` (사유 필수) | `{user, log}` | `adjustMemberPoints` 7808 |
| PATCH | `/api/admin/members/{id}/grade` | 관리자 | `{grade}` | `{user}` | `saveMemberGrade` 7827 |
| GET | `/api/admin/membership/targets` | 관리자 | `?months=6` | `{rules, items:[{user, recent_spend, current, next}]}` | `membershipTargets` 7623 |
| PATCH | `/api/admin/membership/rules` | 관리자 | `{months, thresholds}` | `{rules}` | `saveGradeRulesFromForm` 7632 |
| POST | `/api/admin/membership/apply` | 관리자 | `{months, thresholds, confirm:true}` | `{changed, items}` | `applyMembershipTargets` 7658 |

- 회원 목록 응답에서 **`password_hash` 는 절대 금지**. 연락처는 관리자 화면 용도로만.
- 포인트 조정은 **보유 포인트보다 큰 차감 금지**(400), `point_logs` 기록 필수, 사유는 3자 이상.
- 등급 자동 적용은 **관리자 계정 제외**, 임계값 오름차순 검증.

### 3.12 사이트 설정·미디어 `/api/site/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/site` | 공개 | — | `{site: PublicSite}` + `{help:[...]}` | `siteSettings` 3057 · `applySiteTitle` 2922 |
| PUT | `/api/admin/site` | 관리자 | `PublicSite` + 관리자 전용 필드 | `{site}` | `saveSiteSettings` 3177 · `readSiteForm` 8024 |
| PUT | `/api/admin/help` | 관리자 | `{items:[{id?,title,body}]}` | `{help}` | `saveHelpTopics` 3214 |
| POST | `/api/admin/site/media` | 관리자 | `multipart {file, kind:hero\|story}` | `{src, images}` | `addSiteMedia` 6696 |
| POST | `/api/admin/site/media/url` | 관리자 | `{kind, url}` | `{src, images}` (https/상대경로만) | `addSiteMedia` 6696 |
| DELETE | `/api/admin/site/media` | 관리자 | `{kind, src}` | `{images}` — **적용 중 사진 삭제 409** | `removeSiteMedia` 6712 |
| PATCH | `/api/admin/site/media/select` | 관리자 | `{kind, src}` | `{site}` | `selectSiteMedia` 6727 |

**`PublicSite`(공개 응답) 허용 키** — `top_banner_text`, `top_banner_sub`, `top_banner_enabled`, `hero_image`, `hero_images`, `hero_eyebrow`, `hero_title`, `hero_subtitle`, `hero_cta_label`, `hero_cta2_label`, `hero_effect`, `hero_overlay`, `story_image`, `story_images`, `story_eyebrow`, `story_title`, `story_subtitle`, `story_body`, `story_tags`, `brand_story_enabled`, `shop_eyebrow`, `shop_title`, `shop_desc`, `site_title`, `page_title`, `footer_copyright`, `brand_blurb`, `company_name`, `company_ceo`, `company_reg_no`, `company_mail_order_no`, `company_address`, `company_phone`, `company_email`, `faq_categories`, `product_badges`, `member_grade_rules`(표시용), `sms_enabled`

**절대 공개하지 말 것** — `email_api_url`, `sms_api_url`, `sms_sender`, `email_auth_mode`, `sms_mode`, `id`, `updated_at`

- 사진 목록은 **최대 24장**(`SITE_MEDIA_MAX`). 히어로·스토리는 **상품 사진과 분리된 전용 목록**입니다.
- `company_*` 는 실제 사업자 정보이므로 **관리자만 수정**, 공개 페이지에는 표시됨(의도된 공개).

### 3.13 FAQ·HELP `/api/faqs/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/faqs` | 공개 | `?category=&q=&page=&limit=5` | `{items, total, pages, categories}` | `filteredFaqs` 4114 · `faqListHTML` 10246 |
| GET | `/api/faqs/categories` | 공개 | — | `{items:[...]}` | `faqCategories` 4043 |
| POST | `/api/admin/faqs` | 관리자 | `{category, question, answer, sort_order, is_active}` | `201 {faq}` | `saveFaqItem` 7089 |
| PUT | `/api/admin/faqs/{id}` | 관리자 | 동일 | `{faq}` | `saveFaqItem` 7089 |
| DELETE | `/api/admin/faqs/{id}` | 관리자 | — | `204` | `deleteFaqItems` 7139 |
| POST | `/api/admin/faqs/bulk-delete` | 관리자 | `{ids:[...]}` | `{deleted}` | `deleteFaqItems` 7139 |
| PATCH | `/api/admin/faqs/order` | 관리자 | `{ids:[...]}` | `{items}` | `moveFaqItem` 7125 |
| PUT | `/api/admin/faqs/categories` | 관리자 | `{names:[...], renames?:{old:new}}` | `{categories, moved}` | `saveFaqCategories` 4061 |

- 공개 목록은 `is_active=1` 만, **페이지당 5건**(`FAQ_PAGE_SIZE`).
- 카테고리 이름 변경은 **연결된 FAQ 에 전파**, FAQ 가 있는 카테고리 삭제는 409.
- HELP 항목(`help_topics`)은 **항상 3~4개**, 홈 4칸 중 `FAQ` 칸은 FAQ 게시판으로 연결됩니다.

### 3.14 발송 로그 `/api/logs/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/admin/logs` | 관리자 | `?channel=sms\|email&status=&q=&page=` | `{items, total}` | `dispatchFilterRows` 3482 |
| GET | `/api/admin/logs/anomalies` | 관리자 | — | `{recipients:[...], burst:{count}}` | `dispatchAnomalies` 3394 |
| GET | `/api/admin/sms-logs` | 관리자 | `?order_id=` | `{items}` | `smsLogsOf` 3344 |
| PATCH | `/api/admin/notify-settings` | 관리자 | `{email_auth_mode, sms_enabled, sms_mode}` | `{settings}` (**URL 은 반환하지 않음**) | `saveNotifySettings` 3253 |
| POST | `/api/admin/notify-test` | 관리자 | `{channel, to}` | `{ok, status}` (레이트리밋 적용) | (신규 권장) |

- 수신자(`to_addr`)는 **마스킹해서 목록에 표시**(`abc***@mail.com`), 상세에서만 원문. 전부 관리자 전용.
- 인증번호 원문은 어떤 로그에도 저장하지 않습니다.

### 3.15 관리자 집계 `/api/admin/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 | 대응 |
|---|---|---|---|---|---|
| GET | `/api/admin/stats` | 관리자 | — | `{active_products, orders_total, pending, claims_in_progress}` | KPI 카드 6337 |
| GET | `/api/admin/revenue` | 관리자 | `?from=&to=&bucket=day\|month` | `{summary:{revenue, orders, cancelled, avg}, series:[{key,revenue,orders}], rows:[...]}` | `revenueBuckets` 9067 · `revenueDetailTableHTML` 9196 |
| GET | `/api/admin/data/tables` | 관리자 | — | `{items:[{name,label,count}], total}` | `storeTableSummary` 2863 |
| GET | `/api/admin/data/export` | 관리자 | — | `{tables:{...}, meta}` (**감사 로그 필수**) | `exportPayload` 2663 |
| GET | `/api/admin/data/integrity` | 관리자 | — | 점검 결과(금액 불일치·FK·열거값) | `runIntegrity` 2705 |

- 매출은 **취소 주문 제외 실매출**(`상품금액 + 배송비 − 할인`), 31일 이하면 일별·그 외 월별.
- 데이터 내보내기는 **개인정보 전체**이므로 ① 관리자 ② 감사 로그 ③ 응답 헤더 `Content-Disposition: attachment` ④ 캐시 금지.
- **`POST /api/admin/data/reset`(초기화)는 운영에서 비활성**하는 것을 권장합니다(현재 `resetDB` 2694 는 확인 문구만 있으면 전체 삭제).

### 3.16 미디어 `/api/media/*`

| 메서드 | 경로 | 권한 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/api/media` | 회원 | `multipart {file, purpose: product\|review\|site}` | `201 {url, mime, width, height, bytes}` |
| GET | `/media/{filename}` | 공개 | — | 이미지/동영상 스트림 |
| DELETE | `/api/media/{id}` | 관리자/업로더 | — | `204` (참조 중이면 409) |

- 검증: 확장자 + **매직바이트** + 크기 + (이미지) `Pillow` 재인코딩으로 EXIF 제거. 실패는 `415`.
- 저장 경로: `MEDIA_ROOT/YYYY/MM/<uuid>.<ext>`. **원본 파일명을 경로에 쓰지 않습니다.**
- 리뷰 첨부는 **회원당 6개·동영상 20MB** 제한(현재 UI 제한 6개/4MB 보다 여유 있게, 서버 값을 기준으로).

### 3.17 기타

| 메서드 | 경로 | 권한 | 응답 |
|---|---|---|---|
| GET | `/api/health` | 공개 | `{ok:true, version:"1.9.16", db:"ok", time:"..."}` |
| GET | `/api/meta` | 공개 | `{version, schema_version, free_shipping, shipping_fee, claim_fees, grades, point_policies}` |

---

## 4. 서버 스택 & 배포 가이드 (Ubuntu + Nginx + FastAPI + SQLite)

### 4.1 권장 디렉터리

```
/srv/mono-atelier/
├─ app/
│  ├─ main.py           # FastAPI() · 라우터 등록 · 예외 핸들러
│  ├─ deps.py           # current_user · require_admin · csrf · db 연결
│  ├─ db.py             # sqlite3 연결·트랜잭션 헬퍼
│  ├─ security.py       # bcrypt/argon2 · 세션 · 레이트리밋
│  ├─ routers/
│  │  ├─ auth.py products.py categories.py cart.py orders.py payments.py
│  │  ├─ claims.py reviews.py qnas.py coupons.py members.py site.py
│  │  └─ faqs.py logs.py admin.py media.py
│  ├─ services/
│  │  ├─ pricing.py     # totalsOf / shippingOf / couponEligibleBase 이식
│  │  ├─ points.py      # 적립·사용·회수·환급
│  │  ├─ notify.py      # 메일(Resend/SMTP) · SMS
│  │  └─ toss.py        # 승인·취소 (payment_confirm_example.py 이식)
│  └─ models.py         # Pydantic 요청·응답 모델
├─ web/                 # 이 저장소의 shop/ (정적 프론트)
│  ├─ index.html  src/  assets/  data/(스키마·시드, 서빙 제외 권장)
├─ .venv/
└─ .env                 # 600, 서비스 계정 소유

/var/lib/mono-atelier/
├─ mono-atelier.db      # SQLite (WAL)
└─ media/YYYY/MM/...    # 업로드

/var/log/mono-atelier/  # audit.log · app.log · nginx
/var/backups/mono-atelier/
```

> **중요**: `web/data/`(시드 JSON·`mono-atelier.db`)와 `web/src/` 는 **Nginx 로 서빙하지 마세요.** 정적 루트는 `web/` 이되 `location ~ ^/(data|src)/ { deny all; }` 로 막습니다(시드에 회원 예시 데이터가 있음).

### 4.2 패키지 설치 (Ubuntu 22.04/24.04)

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip nginx sqlite3 rsync ufw

sudo useradd -r -s /usr/sbin/nologin -d /srv/mono-atelier mono
sudo mkdir -p /srv/mono-atelier /var/lib/mono-atelier/media /var/log/mono-atelier /var/backups/mono-atelier
sudo chown -R mono:mono /srv/mono-atelier /var/lib/mono-atelier /var/log/mono-atelier /var/backups/mono-atelier

sudo -u mono python3.12 -m venv /srv/mono-atelier/.venv
sudo -u mono /srv/mono-atelier/.venv/bin/pip install --upgrade pip
sudo -u mono /srv/mono-atelier/.venv/bin/pip install \
  fastapi==0.115.* uvicorn[standard]==0.32.* pydantic==2.* \
  python-multipart bcrypt pillow \
  itsdangerous httpx
# argon2 를 쓸 경우: argon2-cffi
```

### 4.3 DB 초기화 (스키마 + 시드)

```bash
# 1) 저장소에서 shop/ 를 /srv/mono-atelier/web 로 배치했다고 가정
cd /srv/mono-atelier/web/data

# 2) DB 생성 (schema.sql + schema-seed.json → mono-atelier.db)
sudo -u mono python3 build_sqlite.py --out /var/lib/mono-atelier/mono-atelier.db
# 출력에 테이블별 행 수와 검증 결과(FK·금액 불일치·재고·포인트 합계)가 찍립니다.

# 3) 운영 스키마 보강 (이 문서에서 확인된 3건) — 1회만
sudo -u mono sqlite3 /var/lib/mono-atelier/mono-atelier.db <<'SQL'
ALTER TABLE users ADD COLUMN address_detail TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN expires_at TEXT;                      -- pending_payment 만료
CREATE TABLE IF NOT EXISTS coupon_redemptions (                      -- 쿠폰 사용 이력 (V10)
  id         TEXT PRIMARY KEY,
  coupon_id  TEXT NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  order_id   TEXT NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_redemptions_user ON coupon_redemptions(coupon_id, user_id);
CREATE TABLE IF NOT EXISTS sessions (                                -- 세션 저장(V6)
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf_token TEXT NOT NULL,
  ip         TEXT NOT NULL DEFAULT '',
  ua         TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
SQL

# 4) 기동 전 점검
sudo -u mono sqlite3 /var/lib/mono-atelier/mono-atelier.db "PRAGMA integrity_check; PRAGMA foreign_key_check;"
```

- **기존 `payment_confirm_example.py` 는 `orders` 에 `payment_provider`/`payment_key`/`payment_mode` 를 자동 추가**합니다(`ensure_columns`). 스키마에 이미 있으므로 중복 실행해도 무해합니다.
- 시드 비밀번호(`sha256`)는 **첫 로그인 시 bcrypt 로 자동 재해시**하도록 구현하세요(기존 `password_hash` 가 64자 hex 면 legacy 로 판정). 운영 배포에서는 **시드 계정 비밀번호를 즉시 변경**하고 `member*@mono.kr` 계정은 비활성화하세요.
- `admin` 초기 비밀번호는 `.env` 의 `ADMIN_INIT_PASSWORD` 로 1회 설정 → 로그인 → 변경 → `.env` 에서 삭제.

### 4.4 `.env` (필수 환경변수)

전체 목록은 저장소의 **`shop/.env.example`** 을 그대로 복사해서 값을 채우세요. 반드시 있어야 하는 항목만 요약하면:

| 변수 | 필수 | 설명 |
|---|---|---|
| `SESSION_SECRET` | ✅ | 세션 쿠키 서명/암호화 키. `openssl rand -base64 48`. 없으면 기동 실패 |
| `MONO_DB` | ✅ | SQLite 절대 경로 |
| `TOSS_SECRET_KEY` | ✅(결제) | `test_sk_…`/`live_sk_…`/`live_gsk_…`. **서버에만** |
| `TOSS_CLIENT_KEY` | ✅(결제) | `test_gck_…`. 프론트에 내려보내는 공개 키 |
| `ADMIN_INIT_EMAIL`·`ADMIN_INIT_PASSWORD` | ✅(최초 1회) | 초기 관리자 생성·비밀번호 재설정 |
| `MAIL_API_KEY`·`MAIL_FROM` | ✅(메일) | 인증번호·주문 안내 발송 |
| `SMS_API_KEY`·`SMS_SENDER` | ⬜(SMS) | 주문 완료 문자 |
| `MEDIA_ROOT` | ✅ | 업로드 저장 경로 |
| `CORS_ORIGINS` | ⬜ | 프론트를 다른 도메인에서 서빙할 때만 |
| `ALLOW_DEMO_PAYMENT_FALLBACK` | ✅ | **운영은 `0`** (서버 승인 없는 결제 확정 금지) |
| `ALLOW_TEST_OTP_ECHO` | ✅ | **운영은 `0`** (화면에 인증번호 노출 금지) |

- 파일 권한: `chown mono:mono /srv/mono-atelier/.env && chmod 600 /srv/mono-atelier/.env`
- `.gitignore` 에 `.env`, `*.db`, `media/` 를 추가. **저장소에는 `.env.example` 만** 둡니다.
- 토스 클라이언트 키는 이미 `src/app.js` 의 `PAYMENT_CONFIG`(131) 에 **공개 테스트 키**가 들어 있습니다(문서용 공개 키, 시크릿 아님). 운영에서는 `/api/meta` 로 내려주거나 `TOSS_CLIENT_KEY` 값을 프론트 빌드 시 주입하세요. **`…gsk_`/`…sk_` 는 절대 프론트로 내려보내지 않습니다.**

### 4.5 FastAPI 골격(핵심 부분만)

```python
# db.py
import sqlite3, os, contextlib
DB = os.environ["MONO_DB"]

def connect():
    conn = sqlite3.connect(DB, isolation_level=None, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

@contextlib.contextmanager
def tx():
    """쓰기 트랜잭션 — BEGIN IMMEDIATE 로 잠금을 먼저 잡아 경쟁을 직렬화한다."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
```

```python
# deps.py
import os, secrets
from fastapi import Cookie, Depends, HTTPException, Request
from db import connect

COOKIE = os.environ.get("SESSION_COOKIE_NAME", "mono_session")

def current_user(session_id: str | None = Cookie(default=None, alias=COOKIE)):
    if not session_id:
        return None
    conn = connect()
    row = conn.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.id = ? AND s.expires_at > datetime('now')", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user

def require_admin(user=Depends(require_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "관리자만 접근할 수 있습니다.")
    return user

def require_csrf(request: Request, user=Depends(require_user)):
    """상태 변경 요청은 X-CSRF-Token 헤더가 세션의 토큰과 일치해야 한다."""
    if os.environ.get("CSRF_ENABLED", "1") != "1":
        return user
    token = request.headers.get("x-csrf-token", "")
    conn = connect()
    row = conn.execute("SELECT csrf_token FROM sessions WHERE id = ?",
                       (request.cookies.get(COOKIE),)).fetchone()
    conn.close()
    if not row or not secrets.compare_digest(row["csrf_token"], token):
        raise HTTPException(403, "요청 검증에 실패했습니다. 새로고침 후 다시 시도해 주세요.")
    return user
```

```python
# security.py (발췌)
import bcrypt, secrets, datetime as dt

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(pw: str, stored: str) -> tuple[bool, bool]:
    """returns (ok, needs_rehash) — 64자 hex 면 legacy sha256 시드"""
    if len(stored) == 64 and all(c in "0123456789abcdef" for c in stored):
        legacy = hashlib.sha256((os.environ.get("LEGACY_PEPPER", "mono-atelier$") + pw).encode()).hexdigest()
        return (secrets.compare_digest(legacy, stored), True)
    return (bcrypt.checkpw(pw.encode(), stored.encode()), False)

def new_session(conn, user_id: str, ip: str, ua: str) -> tuple[str, str]:
    sid = secrets.token_urlsafe(32); csrf = secrets.token_urlsafe(24)
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=int(os.environ["SESSION_TTL_HOURS"])))
    conn.execute("INSERT INTO sessions(id,user_id,csrf_token,ip,ua,created_at,expires_at) VALUES(?,?,?,?,?,?,?)",
                 (sid, user_id, csrf, ip, ua[:300], dt.datetime.now(dt.timezone.utc).isoformat(), expires.isoformat()))
    return sid, csrf
```

- 쿠키 설정: `response.set_cookie(COOKIE, sid, httponly=True, secure=(SESSION_COOKIE_SECURE=='1'), samesite='lax', max_age=ttl, path='/')`
- **모든 쓰기 라우터**에 `user=Depends(require_csrf)`.
- 예외 핸들러에서 `sqlite3.IntegrityError` → 409, `HTTPException` → 그대로, 그 외 → 500 + `{ok:false, code:'SERVER_ERROR'}` (스택은 로그에만).

### 4.6 systemd

```ini
# /etc/systemd/system/mono-atelier.service
[Unit]
Description=MONO ATELIER API (FastAPI)
After=network.target

[Service]
Type=simple
User=mono
Group=mono
WorkingDirectory=/srv/mono-atelier/app
EnvironmentFile=/srv/mono-atelier/.env
ExecStart=/srv/mono-atelier/.venv/bin/uvicorn main:app \
  --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3
# 보안 하드닝
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/mono-atelier /var/log/mono-atelier
StateDirectory=mono-atelier
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mono-atelier
sudo systemctl status mono-atelier --no-pager
curl -s http://127.0.0.1:8000/api/health
```

> **SQLite + uvicorn worker**: `--workers 1` 을 권장합니다(쓰기 직렬화·세션 일관성). 트래픽이 늘면 ① `uvicorn --workers 1` + `--limit-concurrency` ② SQLite WAL 유지 ③ 그래도 부족하면 PostgreSQL 이전(스키마 동일, `sqlite3` 호출부만 교체).

### 4.7 Nginx (리버스 프록시 + 정적 + 보안 헤더)

```nginx
# /etc/nginx/sites-available/mono-atelier
server {
    listen 80;
    server_name shop.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name shop.example.com;

    ssl_certificate     /etc/letsencrypt/live/shop.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/shop.example.com/privkey.pem;

    root /srv/mono-atelier/web;
    index index.html;
    client_max_body_size 25m;              # 동영상 업로드

    # ---- 보안 헤더 (전 구간)
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; script-src 'self' https://js.tosspayments.com; connect-src 'self' https://api.tosspayments.com; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" always;

    # ---- 소스·시드·DB 는 절대 서빙 금지
    location ~ ^/(src|data|\.git)/ { deny all; return 404; }

    # ---- API
    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_buffering    off;
    }

    # ---- 업로드 파일
    location /media/ {
        alias /var/lib/mono-atelier/media/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff always;
        location ~* \.(php|py|sh|html?)$ { deny all; }
    }

    # ---- 정적
    location / {
        try_files $uri $uri/ /index.html;
        expires 1h;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/mono-atelier /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo ufw allow 'Nginx Full' && sudo ufw enable
```

> **CORS 가 필요한 경우**는 프론트를 `https://chaeci.github.io/shop/` 에 그대로 두고 API 만 내부서버에 둘 때뿐입니다. 그때는 `CORS_ORIGINS=https://chaeci.github.io` + `allow_credentials=True` 로 **그 오리진만** 허용하고, 쿠키는 `SameSite=None; Secure` 가 되어야 하므로 **CSRF 토큰을 반드시** 켭니다. **권장 구성은 같은 도메인**(`shop.example.com` 에서 `/api/`)입니다.

### 4.8 프론트(`src/app.js`)의 `DB` 계층을 `fetch('/api/...')` 로 교체하기

#### 4.8.1 현재 구조의 성격

- `db` 는 **21테이블 전체를 담은 전역 객체**이고, 모든 함수가 **동기**로 `db.users.filter(...)` 처럼 직접 읽습니다.
- 그래서 "한 줄만 바꿔 fetch" 식의 교체는 불가능합니다. **읽기·쓰기 지점을 화면 단위로 끊어** 교체해야 합니다.

#### 4.8.2 권장 전략 — "뷰 단위 점진 교체"

1. `src/api.js` 를 추가하고 `index.template.html` 에 `<script src="api.js"></script>` 를 넣습니다(빌드는 `build.py` 에 목록 추가).
2. `db` 는 **현재 화면이 필요로 하는 데이터의 캐시**로 유지합니다(전체 DB가 아님).
3. 각 뷰 진입 시 `await loadView()` 로 API 를 호출해 캐시를 채우고, **기존 렌더 함수는 그대로** 씁니다.
4. 쓰기 함수는 ① `await API.post(...)` ② 성공 시 관련 캐시만 갱신 ③ `renderAll()` — 이 순서로 바꿉니다.

```js
// src/api.js
const CSRF = document.querySelector('meta[name=csrf-token]')?.content || '';
const API = {
  async req(method, path, body) {
    const isForm = body instanceof FormData;
    const res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: isForm ? { 'X-CSRF-Token': CSRF }
                      : { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF },
      body: isForm ? body : (body == null ? undefined : JSON.stringify(body)),
    });
    if (res.status === 204) return { ok: true };
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.message || '요청을 처리하지 못했습니다.');
      err.status = res.status; err.code = data.code; err.field = data.field;
      throw err;
    }
    return data;
  },
  get: (p) => API.req('GET', p),
  post: (p, b) => API.req('POST', p, b || {}),
  put: (p, b) => API.req('PUT', p, b || {}),
  patch: (p, b) => API.req('PATCH', p, b || {}),
  del: (p) => API.req('DELETE', p),
};
```

#### 4.8.3 교체 순서(같은 순서로 작업하면 화면이 계속 동작합니다)

| 단계 | 교체할 함수(줄) | 새 호출 | 비고 |
|---|---|---|---|
| 1 | `boot` 12824 · `loadDB` 654 | `GET /api/bootstrap` + `GET /api/auth/me` | `SEED` 폴백 제거. `boot` 를 `async` 로 |
| 2 | `login` 1768 · `signup` 1777 · `logout` 1890 · `openAuth` 9895 | `/api/auth/*` | 실패 메시지·필드 유지 |
| 3 | `sendEmailCode` 3287 · `verifyEmailCode` 3324 | `/api/auth/email-code*` | `ui.emailAuth` 는 **토큰 보관용**으로만 |
| 4 | `visibleProducts` 2959 · `productById` 872 · `openProduct` 4591 | `/api/products*` | 상세는 열 때 로드 |
| 5 | `cartRows` 1334 · `addToCart` 1911 · `setCartQty` 1933 · `removeCartItems` 1955 | `/api/cart*` | 합계는 서버 `totals` 사용 |
| 6 | `buildPending` 2055 → **`prepareOrder()`** | `POST /api/orders/prepare` | **클라이언트 금액 계산 제거** |
| 7 | `confirmPayment` 2316 · `handlePaymentReturn` 2346 | `POST /api/payments/confirm` | `tossFallback`(2161) **삭제** |
| 8 | `cancelOrder` 2431 · `confirmOrderItem` 3677 | `/api/orders/{id}/cancel` · `/confirm-items` | 응답의 `restored`·`refunded` 표시 |
| 9 | `buildClaim` 1057 · `finalizeClaim` 1096 · `handleClaimReturn` 2384 | `/api/claims/*` | 배송비 결제도 서버 승인 |
| 10 | `productReviews` 3736 · `addReview` 3872 · `toggleReviewVote` 3769 | `/api/products/{id}/reviews` · `/api/reviews*` | `reviewableItems` 도 서버 |
| 11 | `productQnas` 4831 · `qnaItemHTML` 4856 · `submitQna` 4931 | `/api/products/{id}/qnas*` | **`locked` 플래그**로 마스킹 렌더 |
| 12 | `couponsForUser` 1281 · `applyCouponCode` 5562 | `/api/coupons/mine` · `/validate` | 사유 문자열 그대로 표시 |
| 13 | `saveProduct` 2533 · `toggleProductActive` 2646 · `soldoutProduct` 2653 | `/api/products` (multipart) | 업로드 → `/api/media` |
| 14 | `resizeImageFile` 9801 · `handleImageUploads` 9830 · `handleReviewMedia` 9871 | `POST /api/media` | 클라이언트 축소는 유지해도 되지만 **원본 검증은 서버** |
| 15 | 관리자 목록·페이징(`adminPagerInfo` 6442 등 12종) | `/api/admin/*` + `page` | **서버 페이징으로 교체** |
| 16 | `siteSettings` 3057 · `saveSiteSettings` 3177 · 사이트 미디어 5종 | `/api/site` · `/api/admin/site*` | 공개/관리자 필드 분리 |
| 17 | `saveFaqs` 4122 · `saveFaqItem` 7089 · `saveFaqCategories` 4061 | `/api/faqs*` | — |
| 18 | `notifySettings` 3236 · `sendOrderSms` 3420 · `dispatchLogsOf` 3353 | `/api/logs*` | 발송은 서버만 |
| 19 | `exportPayload` 2663 · `resetDB` 2694 | `/api/admin/data/*` | 초기화는 비활성 권장 |

#### 4.8.4 결제 부분 교체 예(가장 중요한 변경)

```js
// 기존: const pending = buildPending(payload); savePending(pending); requestTossPayment(pending, user);
async function prepareOrder(payload) {
  const r = await API.post('/api/orders/prepare', {
    cart_ids: ui.checkoutIds,
    coupon_code: ui.coupon ? ui.coupon.code : null,
    points_to_use: ui.pointUse,
    recipient_name: payload.recipient_name,
    recipient_phone: payload.recipient_phone,
    postcode: payload.postcode,
    shipping_address: payload.shipping_address,
    payment_method: ui.payMethod,
  });
  if (r.amount === 0) { const done = await API.post('/api/orders/free', { order_no: r.order_no }); return showReceipt(done.order); }
  return requestTossPayment({ order_no: r.order_no, amount: r.amount, order_name: r.order_name }, r.customer_key);
}

// 복귀(?tossResult=success) 후 — 금액은 서버가 대조하므로 orderId/amount 만 넘긴다
async function confirmPayment(info) {
  const r = await API.post('/api/payments/confirm',
    { paymentKey: info.paymentKey, orderId: info.orderId, amount: info.amount });
  toast(r.duplicate ? '이미 확정된 결제입니다.' : '결제가 완료되었습니다.');
  const o = await API.get('/api/orders/' + encodeURIComponent(info.orderId));
  showReceipt(o.order);
}
```

- `LS_PENDING`(2010)·`LS_PENDING_CLAIM`(1167)는 **더 이상 필요 없습니다**(서버가 준비 주문을 보관). 제거하세요.
- `PAYMENT_CONFIG.confirmApiUrl` 은 **항상 `/api/payments/confirm`** 로 고정하고, `tossAvailable()/tossFallback()` 의 **데모 결제 분기**를 삭제합니다.
- `hashPw`/`sha256Hex`(609·646)는 **프론트에서 제거**(비밀번호가 브라우저에서 해시되지 않아야 함: HTTPS 로 서버에 전송).

#### 4.8.5 비동기 전환 시 UI 주의

- `renderAll()` 은 동기 렌더러입니다. **데이터 로드 → `renderAll()`** 순서를 지키고, 로딩 중에는 기존 화면을 유지하세요(스켈레톤 불필요).
- 버튼 중복 클릭 방지: `data-action` 핸들러(10430)에서 `await` 전에 `btn.disabled = true` 후 `finally` 복원.
- 실패 토스트는 **서버 `message` 를 그대로** 표시(§1.7 의 사유 문구가 사용자에게 보이는 문장입니다).
- `history` 기반 모달 복원(`applyRoute` 1651)은 **모달 데이터가 서버에서 와야** 하므로, 복원 시 `GET` 후 `renderModal()` 하도록 바꿉니다(현재는 `db` 에서 즉시 찾음).

### 4.9 배포 절차

```bash
# 1) 코드 반영(정적 프론트 + 스키마)
sudo rsync -a --delete /path/to/chaeci.github.io/shop/ /srv/mono-atelier/web/ \
  --exclude data/mono-atelier.db --exclude .git
sudo chown -R mono:mono /srv/mono-atelier/web

# 2) 스키마 변경이 있으면 백업 후 마이그레이션
sudo -u mono sqlite3 /var/lib/mono-atelier/mono-atelier.db ".backup '/var/backups/mono-atelier/pre-deploy.db'"
sudo -u mono /srv/mono-atelier/.venv/bin/python /srv/mono-atelier/app/migrate.py

# 3) 재시작·확인
sudo systemctl restart mono-atelier
curl -sf http://127.0.0.1:8000/api/health | head -c 200
sudo nginx -t && sudo systemctl reload nginx
```

- 마이그레이션은 **멱등**(`IF NOT EXISTS`, `PRAGMA table_info` 확인)으로 작성하고 `migrate.py` 한 곳에 모읍니다.
- 롤백: ① `systemctl stop` ② 백업 DB 복원 ③ 이전 코드로 `rsync` ④ `start`.

### 4.10 운영(백업·로그·모니터링)

```bash
# 일 1회 백업 (cron 03:10)
0 3 * * * mono sqlite3 /var/lib/mono-atelier/mono-atelier.db ".backup '/var/backups/mono-atelier/db-$(date +\%F).db'" \
  && find /var/backups/mono-atelier -name 'db-*.db' -mtime +14 -delete

# 업로드 백업(주 1회)
0 4 * * 0 rsync -a /var/lib/mono-atelier/media/ /var/backups/mono-atelier/media/
```

- **로그 로테이션**(`/etc/logrotate.d/mono-atelier`): `app.log`, `audit.log`, nginx 로그 주 1회 rotate, 8주 보관.
- **헬스체크**: `/api/health` 를 5분 간격으로 감시(200 + `db:"ok"`).
- **지표 최소셋**: 응답시간 p95, 5xx 비율, 결제 승인 실패 수, 발송 실패 수, DB 파일 크기.
- **개인정보 접근 감사**: 데이터 내보내기·회원 상세 열람·권한 변경은 `audit.log` 에 `who, when, what, target` 을 남깁니다.

---

## 5. 구현 순서 · 수용 기준

### 5.1 마일스톤

| 단계 | 내용 | 완료 조건 |
|---|---|---|
| **M0** | 환경·DB | §4.2~4.3 실행. `build_sqlite.py` 로그의 테이블별 건수가 §1.3 과 일치, `integrity_check=ok`, `foreign_key_check` 0건 |
| **M1** | 인증·세션 | bcrypt 로그인, HttpOnly 쿠키, `GET /api/auth/me`, 관리자 403. **프론트 로그인/로그아웃이 서버 세션으로 동작** |
| **M2** | 카탈로그 읽기 | `/api/bootstrap`·`/api/products`·`/api/categories`·`/api/site`·`/api/faqs` 로 **스토어 홈·상품 상세·FAQ가 서버 데이터로 렌더** |
| **M3** | 주문·결제 | `/api/cart` → `prepare` → (토스) → `confirm`. 재고 차감·포인트 사용·쿠폰 사용·장바구니 비우기가 **한 트랜잭션** |
| **M4** | 회원 기능 | 마이페이지(주문·포인트·쿠폰), 구매확정, 교환/반품, 리뷰·Q&A·추천 |
| **M5** | 관리자 | 14탭 목록·상세·상태 변경·일괄 처리·사이트/FAQ/코드 관리·발송 로그·매출 |
| **M6** | 마감 | §5.2 전항 통과, 백업·감사 로그·헬스체크·`.env` 점검, 시드 관리자 비밀번호 변경 |

### 5.2 수용 테스트

#### 5.2.1 보안 (S) — **하나라도 실패하면 배포 금지**

| # | 시나리오 | 기대 결과 |
|---|---|---|
| S-1 | `curl -s https://<host>/ \| grep -c "demo@mono.kr\|member1@mono.kr"` | `0` |
| S-2 | 브라우저 개발자도구 localStorage 확인 | 회원·주문 데이터 없음(세션 쿠키만) |
| S-3 | `GET /api/orders` 비로그인 | `401` |
| S-4 | 고객 세션으로 `GET /api/admin/orders` | `403` |
| S-5 | 고객 A 세션으로 `GET /api/orders/{B의 주문 id}` | `404`(또는 403) |
| S-6 | 고객 세션으로 `PATCH /api/orders/{id}/status` | `403` |
| S-7 | 비로그인 `GET /api/products/{p_001}/qnas` 에 비밀글 포함 | 해당 항목에 `title`·`content`·`answer` **키 없음**, `locked:true` |
| S-8 | 다른 회원 세션으로 비밀글 조회 | 동일(마스킹) |
| S-9 | 작성자 본인 세션으로 비밀글 조회 | 전문 노출 |
| S-10 | `mysql`/`sqlite3` 로 `users.password_hash` 확인 | `$2b$12$…` 또는 `$argon2id$…` (sha256 hex 아님) |
| S-11 | 로그인 응답·`/api/auth/me`·`/api/admin/members` | `password_hash` 키 없음 |
| S-12 | 쿠키 확인 | `HttpOnly; Secure; SameSite=Lax` |
| S-13 | 세션 쿠키 값을 `user_id=u_002` 로 변조 | 인증 실패(서명/서버 세션) |
| S-14 | `POST /api/payments/confirm` 에 `amount` 를 100원 낮춰 요청 | `402 AMOUNT_MISMATCH`, 토스 승인 호출 로그 없음, 주문 `pending_payment` 유지 |
| S-15 | 같은 `paymentKey` 로 2회 confirm | 2번째 `200 {duplicate:true}`, 재고 1회만 차감 |
| S-16 | 재고 1개 옵션을 2명이 동시에 결제 | 1명 성공, 1명 `409 OUT_OF_STOCK`, `stock` 음수 없음 |
| S-17 | `POST /api/orders/prepare` 에 `points_to_use=999999999` | 서버가 `min(보유, 금액)` 으로 보정, 음수 잔액 없음 |
| S-18 | 같은 쿠폰으로 두 번 결제 | 정책에 따라 2번째 `409`(1인 1회) — 최소한 **사용 이력이 남는다** |
| S-19 | 리뷰 반려 API 에 빈 사유 | `400`, 회수 없음 |
| S-20 | 타인 리뷰에 추천 + 본인 리뷰 추천 | 타인 성공 / 본인 `400` |
| S-21 | 관리자 아닌 세션으로 `POST /api/products` | `403` |
| S-22 | `POST /api/media` 에 `.php`, `.svg`, 10MB 파일 | `415` / `413` |
| S-23 | 업로드된 파일 URL 직접 접근 | 이미지로만 서빙, `X-Content-Type-Options: nosniff` |
| S-24 | 리뷰 본문에 `<script>alert(1)</script>` | 저장·표시 시 실행되지 않음(이스케이프/제거), CSP 위반 로그 |
| S-25 | 로그인 6회 연속 실패 | 6번째 `429`, 계정 존재 여부가 메시지로 구분되지 않음 |
| S-26 | `GET /api/admin/data/export` | 관리자만, `audit.log` 에 기록, `Cache-Control: no-store` |
| S-27 | `grep -rn "sk_\|gsk_\|api_key\|MAIL_API_KEY" src/ index.html` | 실제 시크릿 `0`건(공개 테스트 클라이언트 키만) |
| S-28 | `GET /api/site` 응답 | `email_api_url`·`sms_api_url` 등 내부 설정 없음 |

#### 5.2.2 기능 (F) — 시드 데이터 기준

테스트 계정: `demo@mono.kr / demo1234`(GOLD·4,725P) · `admin@mono.kr / admin1234` · 상품 13종(옵션 88) · 주문 21건 · 리뷰 14 · Q&A 15 · FAQ 8 · 쿠폰 4(전용 1).

| # | 시나리오 | 기대 결과 |
|---|---|---|
| F-1 | 홈 진입 | 상품 카드 12개 + `12 ITEMS`, 카테고리 칩·검색·정렬 동작 |
| F-2 | 상품 상세(p_001) | 이미지 3장 스와이프, 모델 정보, 옵션 3색×4사이즈, 재고 표시 |
| F-3 | 장바구니 담기 → 수량 변경 → 선택 삭제 | 합계·배지·서버 `cart_items` 일치 |
| F-4 | 10만원 미만 단일 상품 결제 | 배송비 3,000원 1회 |
| F-5 | 무료배송 기준 충족 상품만 | 배송비 0원 |
| F-6 | 쿠폰 `GOLD20`(골드+잡화·아우터+BEST 20%) | 조건 상품 금액에만 20% 적용, 조건 불충족 시 사유 문구 |
| F-7 | 포인트 2,000P 사용 | 결제 금액 −2,000, `point_logs(type=use)` 1건 |
| F-8 | 결제 확정 | 주문 `paid`, 재고 차감, 장바구니 비움, 영수증 표시 |
| F-9 | 결제 취소(관리자) | 재고 복구 1회 + 포인트 환급 1회, `cancelled` |
| F-10 | 배송완료 + 구매확정 | `confirm_points = floor(실결제금액 × 등급률)`, 잔액 증가 |
| F-11 | 같은 항목 재구매확정 시도 | 차단(중복 지급 없음) |
| F-12 | 배송완료·미확정 항목 리뷰 작성 | 차단 + 안내 문구 |
| F-13 | 구매확정 후 포토 리뷰 | `photo_bonus` 1회 지급, 리뷰 `published` |
| F-14 | 리뷰 반려(사유) | 비노출, 회수 = `min(보너스, 보유)`, 회수 내역 표시 |
| F-15 | 반려 리뷰 재작성 | `attempt=2` 1회 허용, 2차 반려 후 차단 |
| F-16 | 리뷰 추천/비추천 | 1인 1표(전환 가능), 추천순 정렬 |
| F-17 | 리뷰 페이징 | 5건씩, 1/3 페이지 |
| F-18 | Q&A 작성(비밀글) | 본인·관리자만 전문, 타인은 제목까지 마스킹 |
| F-19 | 관리자 Q&A 답변 | `answered` 전환, 상품 상세 즉시 반영 |
| F-20 | 반품 신청(단순 변심) | 3,000원 결제 후 `requested` |
| F-21 | 교환 신청(사이즈 변경) | 6,000원, 재고 있는 교환 옵션만 선택 |
| F-22 | 제품 하자 반품 | 0원 즉시 접수(`free`) |
| F-23 | 반품 완료 처리 | 재고 1회 복구, 재처리 시 중복 복구 없음 |
| F-24 | 마이페이지 보유 쿠폰 | 공용 + `VIP15`(전용) 표시 |
| F-25 | 회원가입 | OTP 없이 가입 불가, 비밀번호 정책 6항목 ✓/✗ |
| F-26 | 가입 실패 후 재시도 | 입력값 유지 |
| F-27 | 관리자 주문 일괄 상태 변경 | 변경·제외 건수, 취소 시 재고·포인트 1회 처리 |
| F-28 | 관리자 목록 12종 | 10건 페이징 + 연속 순번, 필터 변경 시 1페이지 |
| F-29 | 매출 관리 | 취소 제외 실매출, 일/월 버킷, 무매출 구간 제외 |
| F-30 | 사이트 설정 저장 | 타이틀·푸터·히어로·스토리·배지 즉시 반영, 새로고침 유지 |
| F-31 | 사이트 미디어 | 적용 중 사진 삭제 차단, 24장 상한 |
| F-32 | 카테고리 숨김 | 스토어 필터에서만 제외 |
| F-33 | 뱃지 이름 변경 | 상품·쿠폰 조건에 전파 |
| F-34 | FAQ 카테고리 이름 변경 | 연결 FAQ 이동, 연결된 카테고리 삭제 차단 |
| F-35 | 발송 로그 | 채널·상태 필터, 키워드, 쿨다운 차단(`blocked`) 기록 |
| F-36 | 멤버십 자동 적용 | 최근 6개월 구매액 기준, 관리자 계정 제외 |
| F-37 | 모바일 412px | 모든 화면 가로 넘침 0, 관리자 그리드 셀 겹침 0 |
| F-38 | 새로고침(F5) | 보던 마이페이지·관리자 탭 유지(`#/admin/orders` 등) |
| F-39 | 브라우저 뒤로가기 | 모달만 닫히고 목록·필터 유지 |
| F-40 | 강제 다크모드(삼성 인터넷) | 장바구니·배지 대비 유지 |

> 기존 정적 데모의 회귀 검사 스크립트가 필요하면 저장소 밖 원본 `fashion-shop/tests/verify_deploy.py`(Playwright, HTTP 200 + 콘솔 에러 0 + 개인정보 0 검사)와 `tests/e2e_fashion_shop.py`(E2E 1,666항목)를 참고하세요. **공개 저장소에는 포함하지 않았습니다.**

### 5.3 소유자 결정이 필요한 항목(구현 중 질문이 생기면 이 목록으로)

| # | 쟁점 | 기본 권장 |
|---|---|---|
| D-1 | 쿠폰 재사용 정책 | **1인 1쿠폰 1회** + `coupon_redemptions` 로 차단 |
| D-2 | `pending_payment` 상태 추가 | `orders.status` CHECK 를 6종으로 확장하거나 `payments` 테이블 분리 |
| D-3 | 결제 취소·환불 범위 | 배송 전 전액 취소만(부분 취소는 2차) |
| D-4 | 시드 계정·데이터 처리 | 운영 배포 시 시드 회원 비활성화, 관리자 비밀번호 변경 |
| D-5 | GitHub Pages 정적 데모 유지 여부 | **유지**(포트폴리오·데모) — 단 시드에 실제 개인정보 금지 |
| D-6 | 개인정보 보존기간 | 주문 5년(전자상거래법), 회원 탈퇴 시 30일 내 파기 |
| D-7 | 관리자 비밀번호 재설정 | 서버 CLI(`reset-admin-password`) 로만 |
| D-8 | 이메일·SMS 실제 발송 개시 시점 | 도메인 SPF/DKIM, 발신번호 사전등록 후 |

---

## 부록 A. `src/app.js` 함수 색인

> 줄 번호는 v1.9.16 기준. 이관 체크리스트로 쓰세요(다 옮겼으면 서버에서 같은 이름의 함수/라우터가 있어야 합니다).

| 영역 | 함수(줄) |
|---|---|
| 결제 설정 | `normalizePaymentConfig` 149 · `loadPaymentConfig` 163 · `applyPaymentConfig` 174 · `savePaymentConfig` 182 · `resetPaymentConfig` 190 · `maskKey` 6263 |
| 카테고리 | `categories` 205 · `categoryActive` 211 · `storeCategories` 212 · `sizeCodesOf` 476 · `sizeOptionsFor` 488 |
| 회원 등급 | `GRADES` 216 · `gradeOf` 223 · `gradeLabel` 227 · `gradeForSpend` 7616 |
| 색상 | `normalizeHex` 258 · `colorHexFromName` 269 · `nearestColorName` 324 · `sampleImageColors` 367 · `extractColorLayerPalette` 9656 |
| 유틸 | `esc` 552 · `won` 557 · `fmtDate` 559 · `fmtDateTime` 564 · `newId` 596 · `timeOf` 572 |
| 해시 | `sha256Hex` 609 · `hashPw` 646 **(서버로 대체)** |
| DB | `loadDB` 654 · `migrateDB` 664 · `mergeSeedRows` 824 · `save` 848 · `quotaMessage` 852 |
| 세션 | `loadSession` 855 · `saveSession` 859 · `currentUser` 865 · `isAdmin` 869 |
| 상품 | `productById` 872 · `nextProductCode` 877 · `productCodeTaken` 885 · `productByCode` 893 · `variantById` 898 · `variantsOf` 899 · `stockOf` 902 · `colorsOf` 905 · `sizesOf` 918 · `findVariant` 923 · `discountPct` 928 · `productBadge` 932 · `productImages` 956 · `freeShipThresholdOf` 968 · `shippingLabelOf` 974 |
| 금액 | `shippingOf` 981 · `totalsOf` 1352 · `orderItemNetAmount` 3663 |
| 주문 | `orderItemsOf` 1001 · `orderById` 1004 · `makeOrderNo` 1986 · `orderNameOf` 2040 · `stockProblem` 2045 · `buildPending` 2055 · `finalizeOrder` 2085 · `receiptHTML` 9967 · `orderCardHTML` 6050 · `orderDetailHTML` 6083 |
| 클레임 | `claimById` 1007 · `claimOfOrder` 1008 · `claimFeeOf` 1011 · `claimBlockReason` 1020 · `canClaim` 1032 · `makeClaimId` 1047 · `buildClaim` 1057 · `finalizeClaim` 1096 · `updateClaimStatus` 1131 · `bulkUpdateClaimStatus` 1150 · `claimModalHTML` 10129 |
| 쿠폰 | `couponByCode` 1181 · `couponExpired` 1186 · `couponActive` 1191 · `activeCoupons` 1192 · `couponTargets` 1201 · `couponTargetGrades` 1208 · `couponIsPublic` 1213 · `couponTargetCategories` 1215 · `couponTargetBadges` 1224 · `couponEligibleBase` 1238 · `couponForUser` 1259 · `couponsForUser` 1281 · `couponDiscount` 1288 · `couponCheck` 1295 · `couponUsable` 1318 · `couponHintOf` 1322 · `createCoupon` 8330 · `updateCoupon` 8348 |
| 장바구니 | `cartRows` 1334 · `cartCount` 1346 · `selectedRows` 1349 · `addToCart` 1911 · `setCartQty` 1933 · `removeCartItem` 1947 · `removeCartItems` 1955 · `removeSelectedCartItems` 1970 · `renderCart` 5591 |
| 결제 | `tossAvailable` 2001 · `savePending` 2010 · `loadPending` 2013 · `customerKey` 2023 · `tossReturnUrl` 2151 · `tossFallback` 2161 · `openTossWindow` 2179 · `requestTossPayment` 2208 · `requestTossClaimPayment` 2252 · `startPayment` 2292 · `confirmPayment` 2316 · `handlePaymentReturn` 2346 · `handleClaimReturn` 2384 |
| 주문 상태 | `cancelOrder` 2431 · `updateOrderStatus` 2452 · `applyOrderStatus` 2463 · `bulkUpdateOrderStatus` 2484 |
| 상품 저장 | `normalizeImages` 2508 · `syncProductImages` 2527 · `saveProduct` 2533 · `toggleProductActive` 2646 · `soldoutProduct` 2653 · `readEditor` 9737 · `draftFromProduct` 9452 |
| 데이터 관리 | `exportPayload` 2663 · `exportJSON` 2677 · `resetDB` 2694 · `runIntegrity` 2705 · `storeTableRows` 2846 · `storeTableSummary` 2863 |
| 렌더 | `renderAll` 2878 · `renderHeader` 2893 · `applySiteTitle` 2922 · `renderView` 2948 · `renderShopResults` 4462 · `homeHTML` 4531 · `footerHTML` 4565 · `productModalHTML` 4632 |
| 사이트 | `siteSettings` 3057 · `helpTopics` 3089 · `migrateSiteData` 3125 · `saveSiteSettings` 3177 · `saveHelpTopics` 3214 · `readSiteForm` 8024 · `siteMediaThumbsHTML` 6638 · `addSiteMedia` 6696 · `removeSiteMedia` 6712 · `selectSiteMedia` 6727 |
| 알림 | `notifySettings` 3236 · `saveNotifySettings` 3253 · `newEmailCode` 3276 · `sendEmailCode` 3287 · `verifyEmailCode` 3324 · `buildOrderSmsBody` 3338 · `smsLogsOf` 3344 · `dispatchLogsOf` 3353 · `addDispatchLog` 3359 · `emailCooldownLeft` 3378 · `dispatchAnomalies` 3394 · `sendOrderSms` 3420 |
| 포인트 | `clampRate` 3581 · `pointPolicyMap` 3586 · `pointPolicyOf` 3600 · `userPoints` 3607 · `pointLogsOf` 3618 · `addPointLog` 3623 · `savePointPolicies` 3637 · `adjustMemberPoints` 7808 |
| 구매확정 | `canConfirmItem` 3671 · `confirmOrderItem` 3677 |
| 리뷰 | `reviewsOfOrderItem` 3704 · `reviewAttemptsOf` 3716 · `reviewRewriteAvailable` 3723 · `reviewStats` 3740 · `reviewVoteCounts` 3756 · `toggleReviewVote` 3769 · `sortedProductReviews` 3805 · `reviewableItems` 3844 · `addReview` 3872 · `updateReview` 3948 · `rejectReview` 3981 · `approveReview` 7900 · `reviewReclaimAmount` 7928 · `bulkReclaimReviews` 7936 |
| FAQ | `faqList` 4018 · `faqCategories` 4043 · `saveFaqCategories` 4061 · `filteredFaqs` 4114 · `saveFaqs` 4122 · `saveFaqItem` 7089 · `moveFaqItem` 7125 · `deleteFaqItems` 7139 |
| 주소 | `openAddressSearch` 4230 · `fillAddressFields` 4265 · `readAddressGroup` 4275 |
| Q&A | `qnaById` 4826 · `productQnas` 4831 · `qnaCanRead` 4838 · `qnaItemHTML` 4856 · `submitQna` 4931 · `answerQna` 4957 · `deleteQna` 4971 |
| 상세 모달 | `openProduct` 4591 · `syncProductModal` 5297 · `openLightbox` 5344 · `bindLightboxGestures` 5449 |
| 체크아웃 | `checkoutRows` 5687 · `userAddressParts` 5690 · `pointUseApplied` 5695 · `checkoutHTML` 5719 |
| 마이페이지 | `mypageHTML` 5800 · `profileHTML` 5844 · `couponsHTML` 5877 · `pointReclaimsHTML` 5912 · `pointsHTML` 5933 · `ordersHTML` 6018 |
| 관리자 공통 | `adminSubtabBarHTML` 6173 · `resetAdminFilters` 6308 · `adminFilterChipsHTML` 6426 · `adminPagerInfo` 6442 · `adminPagerHTML` 6459 · `adminSelCellHTML` 6508 · `adminBulkBarHTML` 6543 |
| 관리자 상품 | `adminProductMatches` 6566 · `adminProductList` 6571 · `adminProductTableHTML` 6594 · `adminProductsHTML` 8087 |
| 관리자 사이트 | `adminSiteHTML` 6914 · `siteBannerPanelHTML` 6933 · `storyPanelHTML` 6959 · `siteTitlePanelHTML` 6784 · `siteFooterPanelHTML` 6813 · `siteHelpPanelHTML` 6853 · `siteShopPanelHTML` 6886 |
| 관리자 리뷰/Q&A | `adminReviewList` 7287 · `adminReviewsHTML` 7344 · `adminReclaimHTML` 7253 · `adminQnaList` 7371 · `adminQnasHTML` 7436 · `adminQnaDetailHTML` 7449 |
| 관리자 회원 | `memberList` 7572 · `memberRecentSpend` 7609 · `membershipTargets` 7623 · `saveGradeRulesFromForm` 7632 · `applyMembershipTargets` 7658 · `membershipPanelHTML` 7673 · `adminMemberHTML` 7737 · `saveMemberGrade` 7827 |
| 관리자 쿠폰/카테고리/뱃지 | `adminCouponsHTML` 8229 · `couponInputFrom` 8285 · `createCoupon` 8330 · `updateCoupon` 8348 · `addCategory` 8420 · `deleteCategory` 8473 · `saveCategorySizeCodes` 8496 · `saveBadgeList` 8677 · `renameBadge` 8697 · `adminCodeHTML` 8779 |
| 관리자 클레임/주문 | `adminClaimsBodyHTML` 8812 · `adminClaimSheetHTML` 8878 · `adminOrdersBodyHTML` 9310 · `adminOrderSheetHTML` 9370 |
| 관리자 매출 | `revenuePresetRange` 9042 · `revenueBuckets` 9067 · `revenueSummaryHTML` 9107 · `revenueTrendChartHTML` 9135 · `revenueDetailTableHTML` 9196 · `adminRevenueTabHTML` 9254 |
| 업로드 | `resizeImageFile` 9801 · `handleImageUploads` 9830 · `readVideoFile` 9859 · `handleReviewMedia` 9871 |
| 모달/라우팅 | `renderModal` 10311 · `closeModal` 10342 · `applyRoute` 1651 · `applyHashRoute` 1575 · `syncRoute` 1611 · `pushRouteState` 1570 |
| 부팅 | `boot` 12824 · `migrateColorData` 12795 · `migrateProductCodes` 12805 · `window.__MONO__` 12849 |

---

## 부록 B. 오류 코드

| HTTP | `code` | 의미 | 사용자 문구(예) |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | 입력 검증 실패 (`field` 포함) | "문의 제목을 2자 이상 입력해 주세요." |
| 400 | `PASSWORD_POLICY` | 비밀번호 정책 위반 | "비밀번호에 특수문자(!@#$% 등)를 넣어 주세요." |
| 401 | `LOGIN_REQUIRED` | 로그인 필요 | "로그인이 필요합니다." |
| 401 | `BAD_CREDENTIALS` | 이메일/비밀번호 불일치 | "이메일 또는 비밀번호가 올바르지 않습니다." |
| 403 | `FORBIDDEN` | 권한 없음(관리자 전용) | "관리자만 접근할 수 있습니다." |
| 403 | `CSRF_FAILED` | CSRF 토큰 불일치 | "요청 검증에 실패했습니다. 새로고침 후 다시 시도해 주세요." |
| 404 | `NOT_FOUND` | 없음 또는 접근 불가(존재 숨김) | "주문을 찾을 수 없습니다." |
| 409 | `OUT_OF_STOCK` | 재고 부족 | "‘울 코트 / 차콜 M’ 재고가 부족합니다. (남은 수량 1개)" |
| 409 | `DUPLICATE_EMAIL` | 이메일 중복 | "이미 가입된 이메일입니다. 로그인해 주세요." |
| 409 | `CLAIM_EXISTS` | 클레임 중복 | "이미 접수된 교환/반품 신청이 있습니다." |
| 409 | `CLAIM_NOT_ALLOWED` | 신청 불가 상태 | "배송이 시작된 주문은 취소할 수 없습니다." |
| 409 | `REVIEW_NOT_ALLOWED` | 리뷰 자격 없음 | "구매확정 후에 리뷰를 작성할 수 있습니다." |
| 409 | `REVIEW_REJECTED_FINAL` | 재작성 기회 소진 | "반려된 리뷰의 재작성 기회를 이미 사용했습니다." |
| 409 | `COUPON_NOT_USABLE` | 쿠폰 조건 불충족 (`message` 에 사유) | "사용 조건(잡화·아우터 · BEST)에 해당하는 상품이 장바구니에 없습니다." |
| 409 | `COUPON_ALREADY_USED` | 쿠폰 재사용(V10) | "이미 사용한 쿠폰입니다." |
| 402 | `AMOUNT_MISMATCH` | 결제 금액 불일치 | "결제 금액이 주문 금액과 다릅니다." |
| 402 | `PAYMENT_FAILED` | 토스 승인 실패 | "결제 승인에 실패했습니다." |
| 413 | `PAYLOAD_TOO_LARGE` | 업로드 크기 초과 | "동영상은 20MB 이하만 첨부할 수 있습니다." |
| 415 | `UNSUPPORTED_MEDIA` | MIME/확장자 불가 | "이미지 파일만 업로드할 수 있습니다." |
| 429 | `RATE_LIMITED` | 요청 과다 (`Retry-After`) | "인증번호를 너무 자주 요청했습니다. 42초 후 다시 시도해 주세요." |
| 429 | `OTP_COOLDOWN` | OTP 쿨다운 | 위와 동일 |
| 500 | `SERVER_ERROR` | 내부 오류(상세 미노출) | "잠시 후 다시 시도해 주세요." |

---

## 부록 C. 스키마 보강 목록(이관 시 적용)

| # | 대상 | 변경 | 이유 |
|---|---|---|---|
| C-1 | `users` | `ADD COLUMN address_detail TEXT NOT NULL DEFAULT ''` | 앱이 상세주소를 별도 보관(`signup` 1777) |
| C-2 | `orders.status` | CHECK 에 `pending_payment` 추가(또는 `payments` 테이블) | 서버 준비 주문(§3.6) |
| C-3 | `orders` | `ADD COLUMN expires_at TEXT` | 준비 주문 만료 |
| C-4 | `coupon_redemptions` | 신규 테이블(부록 §4.3 SQL) | 쿠폰 사용 이력(V10) |
| C-5 | `sessions` | 신규 테이블(§4.3 SQL) | 서버 세션(V6) |
| C-6 | `product_variants.size` | CHECK 완화 또는 사이즈 코드 검증으로 대체 | 카테고리별 사이즈(95·28 등) |
| C-7 | `product_reviews` | `ADD COLUMN media_mime TEXT`(선택) | 업로드 파일 검증 감사용 |
| C-8 | `audit_logs`(파일 또는 테이블) | 신규 | 관리자 행위 감사(§2.13) |
| C-9 | 인덱스 | `orders(status, created_at)`, `product_qnas(product_id, is_secret)`, `point_logs(user_id, created_at)` | 목록 성능 |

---

## 부록 D. 시드 데이터 · 테스트 기준값

| 항목 | 값 |
|---|---|
| 앱 버전 | `1.9.16` (`build.py` `APP_VERSION`, `__APP_VERSION__`) |
| 스키마 버전 | `14` (`seed.meta.schema_version`) |
| 통화/단위 | KRW 정수, `1P = 1원` |
| 무료배송 기본 | 100,000원 / 배송비 3,000원 |
| 클레임 배송비 | 반품 3,000 / 교환 6,000 / 판매자 귀책 0 |
| 포인트 상한 | 등급별 적립률 0~10% |
| 관리자 페이지 크기 | 10건 |
| 리뷰·Q&A 페이지 크기 | 5건 |
| OTP | 6자리 · 5분 유효 · 60초 쿨다운 |
| 시드 관리자 | `admin@mono.kr` (role=admin, NORMAL, 0P) |
| 시드 회원 | `demo@mono.kr`(GOLD·4,725P), `member1@`(SILVER), `member2@`(NORMAL), `member3@`(SILVER) |
| 시드 상품/옵션 | 13 / 88 |
| 시드 주문/항목 | 21 / 22 |
| 시드 클레임 | 2 (반품 1 · 교환 1) |
| 시드 리뷰/Q&A/추천표 | 14 / 15 / 21 |
| 시드 쿠폰 | 4 (전용 1 — `VIP15` → demo 회원) |
| 시드 FAQ/HELP | 8 / 3 |
| DB 실측 | `integrity_check=ok`, `foreign_key_check` 0건, 테이블 21 · 뷰 6 |

---

## 부록 E. 이 문서의 검증 이력과 갱신 규칙

- **2026-11-28**: v1.9.16 소스 동기화. `shop/` 에서 `python3 build.py` 재실행 → `index.html`·`schema.sql`·`schema-seed.json` **바이트 동일** 확인. `mono-atelier.db` 무결성·FK 검사 통과. 공개 저장소 기준 **실명·연락처·실주소 0건**(build.py 자체 검사).
- 문서의 `shop/src/app.js` 줄 번호는 v1.9.16 고정값입니다. 코드가 바뀌면 **함수명으로 검색**해 갱신하세요.
- API 를 추가·변경하면 **§3 표와 부록 B(오류 코드)** 를 같은 커밋에서 갱신합니다.
- 보안 항목(V1~V20)은 **삭제하지 말고** "해결됨(커밋/날짜)" 으로 표시합니다. 나중에 같은 실수가 반복되는지 추적할 수 있어야 합니다.

---

### 빠른 시작(요약 명령)

```bash
git clone https://github.com/chaeci/chaeci.github.io.git
cd chaeci.github.io/shop
python3 data/build_sqlite.py --out /var/lib/mono-atelier/mono-atelier.db   # DB 생성
python3 build.py                                                          # 프론트 재빌드(개발용)
cp .env.example /srv/mono-atelier/.env && chmod 600 /srv/mono-atelier/.env  # 값 채우기
# §4.5~4.7 구현 후
sudo systemctl enable --now mono-atelier && curl -s localhost:8000/api/health
```

**질문이 생기면**: ① 이 문서의 §1.7(규칙)·§3(명세)을 먼저 확인 ② 그래도 없으면 **추측해서 구현하지 말고** §5.3 결정 목록에 추가해 소유자에게 확인하세요. 금액·권한·개인정보에 관한 추측은 배포 후 되돌리기 어렵습니다.
