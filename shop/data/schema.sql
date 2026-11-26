-- MONO ATELIER — SQLite schema
-- data/schema-seed.json 을 1:1로 옮길 수 있도록 설계한 정규화 스키마입니다.
-- 금액은 KRW 정수, 시각은 ISO-8601 TEXT(+09:00) 로 저장합니다.
-- 데모 비밀번호 해시: sha256('mono-atelier$' + password)

PRAGMA foreign_keys = ON;

CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  name          TEXT NOT NULL,
  phone         TEXT NOT NULL,
  address       TEXT NOT NULL DEFAULT '',
  role          TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','admin')),
  grade         TEXT NOT NULL DEFAULT 'NORMAL' CHECK (grade IN ('NORMAL','SILVER','GOLD','VIP')),
                -- 회원 등급 — 쿠폰 발급 대상(등급별)에 사용
  created_at    TEXT NOT NULL
);

-- 카테고리 — 관리자 콘솔에서 추가·이름 수정·삭제·순서 변경 (products.category 가 참조)
CREATE TABLE categories (
  id         TEXT PRIMARY KEY,
  label      TEXT NOT NULL,
  en         TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE products (
  id             TEXT PRIMARY KEY,
  product_code   TEXT NOT NULL UNIQUE,          -- 제품고유키(제품번호) 예: MA-0001 · 대소문자 무시 중복 금지
  name           TEXT NOT NULL,
  brand          TEXT NOT NULL DEFAULT 'MONO ATELIER',
  category       TEXT NOT NULL REFERENCES categories(id),
  price          INTEGER NOT NULL CHECK (price >= 0),
  original_price INTEGER CHECK (original_price IS NULL OR original_price >= price),
  badge          TEXT CHECK (badge IS NULL OR (length(trim(badge)) BETWEEN 1 AND 16)),
                 -- 프리셋(BEST/NEW/SALE/LIMITED) 또는 관리자가 입력한 짧은 문구
  description    TEXT NOT NULL DEFAULT '',
  image          TEXT NOT NULL,                              -- 대표 이미지
  model_info     TEXT,                                       -- 모델 착용 정보 (예: '모델 174cm · 54kg · M 사이즈 착용'), NULL = 표시 안 함
  free_shipping_threshold INTEGER
                 CHECK (free_shipping_threshold IS NULL OR free_shipping_threshold >= 0),
                 -- NULL = 스토어 기본(100,000원), 0 = 무조건 무료배송, N = 해당 상품 합계 N원 이상 무료
  created_at     TEXT NOT NULL,
  is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

-- 상품 갤러리 이미지 (products.image = 대표, 이 테이블 = 대표 + 디테일 컷 전체)
CREATE TABLE product_images (
  id         TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  image      TEXT NOT NULL,
  alt        TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
  UNIQUE (product_id, image)
);

CREATE TABLE product_variants (
  id         TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  color      TEXT NOT NULL,
  color_hex  TEXT NOT NULL,
  size       TEXT NOT NULL CHECK (size IN ('S','M','L','XL','FREE')),
  stock      INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
  sku        TEXT NOT NULL UNIQUE,
  UNIQUE (product_id, color, size)
);

CREATE TABLE cart_items (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  variant_id TEXT NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  quantity   INTEGER NOT NULL CHECK (quantity > 0),
  added_at   TEXT NOT NULL,
  UNIQUE (user_id, variant_id)
);

CREATE TABLE orders (
  id               TEXT PRIMARY KEY,
  order_no         TEXT NOT NULL UNIQUE,
  user_id          TEXT NOT NULL REFERENCES users(id),
  status           TEXT NOT NULL DEFAULT 'paid'
                   CHECK (status IN ('paid','preparing','shipping','delivered','cancelled')),
  total_amount     INTEGER NOT NULL CHECK (total_amount >= 0),
  shipping_fee     INTEGER NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
  coupon_code      TEXT,                                    -- 적용된 쿠폰 코드 (없으면 NULL)
  discount_amount  INTEGER NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  recipient_name   TEXT NOT NULL,
  recipient_phone  TEXT NOT NULL,
  shipping_address TEXT NOT NULL,
  payment_method   TEXT NOT NULL CHECK (payment_method IN ('card','easypay','bank')),
  payment_provider TEXT NOT NULL DEFAULT 'demo',           -- demo | tosspayments
  payment_key      TEXT,                                    -- 토스페이먼츠 paymentKey (승인·취소·조회)
  payment_mode     TEXT NOT NULL DEFAULT 'demo',            -- demo | demo-fallback | test-client | server
  created_at       TEXT NOT NULL
);

CREATE TABLE order_items (
  id           TEXT PRIMARY KEY,
  order_id     TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  variant_id   TEXT NOT NULL REFERENCES product_variants(id),
  product_name TEXT NOT NULL,          -- 주문 시점 스냅샷
  color        TEXT NOT NULL,
  size         TEXT NOT NULL,
  unit_price   INTEGER NOT NULL CHECK (unit_price >= 0),
  quantity     INTEGER NOT NULL CHECK (quantity > 0)
);

-- 교환/반품 접수 (주문 단위, 한 주문당 1건)
--   · 판매자 귀책(defect·wrong_item) : 배송비 0원 / payment_status='free'
--   · 고객 귀책(change_of_mind·size_color) : 반품 3,000원, 교환(왕복) 6,000원 → 토스페이먼츠 결제 후 'paid'
CREATE TABLE order_claims (
  id              TEXT PRIMARY KEY,
  order_id        TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  user_id         TEXT NOT NULL REFERENCES users(id),
  claim_type      TEXT NOT NULL CHECK (claim_type IN ('return','exchange')),
  reason_category TEXT NOT NULL
                  CHECK (reason_category IN ('defect','wrong_item','change_of_mind','size_color')),
  reason_detail   TEXT NOT NULL DEFAULT '',
  shipping_fee    INTEGER NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
  payment_status  TEXT NOT NULL DEFAULT 'free' CHECK (payment_status IN ('free','paid','pending')),
  payment_key     TEXT,                                    -- 유료 배송비 결제 시 토스페이먼츠 paymentKey
  payment_mode    TEXT NOT NULL DEFAULT 'free',            -- free | demo-fallback | test-client | server
  exchange_option TEXT,                                    -- 교환 희망 옵션 (예: '카멜 / L'), 반품이면 NULL
  status          TEXT NOT NULL DEFAULT 'requested'
                  CHECK (status IN ('requested','approved','completed','rejected')),
  stock_restored  INTEGER NOT NULL DEFAULT 0 CHECK (stock_restored IN (0,1)),
                  -- 반품 완료 시 재고 복구를 한 번만 수행하기 위한 플래그
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  UNIQUE (order_id)
);

-- 할인 쿠폰 — 관리자 콘솔에서 발행/중지, 체크아웃에서 코드 또는 원클릭 적용
-- 발급 대상: coupon_targets 에 행이 없으면 전체 공용, 있으면 지정된 회원만 사용 가능
CREATE TABLE coupons (
  id               TEXT PRIMARY KEY,
  code             TEXT NOT NULL UNIQUE,
  name             TEXT NOT NULL,
  discount_type    TEXT NOT NULL CHECK (discount_type IN ('percent','fixed')),
  discount_value   INTEGER NOT NULL CHECK (discount_value > 0),
                   -- percent 이면 할인율(%), fixed 이면 할인 금액(원)
  min_order_amount INTEGER NOT NULL DEFAULT 0 CHECK (min_order_amount >= 0),
  expires_at       TEXT,                                    -- NULL = 무기한
  is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  target_grades    TEXT NOT NULL DEFAULT '[]',              -- JSON 배열: 발급 대상 회원 등급 ([] = 등급 제한 없음)
  created_at       TEXT NOT NULL
);

-- 쿠폰 발급 대상 (행 1개 = 대상 회원 1명). 행이 없으면 전체 공용 쿠폰.
CREATE TABLE coupon_targets (
  id         TEXT PRIMARY KEY,
  coupon_id  TEXT NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  UNIQUE (coupon_id, user_id)
);

CREATE INDEX idx_variants_product ON product_variants(product_id);
CREATE INDEX idx_products_category ON products(category, is_active);
-- 제품번호는 대소문자 무시하고 유일하게 관리한다(관리자 저장 시에도 같은 규칙으로 검사)
CREATE UNIQUE INDEX idx_products_code_nocase ON products(product_code COLLATE NOCASE);
CREATE INDEX idx_product_images ON product_images(product_id, sort_order);
CREATE INDEX idx_cart_user ON cart_items(user_id);
CREATE INDEX idx_orders_user ON orders(user_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_coupons_code ON coupons(code);
CREATE INDEX idx_coupon_targets_user ON coupon_targets(user_id);
CREATE INDEX idx_coupon_targets_coupon ON coupon_targets(coupon_id);
CREATE INDEX idx_claims_order ON order_claims(order_id);
CREATE INDEX idx_claims_user ON order_claims(user_id, created_at DESC);
CREATE INDEX idx_claims_status ON order_claims(status);

-- 재고 확인용 뷰: 상품별 총 재고
CREATE VIEW v_product_stock AS
SELECT p.id AS product_id, p.product_code, p.name, p.category,
       COALESCE(SUM(v.stock), 0) AS stock_total,
       COUNT(v.id) AS option_count
FROM products p
LEFT JOIN product_variants v ON v.product_id = p.id
GROUP BY p.id;

-- 주문 요약 뷰: 상품 합계 + 배송비 − 쿠폰 할인 = total_amount 인지 바로 확인
CREATE VIEW v_order_summary AS
SELECT o.id, o.order_no, o.status, o.total_amount, o.shipping_fee,
       o.coupon_code, o.discount_amount,
       COALESCE(SUM(oi.unit_price * oi.quantity), 0) AS subtotal,
       COUNT(oi.id) AS item_count
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id;

-- 교환/반품 접수 현황: 주문번호·회원·사유·배송비 결제·상태를 한눈에 확인
CREATE VIEW v_order_claims AS
SELECT c.id, o.order_no, o.status AS order_status, u.name AS user_name, u.email,
       c.claim_type, c.reason_category, c.reason_detail, c.exchange_option,
       c.shipping_fee, c.payment_status, c.payment_mode, c.status AS claim_status,
       c.created_at, c.updated_at
FROM order_claims c
JOIN orders o ON o.id = c.order_id
JOIN users u ON u.id = c.user_id;

-- 쿠폰 발급 대상 보기: 전용 쿠폰이 누구에게 발급됐는지 한눈에 확인
CREATE VIEW v_coupon_targets AS
SELECT c.code, c.name, t.user_id, u.name AS user_name, u.email
FROM coupons c
JOIN coupon_targets t ON t.coupon_id = c.id
JOIN users u ON u.id = t.user_id;

-- ===================================================== 사이트 설정 (v1.8)
-- 관리자 「메인/사이트 관리」에서 편집 — 히어로 배너·푸터 브랜드 소개·사업자 정보
CREATE TABLE site_settings (
  id                   TEXT PRIMARY KEY,                        -- 'default' 단일 행
  hero_image           TEXT NOT NULL,                           -- 대표 배너 이미지(asset 파일명 또는 업로드 Data URL)
  hero_eyebrow         TEXT NOT NULL DEFAULT '',                -- 상단 뱃지 문구
  hero_title           TEXT NOT NULL,                           -- 메인 타이틀
  hero_subtitle        TEXT NOT NULL DEFAULT '',                -- 서브 문구
  hero_cta_label       TEXT NOT NULL DEFAULT '컬렉션 보기',
  hero_cta2_label      TEXT NOT NULL DEFAULT '브랜드 스토리',
  hero_effect          TEXT NOT NULL DEFAULT 'none'
                       CHECK (hero_effect IN ('none','zoom','fade','slide')),
  hero_overlay         INTEGER NOT NULL DEFAULT 42 CHECK (hero_overlay BETWEEN 0 AND 90),
  brand_blurb          TEXT NOT NULL DEFAULT '',                -- 푸터 브랜드 소개
  company_name         TEXT NOT NULL DEFAULT '',                -- 상호
  company_ceo          TEXT NOT NULL DEFAULT '',                -- 대표자
  company_reg_no       TEXT NOT NULL DEFAULT '',                -- 사업자등록번호
  company_mail_order_no TEXT NOT NULL DEFAULT '',               -- 통신판매업 신고번호
  company_address      TEXT NOT NULL DEFAULT '',                -- 주소
  company_phone        TEXT NOT NULL DEFAULT '',                -- 고객센터 전화
  company_email        TEXT NOT NULL DEFAULT '',                -- 고객센터 이메일
  updated_at           TEXT NOT NULL
);

-- 푸터 HELP 메뉴 — 클릭하면 안내 모달로 열리는 항목(관리자가 제목·본문 편집)
CREATE TABLE help_topics (
  id         TEXT PRIMARY KEY,
  title      TEXT NOT NULL,
  body       TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_help_topics_sort ON help_topics(sort_order);
