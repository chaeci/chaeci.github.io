# MONO ATELIER — 의류 쇼핑몰 프로토타입

프론트엔드만으로 완결되는 모던 컨템포러리 의류 쇼핑몰입니다.
모든 데이터는 **정규화된 6개 테이블(JSON)** 로 관리되고 브라우저 `localStorage`에 저장되며,
`data/schema.sql`로 **SQLite에 1:1 이식**할 수 있게 설계했습니다.

---

## 1. 바로 열어보기

| 파일 | 설명 |
| --- | --- |
| `fashion-shop/index.html` | 실제 앱 (이미지는 `assets/` 상대경로) — 로컬 서버·파일 모두 동작 |
| `downloads/fashion-shop-preview.html` | **단일 HTML 번들** (이미지 13종 base64 내장, 파일 더블클릭으로 바로 실행) |

```bash
# 로컬 서버로 열기 (권장)
cd /workspace && python3 -m http.server 8000
# → http://localhost:8000/fashion-shop/index.html

# 빌드(시드·index.html·프리뷰 재생성)
python3 fashion-shop/build.py
```

### 데모 계정

| 구분 | 이메일 | 비밀번호 |
| --- | --- | --- |
| 일반 회원 | `demo@mono.kr` | `demo1234` |
| 관리자 | `admin@mono.kr` | `admin1234` |

로그인 모달의 **「일반 회원 (데모)」 / 「관리자 (데모)」** 버튼으로 원클릭 로그인할 수 있습니다.
관리자로 로그인하면 상단 메뉴에 `관리자` 탭이 나타납니다.

---

## 2. 파일 구조

```
fashion-shop/
├─ index.html                  # 빌드 산출물 (앱)
├─ build.py                    # 시드/스키마/HTML/프리뷰 생성기
├─ src/
│  ├─ app.js                   # 앱 로직 (vanilla JS, 의존성 0)
│  ├─ styles.css               # 디자인 시스템
│  └─ index.template.html      # HTML 셸
├─ assets/                     # AI 생성 스튜디오 컷 13종 (webp, 872KB)
├─ data/
│  ├─ schema-seed.json         # 정규화 시드 데이터 (6 tables + meta)
│  ├─ schema.sql               # SQLite DDL (FK·CHECK·INDEX·VIEW)
│  ├─ build_sqlite.py          # 시드 → SQLite 변환·검증 스크립트
│  ├─ payment_confirm_example.py # 토스페이먼츠 결제 승인(서버) 예제 — 시크릿 키는 환경변수
│  └─ mono-atelier.db          # 위 스크립트로 만든 샘플 SQLite DB (112KB)
└─ tests/
   ├─ static_check.py          # 데이터 무결성·번들·개인정보·결제 설정 정적 검사 (127 checks)
   ├─ e2e_fashion_shop.py      # Playwright E2E (데스크톱 1280 / 모바일 412 / 토스 결제 / file:// 프리뷰, 137+ checks)
   ├─ make_screenshots.py      # 대표 스크린샷 생성
   └─ smoke.py                 # 단일 페이지 스모크(콘솔 에러 확인)
```

`src/app.js`의 `__SEED__`, `__EMBEDDED_IMAGES__`, `__APP_VERSION__` 토큰은 `build.py`가 치환합니다.
빌드 산출물을 직접 수정하지 말고 `src/`를 고친 뒤 `python3 fashion-shop/build.py`를 실행하세요.

---

## 3. 데이터 구조 (SQLite 이식 대비)

```
users ─┬─< orders ─< order_items >─ product_variants >─ products
       └─< cart_items >──────────────┘
```

| 테이블 | 컬럼 | 비고 |
| --- | --- | --- |
| `users` | id, email, password_hash, name, phone, address, role, created_at | role: customer/admin |
| `products` | id, name, brand, category, price, original_price, badge, description, image, created_at, is_active | category: outer/top/bottom/dress/acc |
| `product_variants` | id, product_id, color, color_hex, size, stock, sku | size: S/M/L/XL/FREE, (product,color,size) UNIQUE |
| `cart_items` | id, user_id, variant_id, quantity, added_at | (user,variant) UNIQUE |
| `orders` | id, order_no, user_id, status, total_amount, shipping_fee, recipient_name, recipient_phone, shipping_address, payment_method, payment_provider, payment_key, payment_mode, created_at | status: paid/preparing/shipping/delivered/cancelled · payment_provider: demo/tosspayments · payment_mode: demo/demo-fallback/test-client/server |
| `order_items` | id, order_id, variant_id, product_name, color, size, unit_price, quantity | 상품명·컬러·사이즈·가격은 **주문 시점 스냅샷** |

* `total_amount` = 상품금액 합계 + `shipping_fee` (전 건 검증됨).
* 시드 규모: users 2 · products 13(판매중 12, 숨김 1) · product_variants 88 · orders 3 · order_items 4.
* 비밀번호는 데모용 `sha256('mono-atelier$' + password)` 해시로 저장합니다(앱 내 동기 SHA-256 구현, 시드와 동일 값 검증 완료).

### SQLite로 옮길 때

1. `data/schema.sql` 실행 (`PRAGMA foreign_keys = ON` 포함, FK·CHECK·SKU UNIQUE·뷰 2종).
2. `data/schema-seed.json`(또는 앱의 **JSON 다운로드**)을 테이블별로 `INSERT`.
   금액은 정수, 시각은 ISO-8601 TEXT, `is_active`는 0/1로 변환하면 그대로 들어갑니다.
3. `v_product_stock`, `v_order_summary` 뷰로 상품별 재고·주문 합계를 바로 검수할 수 있습니다.

자동 변환도 가능합니다:

```bash
python3 fashion-shop/data/build_sqlite.py      # → data/mono-atelier.db 재생성 + 검증 출력
```

```
users 2 · products 13 · product_variants 88 · orders 3 · order_items 4 · cart_items 0
foreign_key_check: OK · 주문 금액 불일치 0
```

---

## 4. 구현 기능

**스토어프론트**
- 29CM/무신사/COS 무드의 에디토리얼 레이아웃, 히어로·아틀리에 노트·서비스 안내·푸터
- 카테고리 탭(전체/아우터/상의/하의/원피스/잡화), 실시간 검색(자동완성 팝업), 정렬(인기/낮은 가격/높은 가격)
- 품절 상품 `SOLD OUT` 오버레이, 할인율·정가 표시, 컬러 도트
- 상품 상세: 컬러 칩 → 사이즈 선택 시 **해당 옵션의 실시간 재고**(`재고 N개 · 품절 임박`), 품절 옵션 비활성, 수량 조절, 총액, 장바구니/바로 구매
- 모바일(≤720px)은 상품 상세가 바텀시트 + 하단 고정 CTA, 2열 그리드, 접이식 검색

**회원**
- 회원가입(이메일·비밀번호·이름·연락처·주소), 로그인, 로그아웃, 데모 원클릭 로그인
- 마이페이지: 회원 정보 수정(이메일 중복 검사), 주문 내역·상태 타임라인·주문 상세, 주문 취소(재고 자동 복구), 누적 결제액, **헤더 우측 로그아웃 버튼**(모바일·데스크톱 공통)
- **데이터 관리(JSON 내보내기·시드 초기화)는 관리자 콘솔 전용** — 마이페이지에는 일반 회원·관리자 모두 탭이 없습니다

**장바구니 / 결제**
- 옵션 단위 담기, 수량 ±(재고 상한), 개별/전체 선택, 10만 원 이상 무료배송(미만 3,000원) 자동 계산, 무료배송까지 남은 금액 게이지
- 체크아웃: 주문자/배송지 자동 채움·수정, 배송지 동일 체크, 결제수단(신용카드/간편결제/무통장입금), 동의 체크
- **토스페이먼츠 SDK v2 결제창(테스트)** — 결제하기 → 대기 주문 저장 → 결제창 → `?tossResult=success` 복귀 시 `paymentKey`·`orderId`·`amount` 검증 → **재고 재검증·차감 → 주문/주문항목 생성(결제키 기록) → 장바구니 비우기 → 영수증 모달**(주문번호 `MAYYYYMMDD-NNNN`)
- `file://`·오프라인·SDK 로드 실패 환경은 자동으로 **데모 모의 결제**로 이어집니다(안내 토스트). 무통장 계좌 안내 유지.

**관리자**
- 대시보드(판매 중 상품·전체 주문·처리 대기·누적 매출)
- 상품 관리: 등록/수정(옵션별 컬러·컬러코드·사이즈·재고), 전체 품절, 숨김/판매재개
- 주문 관리: 상태 변경(결제완료 → 배송준비 → 배송중 → 배송완료 / 취소)
- 데이터: **JSON 다운로드·클립보드 복사·시드 초기화·무결성 검사·테이블 현황·현재 JSON 미리보기** + **결제 설정 카드**(현재 결제 모드·클라이언트 키 마스킹·승인 서버 유무·키 교체 방법)

**토스페이먼츠 결제 연동 (사업자 없이 테스트)**

| 항목 | 값 |
| --- | --- |
| SDK | `https://js.tosspayments.com/v2/standard` (SDK v2 · 결제창형/구 결제위젯) |
| 클라이언트 키 | `test_gck_docs_Ovk5rk1EwkEbP0W43n07xlzm` — 토스페이먼츠 개발자센터 문서에 공개된 테스트 키 |
| 현재 결제 모드 | **테스트 모드 · 사업자 키 미등록** (실제 금액 청구 없음) |
| 서버 승인 | 미연결(`confirmApiUrl: ''`) — 정적 데모에서는 테스트 승인으로 주문만 확정 |

* **키 교체만으로 실결제 전환**: 개발자센터 > API 키 > *주문서형·결제창형 연동 키* 의 `live_gck_…` 를
  `src/app.js` 의 `PAYMENT_CONFIG.clientKey` 에 넣고 `clientKeyMode: 'live'` 로 바꾸면 됩니다.
  시크릿 키(`live_gsk_…`)는 **절대 클라이언트·저장소에 넣지 말고** 서버 환경변수로만 사용하세요.
* **승인 서버 연결**: `PAYMENT_CONFIG.confirmApiUrl = '/api/payments/confirm'` 처럼 지정하면
  복귀 시 브라우저가 `{paymentKey, orderId, amount}` 를 서버로 보내고, 서버가 시크릿 키로 토스 승인 API를 호출합니다.
  참고 구현: `data/payment_confirm_example.py` (금액 서버 검증 · `paymentKey` UNIQUE 멱등 처리 · SQLite 기록).
* 결제창은 구매자가 결제수단을 고르면 `paymentRequest` 이벤트가 발생하고, 그때 `widgets.requestPayment()` 로
  `successUrl`/`failUrl`(= 현재 URL + `?tossResult=success|fail`)로 리다이렉트합니다. 복귀 후 쿼리는 `history.replaceState` 로 정리합니다.

**정책**
- 재고 차감·복구는 변이 시점에 즉시 반영되며, 취소는 `paid`/`preparing`에서만 가능(배송 시작 후 차단).
- 관리자가 옵션을 삭제해도 과거 주문이 참조하는 옵션은 재고 0으로 보존(주문 스냅샷 무결성 유지).
- localStorage를 쓸 수 없는 환경에서는 메모리로 동작하며 안내 토스트를 표시합니다.

---

## 5. 검증 결과

```
static_check.py        127 checks passed (스키마·컬럼·enum·FK·주문금액·해시·DDL·번들·개인정보·결제 설정)
e2e_fashion_shop.py    139 checks passed (데스크톱 1280 / 모바일 412 / 토스 결제 스텁 / 단일 프리뷰)
콘솔 에러              0건
```

E2E 시나리오: 홈·검색·정렬·품절 표시 → **회원가입 → 로그아웃 → 재로그인** → 옵션 선택(재고 확인) → 장바구니 담기 → 수량 변경 → 선택 해제/복원 → 결제(미동의 차단 → 동의) → **재고 6→4 차감** → 영수증 → 마이페이지 주문 → **취소 시 재고 4→6 복구** → 10만 원 미만 주문(배송비 3,000원) → 관리자 로그인 → **상품 등록(옵션 2개)** → 스토어 노출 → **상품 수정(가격·옵션 추가)** → 품절/숨김 → **주문 상태 3단계 변경** → **JSON 내보내기 검증** → 시드 초기화. 모바일은 검색 토글·바텀시트·주문·재고 차감까지 별도 수행.

토스 결제 E2E는 CDN 대신 200 응답 스텁으로 SDK를 대체해 ① `TossPayments(clientKey)` → `widgets` → `setAmount` → `renderPaymentWindow` 호출,
② 결제창의 `paymentRequest` → `requestPayment(orderId/successUrl/failUrl)`, ③ `?tossResult=success&paymentKey=…&orderId=…&amount=…` 복귀 후
**금액·주문번호 검증 → 재고 차감 → 주문 확정(payment_key 기록) → 영수증 → 쿼리 정리**, ④ 실패/금액 변조 시 미확정까지 검증합니다.

```bash
python3 fashion-shop/tests/static_check.py
python3 fashion-shop/tests/e2e_fashion_shop.py
python3 fashion-shop/tests/make_screenshots.py
```

> 테스트는 `LD_LIBRARY_PATH`를 워크스페이스의 `.cache/browserlibs`로 지정해 headless Chromium을 실행합니다(스크립트에 포함).

대표 스크린샷은 `/workspace/downloads/`에 있습니다:
`fashion-shop-home.png`, `fashion-shop-detail-cart.png`, `fashion-shop-admin.png`,
`fashion-shop-cart.png`, `fashion-shop-checkout.png`, `fashion-shop-receipt.png`, `fashion-shop-mypage.png`,
`fashion-shop-admin-orders.png`, `fashion-shop-admin-data.png`, `fashion-shop-mobile-*.png`

---

## 6. 참고

- 상품 이미지는 `images` CLI로 생성한 AI 스튜디오 컷 13종(webp)입니다. 실제 브랜드·상품과 무관합니다.
- 결제는 **토스페이먼츠 테스트 키**로 열리는 테스트 결제창이며 실제 청구가 발생하지 않습니다. 카드 정보는 토스페이먼츠 결제창에서만 입력되고 이 앱은 저장하지 않습니다.
- 공개 저장소 배포본에는 실명·연락처·실주소가 들어가지 않습니다(예시값 `홍길동` / `010-0000-0000` / `서울특별시 송파구 올림픽로 300`). `build.py` 가 빌드 시 개인정보를 검사합니다.
- 이 앱은 프론트엔드 완결형 프로토타입입니다. 서버·동시성 제어는 없으므로 실제 운영 시 재고 차감은 DB 트랜잭션(예: `UPDATE ... WHERE stock >= ?`)으로 옮겨야 합니다.
