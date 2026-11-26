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
  created_at    TEXT NOT NULL
);

CREATE TABLE products (
  id             TEXT PRIMARY KEY,
  name           TEXT NOT NULL,
  brand          TEXT NOT NULL DEFAULT 'MONO ATELIER',
  category       TEXT NOT NULL CHECK (category IN ('outer','top','bottom','dress','acc')),
  price          INTEGER NOT NULL CHECK (price >= 0),
  original_price INTEGER CHECK (original_price IS NULL OR original_price >= price),
  badge          TEXT CHECK (badge IS NULL OR badge IN ('NEW','BEST','SALE')),
  description    TEXT NOT NULL DEFAULT '',
  image          TEXT NOT NULL,
  created_at     TEXT NOT NULL,
  is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
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
  recipient_name   TEXT NOT NULL,
  recipient_phone  TEXT NOT NULL,
  shipping_address TEXT NOT NULL,
  payment_method   TEXT NOT NULL CHECK (payment_method IN ('card','easypay','bank')),
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

CREATE INDEX idx_variants_product ON product_variants(product_id);
CREATE INDEX idx_products_category ON products(category, is_active);
CREATE INDEX idx_cart_user ON cart_items(user_id);
CREATE INDEX idx_orders_user ON orders(user_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_order_items_order ON order_items(order_id);

-- 재고 확인용 뷰: 상품별 총 재고
CREATE VIEW v_product_stock AS
SELECT p.id AS product_id, p.name, p.category,
       COALESCE(SUM(v.stock), 0) AS stock_total,
       COUNT(v.id) AS option_count
FROM products p
LEFT JOIN product_variants v ON v.product_id = p.id
GROUP BY p.id;

-- 주문 요약 뷰: 상품 합계와 배송비 합이 total_amount 와 일치하는지 바로 확인
CREATE VIEW v_order_summary AS
SELECT o.id, o.order_no, o.status, o.total_amount, o.shipping_fee,
       COALESCE(SUM(oi.unit_price * oi.quantity), 0) AS subtotal,
       COUNT(oi.id) AS item_count
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id;
