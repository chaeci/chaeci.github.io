#!/usr/bin/env python3
"""Build MONO ATELIER: seed JSON/SQL + index.html + single-file preview.

Usage:  python3 fashion-shop/build.py
"""
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
ASSETS = ROOT / "assets"
DATA = ROOT / "data"
SRC = ROOT / "src"
DOWNLOADS = WORKSPACE / "downloads"
APP_VERSION = "1.9.16"
FREE_SHIPPING = 100000
SHIPPING_FEE = 3000

PEPPER = "mono-atelier$"

# 공개 저장소(chaeci.github.io/shop)에 배포되는 시드 — 실제 개인정보 대신 예시값만 사용한다.
EXAMPLE_NAME = "홍길동"
EXAMPLE_PHONE = "010-0000-0000"
EXAMPLE_ADDRESS = "서울특별시 송파구 올림픽로 300 101동 1203호"
# 빌드 산출물에 실제 개인정보가 섞이지 않았는지 확인하는 안전장치(빌드 실패 처리).
# 실명·연락처·실주소 문자열 자체는 **공개 저장소에 두지 않는다.** 필요하면 환경변수로 주입한다.
#   MONO_PRIVATE_PATTERNS="이름,연락처,주소조각" python3 build.py
PRIVATE_PATTERNS = [p.strip() for p in os.environ.get("MONO_PRIVATE_PATTERNS", "").split(",") if p.strip()]
# 값과 무관하게 항상 검사하는 패턴 — 주민등록번호 · 예시값(010-0000-0000)이 아닌 휴대전화 번호
RRN_RE = re.compile(r"\d{6}-\s?[1-4]\d{6}")
MOBILE_RE = re.compile(r"01[016789]-\d{3,4}-\d{4}")
ALLOWED_PHONES = {"010-0000-0000"}


def h(pw: str) -> str:
    return hashlib.sha256((PEPPER + pw).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- users
users = [
    {
        "id": "u_001",
        "email": "demo@mono.kr",
        "password_hash": h("demo1234"),
        "name": EXAMPLE_NAME,
        "phone": EXAMPLE_PHONE,
        "address": EXAMPLE_ADDRESS,
        "role": "customer",
        "grade": "GOLD",          # 회원 등급 — 쿠폰 발급 대상(등급별)·포인트 적립률에 사용
        "points": 4725,           # 보유 포인트 (point_logs 합계와 일치)
        "postcode": "05551",
        "created_at": "2026-11-09T10:42:00+09:00",
    },
    {
        "id": "u_002",
        "email": "admin@mono.kr",
        "password_hash": h("admin1234"),
        "name": "관리자",
        "phone": "02-0000-0000",
        "address": EXAMPLE_ADDRESS + " 3층",
        "role": "admin",
        "grade": "NORMAL",
        "points": 0,
        "postcode": "05551",
        "created_at": "2026-10-01T09:00:00+09:00",
    },
    # v1.9.1 — 상품 상세 리뷰 페이징(5개씩)을 확인할 수 있도록 리뷰 작성자 회원을 추가한다.
    # 실제 개인정보가 아닌 예시값만 사용한다.
    {
        "id": "u_003", "email": "member1@mono.kr", "password_hash": h("demo1234"),
        "name": "홍길순", "phone": EXAMPLE_PHONE, "address": EXAMPLE_ADDRESS,
        "role": "customer", "grade": "SILVER", "points": 0, "postcode": "05551",
        "created_at": "2026-10-20T10:00:00+09:00",
    },
    {
        "id": "u_004", "email": "member2@mono.kr", "password_hash": h("demo1234"),
        "name": "홍길자", "phone": EXAMPLE_PHONE, "address": EXAMPLE_ADDRESS,
        "role": "customer", "grade": "NORMAL", "points": 0, "postcode": "05551",
        "created_at": "2026-10-21T10:00:00+09:00",
    },
    {
        "id": "u_005", "email": "member3@mono.kr", "password_hash": h("demo1234"),
        "name": "홍길녀", "phone": EXAMPLE_PHONE, "address": EXAMPLE_ADDRESS,
        "role": "customer", "grade": "SILVER", "points": 0, "postcode": "05551",
        "created_at": "2026-10-22T10:00:00+09:00",
    },
]

# --------------------------------------------------------------- categories
# 관리자 콘솔 「카테고리 관리」에서 추가·이름 수정·삭제·순서 변경이 가능하다.
# products.category 가 이 테이블의 id 를 참조한다 (스토어 상단 필터·상품 등록 드롭다운과 즉시 연동).
# v1.9.1 — 카테고리별 사이즈 코드: 관리자 「카테고리」 탭에서 추가·수정·삭제·순서 변경,
# 상품 등록/수정의 사이즈 드롭다운에 즉시 반영된다. (95·100·105 / 28·30·32 / 240·250 …)
categories = [
    {"id": "outer", "label": "아우터", "en": "OUTER", "sort_order": 1,
     "size_codes": ["95", "100", "105", "S", "M", "L", "XL"], "created_at": "2026-10-01T09:00:00+09:00", "is_active": True},
    {"id": "top", "label": "상의", "en": "TOP", "sort_order": 2,
     "size_codes": ["95", "100", "105", "S", "M", "L", "XL", "FREE"], "created_at": "2026-10-01T09:00:00+09:00", "is_active": True},
    {"id": "bottom", "label": "하의", "en": "BOTTOM", "sort_order": 3,
     "size_codes": ["28", "30", "32", "34", "S", "M", "L"], "created_at": "2026-10-01T09:00:00+09:00", "is_active": True},
    {"id": "dress", "label": "원피스", "en": "DRESS", "sort_order": 4,
     "size_codes": ["S", "M", "L"], "created_at": "2026-10-01T09:00:00+09:00", "is_active": True},
    {"id": "acc", "label": "잡화", "en": "ACC", "sort_order": 5,
     "size_codes": ["FREE"], "created_at": "2026-10-01T09:00:00+09:00", "is_active": True},
]

# ------------------------------------------------------------------ products
# (id, name, category, price, original_price, badge, image, description,
#  sizes, [(color, hex, [stocks...])], created_at, is_active)
P = [
    (
        "p_001", "울 더블 브레스티드 코트", "outer", 289000, 349000, "BEST", "coat.webp",
        "두 겹의 울 소재로 지은 더블 브레스티드 코트. 어깨선은 단정하게, 기장은 무릎 아래로 떨어지는 클래식한 실루엣입니다.",
        ["S", "M", "L", "XL"],
        [("차콜", "#35353A", [5, 3, 2, 1]), ("카멜", "#B08A5E", [4, 6, 3, 0]), ("블랙", "#1B1B1D", [2, 0, 4, 2])],
        "2026-11-10T09:20:00+09:00", True,
    ),
    (
        "p_002", "캐시미어 리브 니트", "top", 129000, 159000, "NEW", "knit.webp",
        "캐시미어 혼방의 부드러운 촉감. 목선은 여유 있게, 소매는 살짝 길게 떨어지는 데일리 니트입니다.",
        ["S", "M", "L"],
        [("크림", "#EFE7D9", [8, 12, 5]), ("오트밀", "#D9CBB5", [3, 2, 6]), ("블랙", "#262626", [4, 1, 0])],
        "2026-11-18T11:05:00+09:00", True,
    ),
    (
        "p_003", "와이드 테일러드 트라우저", "bottom", 149000, None, None, "pants.webp",
        "허리선을 높여 다리를 길게 보이게 만든 와이드 슬랙스. 힘을 뺀 핏이 하루 종일 편안합니다.",
        ["S", "M", "L", "XL"],
        [("블랙", "#1B1B1D", [6, 9, 4, 2]), ("차콜", "#3B3B3F", [2, 5, 7, 1])],
        "2026-10-25T16:30:00+09:00", True,
    ),
    (
        "p_004", "사틴 슬립 미디 드레스", "dress", 189000, 220000, "SALE", "dress.webp",
        "빛을 따라 흐르는 사틴 소재의 미디 드레스. 슬립 실루엣 위에 오버사이즈 니트를 걸쳐 입기 좋습니다.",
        ["S", "M", "L"],
        [("샴페인", "#D9C3A8", [3, 0, 2]), ("블랙", "#1B1B1D", [4, 5, 3])],
        "2026-11-02T13:10:00+09:00", True,
    ),
    (
        "p_005", "스무스 레더 숄더백", "acc", 259000, None, "BEST", "bag.webp",
        "이탈리아산 소프트 카프레더. 실버 클래스프 하나로 마무리한 미니멀한 숄더백입니다.",
        ["FREE"],
        [("블랙", "#1B1B1D", [6]), ("다크브라운", "#4A3628", [2])],
        "2026-11-08T10:00:00+09:00", True,
    ),
    (
        "p_006", "나일론 봄버 재킷", "outer", 179000, 210000, "NEW", "jacket.webp",
        "가벼운 나일론에 광택을 낮춘 봄버 재킷. 리브 소매와 밴딩 밑단으로 담백하게 완성했습니다.",
        ["M", "L", "XL"],
        [("올리브", "#5A6247", [5, 4, 2]), ("블랙", "#1B1B1D", [3, 0, 5]), ("샌드", "#C9B79C", [2, 3, 1])],
        "2026-11-20T09:45:00+09:00", True,
    ),
    (
        "p_007", "오버사이즈 코튼 셔츠", "top", 89000, None, None, "shirt.webp",
        "두 겹의 코튼 포플린으로 만든 오버사이즈 셔츠. 떨어지는 어깨선이 여유로운 분위기를 만듭니다.",
        ["S", "M", "L"],
        [("화이트", "#F7F5F0", [10, 14, 6]), ("스카이", "#C9D8E4", [4, 3, 2])],
        "2026-10-28T15:20:00+09:00", True,
    ),
    (
        "p_008", "플리츠 미디 스커트", "bottom", 139000, 168000, "SALE", "skirt.webp",
        "곱게 잡힌 주름이 움직임마다 다른 표정을 만드는 미디 스커트. 허리 밴딩으로 편안하게 착용됩니다.",
        ["S", "M", "L"],
        [("차콜", "#3B3B3F", [5, 3, 2]), ("블랙", "#1B1B1D", [4, 6, 1])],
        "2026-10-20T12:00:00+09:00", True,
    ),
    (
        "p_009", "개버딘 트렌치 코트", "outer", 319000, 369000, "LIMITED", "trench.webp",
        "묵직한 코튼 개버딘으로 지은 트렌치 코트. 벨트를 묶거나 풀어 두 가지 실루엣으로 입을 수 있습니다.",
        ["S", "M", "L", "XL"],
        [("베이지", "#C9B48F", [0, 3, 4, 2]), ("블랙", "#1B1B1D", [2, 4, 3, 1])],
        "2026-11-15T10:30:00+09:00", True,
    ),
    (
        "p_010", "울 블렌드 오픈 가디건", "top", 119000, None, None, "cardigan.webp",
        "울 혼방의 도톰한 가디건. 티셔츠 위에 걸치기 좋은 기장과 단추 없는 오픈 디자인입니다.",
        ["S", "M", "L"],
        [("그레이", "#B9B7B1", [4, 5, 3]), ("아이보리", "#EEE8DA", [2, 2, 4])],
        "2026-10-15T09:10:00+09:00", True,
    ),
    (
        "p_011", "와이드 데님 팬츠", "bottom", 109000, 129000, "NEW", "denim.webp",
        "워싱을 최소화한 진한 인디고 데님. 넓게 떨어지는 다리선과 높은 허리로 비율을 잡아 줍니다.",
        ["S", "M", "L", "XL"],
        [("미드블루", "#5C7CA6", [6, 8, 5, 3]), ("워시드 블랙", "#3A3A3E", [3, 4, 2, 0])],
        "2026-11-23T14:00:00+09:00", True,
    ),
    (
        "p_012", "레더 페니 로퍼", "acc", 219000, 249000, None, "loafers.webp",
        "블랙 카프레더 페니 로퍼. 2.5cm의 낮은 굽으로 하루 종일 편안하게 신을 수 있습니다.",
        ["FREE"],
        [("블랙", "#1B1B1D", [0]), ("다크브라운", "#4A3628", [0])],
        "2026-11-05T11:40:00+09:00", True,
    ),
    (
        "p_013", "실크 크레이프 미디 원피스", "dress", 209000, None, None, "dress.webp",
        "실크 크레이프가 몸의 선을 따라 흐르는 미디 원피스. (관리자 숨김 상태 데모 상품)",
        ["S", "M", "L"],
        [("샴페인", "#D9C3A8", [2, 2, 1]), ("블랙", "#1B1B1D", [3, 2, 2])],
        "2026-11-25T17:30:00+09:00", False,
    ),
]

CAT_CODE = {"outer": "OUT", "top": "TOP", "bottom": "BTM", "dress": "DRS", "acc": "ACC"}

# 상품별 모델 착용 정보 (관리자 상품 등록/수정에서 변경 가능, 비우면 상세에서 숨김)
MODEL_INFO = {
    "p_001": "모델 174cm · 54kg · M 사이즈 착용",
    "p_002": "모델 171cm · 52kg · M 사이즈 착용",
    "p_003": "모델 176cm · 60kg · M 사이즈 착용",
    "p_004": "모델 173cm · 53kg · S 사이즈 착용",
    "p_005": "모델 172cm 착용 컷",
    "p_006": "모델 178cm · 62kg · L 사이즈 착용",
    "p_007": "모델 174cm · 56kg · M 사이즈 착용",
    "p_008": "모델 170cm · 51kg · S 사이즈 착용",
    "p_009": "모델 176cm · 58kg · M 사이즈 착용",
    "p_010": "모델 169cm · 50kg · S 사이즈 착용",
    "p_011": "모델 175cm · 59kg · M 사이즈 착용",
    "p_012": "모델 172cm 착용 컷",
    "p_013": "모델 173cm · 53kg · M 사이즈 착용",
}

# 제품별 무료배송 기준 금액 — None 이면 스토어 기본(100,000원), 0 이면 무조건 무료배송
FREE_SHIP_BY_PRODUCT = {
    "p_001": None, "p_002": 50000, "p_003": None, "p_004": None, "p_005": 0,
    "p_006": None, "p_007": None, "p_008": None, "p_009": 0, "p_010": 50000,
    "p_011": 50000, "p_012": 0, "p_013": None,
}


def gallery_of(image: str):
    """대표 이미지 + 디테일 크롭 2장(assets/<stem>-detail|-fabric.webp)."""
    stem = image.rsplit(".", 1)[0]
    return [image, stem + "-detail.webp", stem + "-fabric.webp"]


products, variants, product_images = [], [], []
imgnum = 0
vnum = 0
for pidx, (pid, name, cat, price, orig, badge, image, desc, sizes, colors, created, active) in enumerate(P, start=1):
    images = gallery_of(image)
    products.append({
        "id": pid,
        "product_code": f"MA-{pidx:04d}",   # 제품고유키(제품번호) — UNIQUE, 관리자 화면에서 자동 채번
        "name": name,
        "brand": "MONO ATELIER",
        "category": cat,
        "price": price,
        "original_price": orig,
        "badge": badge,
        "description": desc,
        "image": image,
        "images": images,
        "model_info": MODEL_INFO.get(pid),
        "free_shipping_threshold": FREE_SHIP_BY_PRODUCT[pid],
        "created_at": created,
        "is_active": active,
    })
    for order, img in enumerate(images):
        imgnum += 1
        product_images.append({
            "id": f"pi_{imgnum:03d}",
            "product_id": pid,
            "image": img,
            "alt": name + ("" if order == 0 else (" 디테일" if order == 1 else " 소재 클로즈업")),
            "sort_order": order,
        })
    for color, hexv, stocks in colors:
        for size, stock in zip(sizes, stocks):
            vnum += 1
            variants.append({
                "id": f"v_{vnum:03d}",
                "product_id": pid,
                "color": color,
                "color_hex": hexv,
                "size": size,
                "stock": stock,
                "sku": f"MA-{CAT_CODE[cat]}-{pid[-3:]}-{color[:2]}-{size}",
            })

# -------------------------------------------------------------------- orders
orders = [
    {
        "id": "o_001",
        "order_no": "MA20261112-4821",
        "user_id": "u_001",
        "status": "delivered",
        "total_amount": 278000,
        "shipping_fee": 0,
        "coupon_code": None,
        "discount_amount": 0,
        "recipient_name": EXAMPLE_NAME,
        "recipient_phone": EXAMPLE_PHONE,
        "shipping_address": EXAMPLE_ADDRESS,
        "payment_method": "card",
        "payment_provider": "demo",
        "payment_key": None,
        "payment_mode": "demo",
        "created_at": "2026-11-12T10:24:00+09:00",
    },
    {
        "id": "o_002",
        "order_no": "MA20261124-3917",
        "user_id": "u_001",
        "status": "paid",
        "total_amount": 173000,
        "shipping_fee": 0,
        "coupon_code": "MONO5000",
        "discount_amount": 5000,
        "recipient_name": EXAMPLE_NAME,
        "recipient_phone": EXAMPLE_PHONE,
        "shipping_address": EXAMPLE_ADDRESS,
        "payment_method": "easypay",
        "payment_provider": "demo",
        "payment_key": None,
        "payment_mode": "demo",
        "created_at": "2026-11-24T15:40:00+09:00",
    },
    {
        "id": "o_003",
        "order_no": "MA20261125-6042",
        "user_id": "u_001",
        "status": "preparing",
        "total_amount": 289000,
        "shipping_fee": 0,
        "coupon_code": None,
        "discount_amount": 0,
        "recipient_name": EXAMPLE_NAME,
        "recipient_phone": EXAMPLE_PHONE,
        "shipping_address": EXAMPLE_ADDRESS,
        "payment_method": "bank",
        "payment_provider": "demo",
        "payment_key": None,
        "payment_mode": "demo",
        "created_at": "2026-11-25T09:12:00+09:00",
    },
    {
        "id": "o_004",
        "order_no": "MA20261114-2288",
        "user_id": "u_001",
        "status": "delivered",
        "total_amount": 109000,
        "shipping_fee": 0,
        "coupon_code": None,
        "discount_amount": 0,
        "recipient_name": EXAMPLE_NAME,
        "recipient_phone": EXAMPLE_PHONE,
        "shipping_address": EXAMPLE_ADDRESS,
        "payment_method": "card",
        "payment_provider": "demo",
        "payment_key": None,
        "payment_mode": "demo",
        "created_at": "2026-11-14T11:05:00+09:00",
    },
    {
        "id": "o_005",
        "order_no": "MA20261116-7735",
        "user_id": "u_001",
        "status": "delivered",
        "total_amount": 139000,
        "shipping_fee": 0,
        "coupon_code": None,
        "discount_amount": 0,
        "recipient_name": EXAMPLE_NAME,
        "recipient_phone": EXAMPLE_PHONE,
        "shipping_address": EXAMPLE_ADDRESS,
        "payment_method": "easypay",
        "payment_provider": "demo",
        "payment_key": None,
        "payment_mode": "demo",
        "created_at": "2026-11-16T14:30:00+09:00",
    },
]

order_items = [
    {"id": "oi_001", "order_id": "o_001", "variant_id": "v_014", "product_name": "캐시미어 리브 니트", "color": "크림", "size": "M", "unit_price": 129000, "quantity": 1},
    {"id": "oi_002", "order_id": "o_001", "variant_id": "v_023", "product_name": "와이드 테일러드 트라우저", "color": "블랙", "size": "M", "unit_price": 149000, "quantity": 1},
    {"id": "oi_003", "order_id": "o_002", "variant_id": "v_047", "product_name": "오버사이즈 코튼 셔츠", "color": "화이트", "size": "S", "unit_price": 89000, "quantity": 2},
    {"id": "oi_004", "order_id": "o_003", "variant_id": "v_001", "product_name": "울 더블 브레스티드 코트", "color": "차콜", "size": "S", "unit_price": 289000, "quantity": 1},
    {"id": "oi_005", "order_id": "o_004", "variant_id": "v_074", "product_name": "와이드 데님 팬츠", "color": "미드블루", "size": "M", "unit_price": 109000, "quantity": 1},
    {"id": "oi_006", "order_id": "o_005", "variant_id": "v_054", "product_name": "플리츠 미디 스커트", "color": "차콜", "size": "M", "unit_price": 139000, "quantity": 1},
    {"id": "oi_007", "order_id": "o_006", "variant_id": "v_001", "product_name": "울 더블 브레스티드 코트", "color": "차콜", "size": "S", "unit_price": 289000, "quantity": 1},
    # v1.9.1 — 리뷰 페이징용 코트 주문 항목 (각기 다른 회원의 배송완료 주문)
    {"id": "oi_008", "order_id": "o_007", "variant_id": "v_001", "product_name": "울 더블 브레스티드 코트", "color": "차콜", "size": "S", "unit_price": 289000, "quantity": 1},
    {"id": "oi_009", "order_id": "o_008", "variant_id": "v_005", "product_name": "울 더블 브레스티드 코트", "color": "카멜", "size": "S", "unit_price": 289000, "quantity": 1},
    {"id": "oi_010", "order_id": "o_009", "variant_id": "v_006", "product_name": "울 더블 브레스티드 코트", "color": "카멜", "size": "M", "unit_price": 289000, "quantity": 1},
    {"id": "oi_011", "order_id": "o_010", "variant_id": "v_010", "product_name": "울 더블 브레스티드 코트", "color": "블랙", "size": "M", "unit_price": 289000, "quantity": 1},
    {"id": "oi_012", "order_id": "o_011", "variant_id": "v_003", "product_name": "울 더블 브레스티드 코트", "color": "차콜", "size": "L", "unit_price": 289000, "quantity": 1},
    {"id": "oi_013", "order_id": "o_012", "variant_id": "v_012", "product_name": "울 더블 브레스티드 코트", "color": "블랙", "size": "XL", "unit_price": 289000, "quantity": 1},
]

# v1.9: 주문별 우편번호·사용 포인트 · 주문항목별 구매확정/포인트 적립 상태
orders.append({
    "id": "o_006",
    "order_no": "MA20261105-1852",
    "user_id": "u_001",
    "status": "delivered",
    "total_amount": 289000,
    "shipping_fee": 0,
    "coupon_code": None,
    "discount_amount": 0,
    "recipient_name": EXAMPLE_NAME,
    "recipient_phone": EXAMPLE_PHONE,
    "shipping_address": EXAMPLE_ADDRESS,
    "postcode": "05551",
    "points_used": 0,
    "payment_method": "card",
    "payment_provider": "demo",
    "payment_key": None,
    "payment_mode": "demo",
    "created_at": "2026-11-05T11:20:00+09:00",
})
for _o in orders:
    _o.setdefault("postcode", "05551")
    _o.setdefault("points_used", 0)

# v1.9.1 — 리뷰 페이징(5개씩)을 확인할 수 있도록 코트(p_001) 리뷰가 있는 배송완료 주문을 추가한다.
# 6건을 서로 다른 회원(u_003~u_005)의 주문으로 넣어, 실제 구매자만 리뷰를 쓸 수 있다는 규칙과도 맞춘다.
_EXTRA_ORDERS = [
    ("o_007", "MA20261029-3311", "u_003", "2026-10-29T13:10:00+09:00"),
    ("o_008", "MA20261108-4420", "u_003", "2026-11-08T11:25:00+09:00"),
    ("o_009", "MA20261113-5527", "u_004", "2026-11-13T16:40:00+09:00"),
    ("o_010", "MA20261119-6634", "u_004", "2026-11-19T09:55:00+09:00"),
    ("o_011", "MA20261123-7741", "u_005", "2026-11-23T15:05:00+09:00"),
    ("o_012", "MA20261126-8858", "u_005", "2026-11-26T10:15:00+09:00"),
]
for _id, _no, _uid, _created in _EXTRA_ORDERS:
    orders.append({
        "id": _id, "order_no": _no, "user_id": _uid, "status": "delivered",
        "total_amount": 289000, "shipping_fee": 0, "coupon_code": None, "discount_amount": 0,
        "recipient_name": next(u["name"] for u in users if u["id"] == _uid),
        "recipient_phone": EXAMPLE_PHONE, "shipping_address": EXAMPLE_ADDRESS,
        "postcode": "05551", "points_used": 0,
        "payment_method": "card", "payment_provider": "demo", "payment_key": None,
        "payment_mode": "demo", "created_at": _created,
    })
# v1.9.6 — 「월별 매출 추이」 그래프(최근 6개월)를 바로 확인할 수 있도록 6~9월 배송완료 주문 4건을 더 둔다.
#   · 데모 계정(u_001)의 마이페이지 주문 목록은 그대로 두려고 다른 회원(u_003~u_005)의 주문으로 넣는다
#   · 금액 = 상품금액 + 배송비(3,000원, 무료배송 기준 미달인 89,000원 주문만) − 할인 0
_HISTORY_ORDERS = [
    # (order_id, order_item_id, order_no, user_id, created_at, variant, 상품명, 컬러, 사이즈, 단가, 배송비)
    ("o_013", "oi_014", "MA20260618-1201", "u_003", "2026-06-18T11:10:00+09:00", "v_047", "오버사이즈 코튼 셔츠", "화이트", "S", 89000, 3000),
    ("o_014", "oi_015", "MA20260709-2415", "u_004", "2026-07-09T16:05:00+09:00", "v_054", "플리츠 미디 스커트", "차콜", "M", 139000, 0),
    ("o_015", "oi_016", "MA20260821-3372", "u_005", "2026-08-21T10:40:00+09:00", "v_074", "와이드 데님 팬츠", "미드블루", "M", 109000, 0),
    ("o_016", "oi_017", "MA20260915-4188", "u_003", "2026-09-15T14:25:00+09:00", "v_023", "와이드 테일러드 트라우저", "블랙", "M", 149000, 0),
]
for _hid, _hoiid, _hno, _huid, _hcreated, _hvid, _hname, _hcolor, _hsize, _hprice, _hship in _HISTORY_ORDERS:
    orders.append({
        "id": _hid, "order_no": _hno, "user_id": _huid, "status": "delivered",
        "total_amount": _hprice + _hship, "shipping_fee": _hship, "coupon_code": None, "discount_amount": 0,
        "recipient_name": next(u["name"] for u in users if u["id"] == _huid),
        "recipient_phone": EXAMPLE_PHONE, "shipping_address": EXAMPLE_ADDRESS,
        "postcode": "05551", "points_used": 0,
        "payment_method": "card", "payment_provider": "demo", "payment_key": None,
        "payment_mode": "demo", "created_at": _hcreated,
    })
    order_items.append({
        "id": _hoiid, "order_id": _hid, "variant_id": _hvid, "product_name": _hname,
        "color": _hcolor, "size": _hsize, "unit_price": _hprice, "quantity": 1,
    })

# v1.9.12 — 코트(p_001) 리뷰를 12건으로 늘려 5건씩 페이징 3페이지를 바로 눌러볼 수 있게 한다.
#   · 각 리뷰는 서로 다른 회원의 배송완료 주문항목에 붙는다(구매자만 리뷰 작성 규칙과 동일)
#   · 주문일은 모두 2026-11 — 월별 매출 추이(최근 6개월)에 새 달이 끼어들지 않게 한다
_NEW_REVIEW_ORDERS = [
    # (order_id, order_item_id, order_no, user_id, created_at, variant, 컬러, 사이즈)
    ("o_017", "oi_018", "MA20261124-9961", "u_003", "2026-11-24T09:40:00+09:00", "v_002", "차콜", "M"),
    ("o_018", "oi_019", "MA20261122-7742", "u_004", "2026-11-22T13:15:00+09:00", "v_007", "카멜", "L"),
    ("o_019", "oi_020", "MA20261119-6633", "u_005", "2026-11-19T18:05:00+09:00", "v_009", "블랙", "S"),
    ("o_020", "oi_021", "MA20261114-5514", "u_003", "2026-11-14T10:25:00+09:00", "v_005", "카멜", "S"),
    ("o_021", "oi_022", "MA20261102-4407", "u_004", "2026-11-02T15:35:00+09:00", "v_011", "블랙", "L"),
]
for _nid, _noiid, _nno, _nuid, _ncreated, _nvid, _ncolor, _nsize in _NEW_REVIEW_ORDERS:
    orders.append({
        "id": _nid, "order_no": _nno, "user_id": _nuid, "status": "delivered",
        "total_amount": 289000, "shipping_fee": 0, "coupon_code": None, "discount_amount": 0,
        "recipient_name": next(u["name"] for u in users if u["id"] == _nuid),
        "recipient_phone": EXAMPLE_PHONE, "shipping_address": EXAMPLE_ADDRESS,
        "postcode": "05551", "points_used": 0,
        "payment_method": "card", "payment_provider": "demo", "payment_key": None,
        "payment_mode": "demo", "created_at": _ncreated,
    })
    order_items.append({
        "id": _noiid, "order_id": _nid, "variant_id": _nvid, "product_name": "울 더블 브레스티드 코트",
        "color": _ncolor, "size": _nsize, "unit_price": 289000, "quantity": 1,
    })

# o_001 의 니트(oi_001)는 이미 구매확정 + 포토리뷰 적립이 끝난 상태 — 트라우저(oi_002)는 눌러볼 수 있게 남겨 둔다.
_CONFIRMED = {
    "oi_001": ("2026-11-22T10:05:00+09:00", 1290, 1935, "2026-11-22T10:20:00+09:00"),
}
for _oi in order_items:
    _c = _CONFIRMED.get(_oi["id"])
    _oi["confirmed_at"] = _c[0] if _c else None
    _oi["confirm_points"] = _c[1] if _c else 0
    _oi["photo_bonus"] = _c[2] if _c else 0
    _oi["photo_bonus_at"] = _c[3] if _c else None

# 교환/반품 접수(클레임) 시드 — 관리자 콘솔에서 바로 확인할 수 있도록 무료·유료 각 1건.
#   · 무료: 제품 하자(판매자 귀책) → 배송비 0원, payment_status='free'
#   · 유료: 교환 + 사이즈 변경 → 왕복 6,000원 결제 완료(payment_status='paid'), 수거중('approved')
# o_001(배송완료)은 접수 이력이 없어 데모 계정으로 로그인하자마자 「교환/반품 신청」을 눌러볼 수 있다.
claims = [
    {
        "id": "oc_20261119_1001",
        "order_id": "o_004",
        "user_id": "u_001",
        "claim_type": "return",
        "reason_category": "defect",
        "reason_detail": "밑단 박음질이 풀려 있고 오른쪽 무릎 부분에 5cm 정도 올이 나 있습니다.",
        "shipping_fee": 0,
        "payment_status": "free",
        "payment_key": None,
        "payment_mode": "free",
        "exchange_option": None,
        "status": "requested",
        "stock_restored": 0,
        "admin_memo": "11/20 수거 택배 접수 · 검수 후 무료 반품 처리 예정",
        "created_at": "2026-11-19T09:20:00+09:00",
        "updated_at": "2026-11-19T09:20:00+09:00",
    },
    {
        "id": "oc_20261121_1002",
        "order_id": "o_005",
        "user_id": "u_001",
        "claim_type": "exchange",
        "reason_category": "size_color",
        "reason_detail": "허리가 조금 커서 S 사이즈로 교환하고 싶습니다.",
        "shipping_fee": 6000,
        "payment_status": "paid",
        "payment_key": "test_claim_seed_6f1c",
        "payment_mode": "test-client",
        "exchange_option": "차콜 / S",
        "status": "approved",
        "stock_restored": 0,
        "admin_memo": "",
        "created_at": "2026-11-21T10:12:00+09:00",
        "updated_at": "2026-11-22T09:00:00+09:00",
    },
]

# ------------------------------------------------------------------- coupons
coupons = [
    {
        "id": "c_001", "code": "WELCOME10", "name": "신규 회원 10% 할인",
        "discount_type": "percent", "discount_value": 10, "min_order_amount": 30000,
        "expires_at": "2027-12-31T23:59:59+09:00", "is_active": True,
        "target_user_ids": [],          # [] = 전체 공용
        "target_grades": [],             # [] = 등급 제한 없음
        "target_categories": [],         # v1.9.13 [] = 카테고리 조건 없음
        "target_badges": [],             # v1.9.13 [] = 뱃지 조건 없음
        "created_at": "2026-11-01T10:00:00+09:00",
    },
    {
        "id": "c_002", "code": "MONO5000", "name": "5,000원 할인 쿠폰",
        "discount_type": "fixed", "discount_value": 5000, "min_order_amount": 50000,
        "expires_at": "2027-06-30T23:59:59+09:00", "is_active": True,
        "target_user_ids": [],
        "target_grades": [],
        "target_categories": [],
        "target_badges": [],
        "created_at": "2026-11-05T10:00:00+09:00",
    },
    {
        # 특정 회원 전용 쿠폰(데모: 홍길동 u_001). 다른 계정에는 목록에 보이지 않고 코드 입력도 거부된다.
        "id": "c_003", "code": "VIP15", "name": "VIP 회원 전용 15% 할인",
        "discount_type": "percent", "discount_value": 15, "min_order_amount": 50000,
        "expires_at": "2027-03-31T23:59:59+09:00", "is_active": True,
        "target_user_ids": ["u_001"], "target_grades": [],   # 특정 회원 지정
        "target_categories": [],
        "target_badges": [],
        "created_at": "2026-11-20T10:00:00+09:00",
    },
    {
        # v1.9.13 — 복합 조건 쿠폰: 골드 등급 + 잡의·야우터 카테고리 + BEST 뱃지
        #   p_005 스무스 레더 숄더백(잡의·BEST 259,000원), p_001 코트(야우터·BEST 289,000원) 이 해당된다.
        "id": "c_004", "code": "GOLD20", "name": "골드 전용 20% — 잡의·야우터 BEST",
        "discount_type": "percent", "discount_value": 20, "min_order_amount": 100000,
        "expires_at": "2027-06-30T23:59:59+09:00", "is_active": True,
        "target_user_ids": [], "target_grades": ["GOLD"],
        "target_categories": ["acc", "outer"], "target_badges": ["BEST"],
        "created_at": "2026-11-28T09:00:00+09:00",
    },
]

# ------------------------------------------------------- v1.9 포인트 정책
# 등급별 적립률(%) — 관리자 「포인트/회원」에서 수정한다.
POINT_POLICIES = {
    "NORMAL": {"confirm_rate": 0.5, "photo_rate": 1.0},
    "SILVER": {"confirm_rate": 0.7, "photo_rate": 1.2},
    "GOLD":   {"confirm_rate": 1.0, "photo_rate": 1.5},
    "VIP":    {"confirm_rate": 1.5, "photo_rate": 2.0},
}
point_policies = [
    {"grade": g, "confirm_rate": v["confirm_rate"], "photo_rate": v["photo_rate"],
     "updated_at": "2026-11-27T08:30:00+09:00"}
    for g, v in POINT_POLICIES.items()
]

# ------------------------------------------------------- v1.9 상품 리뷰
# 구매한 주문항목(order_item_id)에 1건씩 — 별점·텍스트·사진/동영상(Data URL 또는 asset 경로)
# v1.9.1 — status(published/rejected)·rejected_reason·reclaimed_points 로 관리자 리뷰 검수·포인트 회수를 기록한다.
product_reviews = [
    {
        "id": "rv_001", "product_id": "p_002", "user_id": "u_001", "user_name": "홍길*",
        "order_item_id": "oi_001", "rating": 5,
        "content": "캐시미어라 그런지 정말 부드럽고 목선이 답답하지 않아요. 크림 색도 화면과 거의 같고, 코트 안에 입어도 두께감이 부담스럽지 않습니다.",
        "media": [
            {"type": "image", "src": "knit-detail.webp", "name": "착용 디테일"},
            {"type": "image", "src": "knit-fabric.webp", "name": "소재 클로즈업"},
        ],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-22T10:20:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_002", "product_id": "p_003", "user_id": "u_001", "user_name": "홍길*",
        "order_item_id": "oi_002", "rating": 4,
        "content": "허리선이 높아서 다리가 길어 보입니다. 기장이 조금 길어 힐을 신어야 하지만 핏은 만족해요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-18T09:10:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_003", "product_id": "p_001", "user_id": "u_001", "user_name": "홍길*",
        "order_item_id": "oi_007", "rating": 5,
        "content": "무게감이 있지만 어깨가 편하고, 차콜 색이 사진보다 더 깊어 보입니다. 오래 입을 코트로 추천합니다.",
        "media": [
            {"type": "image", "src": "coat-detail.webp", "name": "코트 디테일"},
        ],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-12T14:40:00+09:00", "updated_at": None,
    },
    # v1.9.1 — 코트(p_001) 리뷰 6건 추가: 5개씩 페이징(1페이지 5건 → 2페이지 2건) 확인용
    {
        "id": "rv_004", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "order_item_id": "oi_008", "rating": 5,
        "content": "겨울 코트로 정말 따뜻합니다. 차콜 색이 어디에나 어울리고 어깨 패드가 있어서 라인이 깔끔해요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-10-30T09:15:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_005", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "order_item_id": "oi_009", "rating": 4,
        "content": "카멜 색이 사진보다 조금 노랗게 보여서 별 하나 뺐어요. 핏과 소재는 만족합니다.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-09T18:05:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_006", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "order_item_id": "oi_010", "rating": 5,
        "content": "키 178에 M 샀는데 소매가 딱 맞습니다. 두꺼운 니트 위에 입어도 여유가 있어요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-14T11:30:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_007", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "order_item_id": "oi_011", "rating": 4,
        "content": "블랙은 먼지가 조금 붙지만 실루엣이 정말 예쁩니다. 드라이클리닝 한 번 했는데 모양 그대로예요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-20T13:45:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_008", "product_id": "p_001", "user_id": "u_005", "user_name": "홍길*",
        "order_item_id": "oi_012", "rating": 5,
        "content": "배송이 빠르고 포장도 깔끔했습니다. 차콜 L 사이즈가 저한테 딱이에요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-24T08:20:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_009", "product_id": "p_001", "user_id": "u_005", "user_name": "홍길*",
        "order_item_id": "oi_013", "rating": 5,
        "content": "XL 사이즈를 남편 선물로 샀는데 아주 좋아합니다. 단추가 묵직해서 고급스러워요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-26T19:10:00+09:00", "updated_at": None,
    },
    # v1.9.12 — 코트(p_001) 리뷰 12건(5건씩 3페이지) — 새로 넣은 주문항목(oi_018~oi_022)에 1건씩
    {
        "id": "rv_010", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "order_item_id": "oi_018", "rating": 5,
        "content": "출근할 때마다 입는데 차콜 M이 정장 위에도 잘 어울립니다. 안감이 있어서 목이 따뜻하고, 주머니 깊이도 만족스러워요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-26T08:50:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_011", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "order_item_id": "oi_019", "rating": 4,
        "content": "카멜 L을 아내와 같이 입으려고 샀습니다. 색이 은은하고 좋은데 어깨가 조금 넓게 나온 편이라 별 하나 뺐어요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-25T20:10:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_012", "product_id": "p_001", "user_id": "u_005", "user_name": "홍길*",
        "order_item_id": "oi_020", "rating": 5,
        "content": "블랙 S인데 어깨선이 딱 떨어져서 좋습니다. 무게가 있어 한겨울까지는 충분히 따뜻할 것 같아요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-21T12:30:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_013", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "order_item_id": "oi_021", "rating": 5,
        "content": "카멜 S가 어머니 선물로 딱이었습니다. 포장도 단정하고 단추 마감이 튼튼해서 오래 입을 수 있을 것 같아요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-16T19:05:00+09:00", "updated_at": None,
    },
    {
        "id": "rv_014", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "order_item_id": "oi_022", "rating": 3,
        "content": "블랙 L을 주문했는데 배송이 예정보다 나흘 늦었습니다. 옷 자체는 마음에 들지만 소매가 길어 수선이 필요해요.",
        "media": [],
        "status": "published", "rejected_reason": None, "reclaimed_points": 0, "rejected_at": None,
        "created_at": "2026-11-04T09:15:00+09:00", "updated_at": None,
    },
]

# ------------------------------------------------------- v1.9.2 리뷰 재작성 추적
# · order_items.review_attempts = 리뷰 작성 횟수(1 = 최초, 2 = 반려 후 재작성)
# · order_items.rewrite_used    = 재작성 기회를 이미 썼는지(0/1)
# · product_reviews.attempt     = 리뷰 차수(1/2) — 같은 주문항목의 이력을 남긴다
for _r in product_reviews:
    _r["attempt"] = 1
for _oi in order_items:
    _mine = [r for r in product_reviews if r["order_item_id"] == _oi["id"]]
    _oi["review_attempts"] = len(_mine)
    _oi["rewrite_used"] = 0

# ------------------------------------------------------- v1.9.11 상품 Q&A
# 상품 상세의 「상품 Q&A」 시드 — 답변완료·미답변·비밀글 예시를 섞어 6건.
#   qna_type: product(상품 문의) / delivery(배송 문의) / claim(교환·반품) / etc(기타)
#   status 는 answer 유무와 항상 같다(answered_at 이 있으면 answer 도 있다).
product_qnas = [
    {
        "id": "q_001", "product_id": "p_001", "user_id": "u_001", "user_name": "홍길*",
        "qna_type": "product", "title": "173cm 62kg이면 M 사이즈 괜찮을까요?",
        "content": "코트 안에 두꺼운 니트를 입고 싶은데 M이 넉넉할지 궁금합니다. 평소 95~100 사이즈를 입습니다.",
        "is_secret": 0, "answer": "어깨가 여유 있는 실루엣이라 173cm·62kg 이시면 M 사이즈가 잘 맞습니다. 두꺼운 니트를 입으실 예정이면 L도 여유 있게 잘 어울립니다.",
        "answered_by": "u_002", "answered_at": "2026-11-20T10:12:00+09:00",
        "status": "answered", "created_at": "2026-11-19T21:40:00+09:00", "updated_at": "2026-11-20T10:12:00+09:00",
    },
    {
        "id": "q_002", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "qna_type": "delivery", "title": "오늘 결제하면 오늘 출고되나요?",
        "content": "내일 외출에 입고 나가려고 하는데 오늘 오후 1시에 결제하면 당일 출고가 가능할까요?",
        "is_secret": 0, "answer": "", "answered_by": None, "answered_at": None,
        "status": "pending", "created_at": "2026-11-25T12:58:00+09:00", "updated_at": None,
    },
    {
        "id": "q_003", "product_id": "p_002", "user_id": "u_001", "user_name": "홍길*",
        "qna_type": "product", "title": "세탁은 어떻게 해야 하나요?",
        "content": "캐시미어라 드라이클리닝만 해야 하는지, 집에서 손세탁도 괜찮은지 문의드립니다.",
        "is_secret": 1,
        "answer": "캐시미어 20% 혼방이라 드라이클리닝을 권장합니다. 집에서 손세탁하실 때는 찬물에 중성세제로 가볍게 주무르고 평평하게 눕혀 건조해 주세요.",
        "answered_by": "u_002", "answered_at": "2026-11-23T09:30:00+09:00",
        "status": "answered", "created_at": "2026-11-22T18:20:00+09:00", "updated_at": "2026-11-23T09:30:00+09:00",
    },
    {
        "id": "q_004", "product_id": "p_002", "user_id": "u_004", "user_name": "홍길*",
        "qna_type": "claim", "title": "받은 니트에 올이 풀린 곳이 있어요",
        "content": "소매 안쪽에 올이 풀린 부분이 있는데 교환하면 재고가 있을까요? 색상은 크림입니다.",
        "is_secret": 1, "answer": "", "answered_by": None, "answered_at": None,
        "status": "pending", "created_at": "2026-11-27T08:15:00+09:00", "updated_at": None,
    },
    {
        "id": "q_005", "product_id": "p_003", "user_id": "u_005", "user_name": "홍길*",
        "qna_type": "product", "title": "기장 수선이 가능한가요?",
        "content": "와이드 팬츠 기장이 조금 길 것 같아서 수선해서 입으려고 합니다. 밑단 원단 여유가 있는지 궁금합니다.",
        "is_secret": 0, "answer": "밑단 안쪽에 3cm 정도 시접 여유가 있어 수선집에서 줄이거나 늘릴 수 있습니다.",
        "answered_by": "u_002", "answered_at": "2026-11-21T15:05:00+09:00",
        "status": "answered", "created_at": "2026-11-21T11:32:00+09:00", "updated_at": "2026-11-21T15:05:00+09:00",
    },
    {
        "id": "q_006", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "qna_type": "etc", "title": "선물 포장도 가능할까요?",
        "content": "생일 선물로 보내려고 하는데 리본 포장과 메시지 카드를 같이 넣어 주실 수 있는지 문의드립니다.",
        "is_secret": 0, "answer": "", "answered_by": None, "answered_at": None,
        "status": "pending", "created_at": "2026-11-26T19:44:00+09:00", "updated_at": None,
    },
    # v1.9.12 — 코트(p_001) Q&A 12건(5건씩 3페이지) + 다른 상품 문의와 섞어 관리자 목록도 15건
    {
        "id": "q_007", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "qna_type": "product", "title": "소매 기장이 많이 길까요?",
        "content": "173cm인데 소매가 손등을 덮을 정도로 길게 나오는지 궁금합니다. 수선 없이 입고 싶습니다.",
        "is_secret": 0,
        "answer": "173cm 기준으로 소매 끝이 손목 뼈를 살짝 덮는 정도입니다. 손등까지 오지는 않아 수선 없이 입으시는 분이 많습니다.",
        "answered_by": "u_002", "answered_at": "2026-11-24T10:40:00+09:00",
        "status": "answered", "created_at": "2026-11-23T21:15:00+09:00", "updated_at": "2026-11-24T10:40:00+09:00",
    },
    {
        "id": "q_008", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "qna_type": "delivery", "title": "주말에 주문하면 월요일 출고인가요?",
        "content": "토요일 오전에 결제하면 주말에는 출고가 안 되는지, 월요일에 바로 나가는지 궁금합니다.",
        "is_secret": 0, "answer": "", "answered_by": None, "answered_at": None,
        "status": "pending", "created_at": "2026-11-27T10:20:00+09:00", "updated_at": None,
    },
    {
        "id": "q_009", "product_id": "p_001", "user_id": "u_005", "user_name": "홍길*",
        "qna_type": "product", "title": "차콜과 블랙 중 먼지가 덜 붙는 색은?",
        "content": "검정 계열 코트는 먼지가 잘 보인다고 해서 고민입니다. 두 색 중 어떤 쪽이 관리하기 편한가요?",
        "is_secret": 0,
        "answer": "블랙은 먼지·털이 조금 더 잘 보입니다. 차콜은 같은 검정 계열이라도 결이 있어서 관리가 조금 수월합니다.",
        "answered_by": "u_002", "answered_at": "2026-11-22T09:05:00+09:00",
        "status": "answered", "created_at": "2026-11-21T18:40:00+09:00", "updated_at": "2026-11-22T09:05:00+09:00",
    },
    {
        "id": "q_010", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "qna_type": "claim", "title": "단추 하나가 흔들려서 왔어요",
        "content": "받은 코트의 두 번째 단추가 흔들립니다. 교환 없이 단추만 다시 달아 주실 수 있을까요?",
        "is_secret": 1, "answer": "", "answered_by": None, "answered_at": None,
        "status": "pending", "created_at": "2026-11-26T13:05:00+09:00", "updated_at": None,
    },
    {
        "id": "q_011", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "qna_type": "product", "title": "175cm 70kg이면 L 사이즈가 맞을까요?",
        "content": "평소 100 사이즈를 입습니다. 니트 위에 입을 생각인데 L이 넉넉할지 문의드립니다.",
        "is_secret": 0,
        "answer": "175cm·70kg에 100 사이즈를 입으시면 L이 잘 맞습니다. 두꺼운 니트 위에도 여유가 있습니다.",
        "answered_by": "u_002", "answered_at": "2026-11-20T11:20:00+09:00",
        "status": "answered", "created_at": "2026-11-19T22:10:00+09:00", "updated_at": "2026-11-20T11:20:00+09:00",
    },
    {
        "id": "q_012", "product_id": "p_001", "user_id": "u_005", "user_name": "홍길*",
        "qna_type": "etc", "title": "카멜 XL 재입고 예정이 있나요?",
        "content": "카멜 XL이 품절로 보이는데 재입고 계획이 있는지 궁금합니다.",
        "is_secret": 0, "answer": "", "answered_by": None, "answered_at": None,
        "status": "pending", "created_at": "2026-11-25T08:35:00+09:00", "updated_at": None,
    },
    {
        "id": "q_013", "product_id": "p_001", "user_id": "u_003", "user_name": "홍길*",
        "qna_type": "product", "title": "안감이 있는 코트인가요?",
        "content": "목이 따가운 소재를 못 입어서요. 안감 재질과 두께를 알려 주시면 감사하겠습니다.",
        "is_secret": 0,
        "answer": "폴리에스터 안감이 등판까지 들어가 있습니다. 목에 닿는 부분은 울 원단이 아니라 안감이 닿도록 마감되어 있습니다.",
        "answered_by": "u_002", "answered_at": "2026-11-17T15:45:00+09:00",
        "status": "answered", "created_at": "2026-11-16T12:00:00+09:00", "updated_at": "2026-11-17T15:45:00+09:00",
    },
    {
        "id": "q_014", "product_id": "p_001", "user_id": "u_004", "user_name": "홍길*",
        "qna_type": "delivery", "title": "제주도도 배송되나요?",
        "content": "제주에 계신 부모님께 보내려고 합니다. 도서산간 추가 배송비가 있는지 궁금합니다.",
        "is_secret": 1,
        "answer": "제주도 배송 가능하며 도서산간 추가 배송비 3,000원이 있습니다. 주문서 작성 시 자동으로 합산됩니다.",
        "answered_by": "u_002", "answered_at": "2026-11-13T09:50:00+09:00",
        "status": "answered", "created_at": "2026-11-12T20:25:00+09:00", "updated_at": "2026-11-13T09:50:00+09:00",
    },
    {
        "id": "q_015", "product_id": "p_001", "user_id": "u_005", "user_name": "홍길*",
        "qna_type": "product", "title": "세탁 후에 털이 많이 빠지나요?",
        "content": "드라이클리닝을 맡기면 털 빠짐이 심한지, 집에서 관리할 때 주의할 점이 있는지 문의드립니다.",
        "is_secret": 0, "answer": "", "answered_by": None, "answered_at": None,
        "status": "pending", "created_at": "2026-11-18T09:10:00+09:00", "updated_at": None,
    },
]

# ------------------------------------------------------- v1.9.11 리뷰 추천/비추천
# 리뷰 1건에 회원 1명이 추천(up) 또는 비추천(down) 하나만 남긴다(본인 리뷰는 제외).
review_votes = [
    {"id": "rvv_001", "review_id": "rv_001", "user_id": "u_003", "vote": "up", "created_at": "2026-11-22T12:00:00+09:00"},
    {"id": "rvv_002", "review_id": "rv_001", "user_id": "u_004", "vote": "up", "created_at": "2026-11-22T15:10:00+09:00"},
    {"id": "rvv_003", "review_id": "rv_003", "user_id": "u_003", "vote": "up", "created_at": "2026-11-13T09:00:00+09:00"},
    {"id": "rvv_004", "review_id": "rv_003", "user_id": "u_004", "vote": "up", "created_at": "2026-11-14T10:20:00+09:00"},
    {"id": "rvv_005", "review_id": "rv_003", "user_id": "u_005", "vote": "up", "created_at": "2026-11-15T19:40:00+09:00"},
    {"id": "rvv_006", "review_id": "rv_004", "user_id": "u_001", "vote": "up", "created_at": "2026-10-31T08:30:00+09:00"},
    {"id": "rvv_007", "review_id": "rv_004", "user_id": "u_004", "vote": "up", "created_at": "2026-11-01T13:05:00+09:00"},
    {"id": "rvv_008", "review_id": "rv_004", "user_id": "u_005", "vote": "down", "created_at": "2026-11-02T17:25:00+09:00"},
    {"id": "rvv_009", "review_id": "rv_005", "user_id": "u_001", "vote": "down", "created_at": "2026-11-10T09:15:00+09:00"},
    {"id": "rvv_010", "review_id": "rv_005", "user_id": "u_004", "vote": "down", "created_at": "2026-11-11T11:45:00+09:00"},
    {"id": "rvv_011", "review_id": "rv_006", "user_id": "u_001", "vote": "up", "created_at": "2026-11-15T10:00:00+09:00"},
    {"id": "rvv_012", "review_id": "rv_006", "user_id": "u_003", "vote": "up", "created_at": "2026-11-16T12:30:00+09:00"},
    {"id": "rvv_013", "review_id": "rv_007", "user_id": "u_005", "vote": "up", "created_at": "2026-11-21T09:50:00+09:00"},
    {"id": "rvv_014", "review_id": "rv_008", "user_id": "u_001", "vote": "up", "created_at": "2026-11-25T08:10:00+09:00"},
    {"id": "rvv_015", "review_id": "rv_002", "user_id": "u_005", "vote": "up", "created_at": "2026-11-19T14:00:00+09:00"},
    # v1.9.12 — 새로 넣은 코트 리뷰(rv_010·rv_011·rv_012·rv_014)에 추천/비추천 표
    {"id": "rvv_016", "review_id": "rv_010", "user_id": "u_001", "vote": "up", "created_at": "2026-11-26T11:20:00+09:00"},
    {"id": "rvv_017", "review_id": "rv_010", "user_id": "u_005", "vote": "up", "created_at": "2026-11-26T15:05:00+09:00"},
    {"id": "rvv_018", "review_id": "rv_011", "user_id": "u_003", "vote": "up", "created_at": "2026-11-26T09:40:00+09:00"},
    {"id": "rvv_019", "review_id": "rv_012", "user_id": "u_004", "vote": "up", "created_at": "2026-11-22T08:30:00+09:00"},
    {"id": "rvv_020", "review_id": "rv_014", "user_id": "u_001", "vote": "down", "created_at": "2026-11-05T10:10:00+09:00"},
    {"id": "rvv_021", "review_id": "rv_014", "user_id": "u_005", "vote": "down", "created_at": "2026-11-06T19:35:00+09:00"},
]

# ------------------------------------------------------- v1.9.2 발송 로그(통합)
# SMS(주문 완료 안내) + 이메일 인증번호 발송을 한 표에 기록 — 관리자 「발송 로그」 탭.
# status: test(테스트 발송) / sent(발송) / blocked(쿨다운·과다로 차단) / failed(실패)
dispatch_logs = [
    {
        "id": "dsp_001", "channel": "sms", "to": "010-0000-0000", "kind": "order_created",
        "summary": "[MONO ATELIER] 홍길동님 주문이 접수되었습니다. MA20261112-4821 · 캐시미어 리브 니트 외 1건 · 결제 278,000원. 배송은 준비 후 순차적으로 진행됩니다.",
        "status": "test", "mode": "test", "order_id": "o_001", "created_at": "2026-11-12T10:24:00+09:00",
    },
    {
        "id": "dsp_002", "channel": "email", "to": "signup-test@mono.kr", "kind": "email_otp",
        "summary": "[MONO ATELIER] 회원가입 이메일 인증번호 발송 (6자리, 5분 유효)",
        "status": "test", "mode": "test", "order_id": None, "created_at": "2026-11-26T21:14:00+09:00",
    },
    {
        "id": "dsp_003", "channel": "email", "to": "signup-test@mono.kr", "kind": "email_otp",
        "summary": "인증번호 재발송 차단 — 쿨다운 41초 남음",
        "status": "blocked", "mode": "test", "order_id": None, "created_at": "2026-11-26T21:14:19+09:00",
    },
]

# ------------------------------------------------------- v1.9 포인트 내역
# users.points 와 합계가 일치해야 한다 (u_001: 2000 − 500 + 1290 + 1935 = 4725)
point_logs = [
    {"id": "pl_001", "user_id": "u_001", "type": "signup", "amount": 2000,
     "base_amount": 0, "rate": 0, "order_id": None, "order_item_id": None, "review_id": None,
     "description": "가입 축하 포인트", "created_at": "2026-11-09T10:42:00+09:00"},
    {"id": "pl_002", "user_id": "u_001", "type": "use", "amount": -500,
     "base_amount": 0, "rate": 0, "order_id": "o_005", "order_item_id": None, "review_id": None,
     "description": "주문 결제에 포인트 사용", "created_at": "2026-11-16T14:30:00+09:00"},
    {"id": "pl_003", "user_id": "u_001", "type": "confirm", "amount": 1290,
     "base_amount": 129000, "rate": 1.0, "order_id": "o_001", "order_item_id": "oi_001", "review_id": None,
     "description": "구매확정 적립 (골드 1.0%)", "created_at": "2026-11-22T10:05:00+09:00"},
    {"id": "pl_004", "user_id": "u_001", "type": "photo_review", "amount": 1935,
     "base_amount": 129000, "rate": 1.5, "order_id": "o_001", "order_item_id": "oi_001", "review_id": "rv_001",
     "description": "포토·영상 리뷰 추가 적립 (골드 1.5%)", "created_at": "2026-11-22T10:20:00+09:00"},
]

# ------------------------------------------------------------- v1.9 FAQ 게시판
faqs = [
    {"id": "faq_001", "category": "배송", "question": "배송은 얼마나 걸리나요?",
     "answer": "평일 오후 2시 이전 결제 건은 당일 출고됩니다. 수도권은 출고 후 1~2일, 지방은 2~3일 정도 소요되며 제주·도서산간은 하루 더 걸릴 수 있습니다.", "sort_order": 1, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
    {"id": "faq_002", "category": "배송", "question": "무료배송 기준은 어떻게 되나요?",
     "answer": "기본 100,000원 이상 구매 시 무료배송입니다. 상품에 별도 기준이 있는 경우 상품 상세의 배송 안내를 확인해 주세요(0원 = 무조건 무료배송).", "sort_order": 2, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
    {"id": "faq_003", "category": "주문/결제", "question": "쿠폰과 포인트를 같이 사용할 수 있나요?",
     "answer": "네. 결제 화면에서 쿠폰을 적용한 뒤 보유 포인트를 원하는 만큼 입력해 사용할 수 있습니다. 포인트는 결제 금액을 넘지 않게 사용되며, 남은 금액만 결제됩니다.", "sort_order": 3, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
    {"id": "faq_004", "category": "주문/결제", "question": "주문 취소는 언제까지 가능한가요?",
     "answer": "상품 준비 단계까지 마이페이지 > 주문 내역에서 직접 취소할 수 있습니다. 배송이 시작된 뒤에는 취소할 수 없으며 교환·반품으로 접수해 주세요. 취소 시 사용한 포인트는 다시 적립됩니다.", "sort_order": 4, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
    {"id": "faq_005", "category": "교환/반품", "question": "교환·반품 배송비는 얼마인가요?",
     "answer": "제품 하자·오배송은 판매자 귀책으로 무료입니다. 단순 변심·사이즈/색상 변경은 반품 3,000원, 교환(왕복) 6,000원입니다. 수령 후 7일 이내 신청해 주세요.", "sort_order": 5, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
    {"id": "faq_006", "category": "회원/포인트", "question": "포인트는 어떻게 적립되나요?",
     "answer": "구매확정 시 결제 금액의 등급별 적립률(일반 0.5% · 실버 0.7% · 골드 1.0% · VIP 1.5%)만큼 적립됩니다. 사진이나 동영상을 첨부한 리뷰를 등록하면 등급별 추가 적립률(1.0~2.0%)이 한 번 더 지급됩니다.", "sort_order": 6, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
    {"id": "faq_007", "category": "회원/포인트", "question": "구매확정을 누르면 무엇이 바뀌나요?",
     "answer": "구매확정한 주문 상품은 적립 포인트가 즉시 지급되고, 같은 상품에 리뷰를 작성할 수 있습니다. 한 번 확정한 상품은 다시 확정할 수 없어 포인트가 중복 지급되지 않습니다.", "sort_order": 7, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
    {"id": "faq_008", "category": "상품", "question": "사이즈는 어떻게 고르면 좋나요?",
     "answer": "상품 상세의 실측 사이즈와 모델 착용 정보(키·몸무게·착용 사이즈)를 참고해 주세요. 평소 착용 사이즈와 실측 단면을 비교하면 가장 정확합니다.", "sort_order": 8, "is_active": True, "created_at": "2026-11-27T08:30:00+09:00"},
]

# --------------------------------------------------------- 사이트 설정 / 고객센터
# 관리자 「메인/사이트 관리」에서 편집한다. 공개 저장소용 예시값만 사용(실제 개인정보 0).
SITE_SETTINGS = {
    "id": "default",
    "top_banner_text": "FALL / WINTER 2026 — 10만 원 이상 무료배송",   # v1.9.3 상단 안내 띠(‘—’ 뒤 문구는 굵게 강조)
    "top_banner_sub": "평일 오후 2시 이전 당일 출고",                     # v1.9.3 보조 문구(비우면 숨김)
    "top_banner_enabled": True,                                          # v1.9.10 상단 안내 띠 노출 ON/OFF(기본 ON)
    "hero_image": "hero.webp",
    "hero_eyebrow": "FALL / WINTER 2026 — THE QUIET COLLECTION",
    "hero_title": "Quiet luxury,\nfor every day.",
    "hero_subtitle": "매일 손이 가는 단정한 실루엣.\n좋은 소재만 골라 만든 모노 아뜰리에의 가을·겨울.",
    "hero_cta_label": "컬렉션 보기",
    "hero_cta2_label": "브랜드 스토리",
    "hero_effect": "zoom",          # none | zoom | fade | slide
    "hero_overlay": 42,             # 0~90 (사진 위 어두운 오버레이 %)
    "brand_blurb": "단정한 실루엣, 좋은 소재. 서울에서 만드는 모던 컨템포러리 브랜드입니다.",
    "story_image": "coat.webp",
    "story_eyebrow": "ATELIER NOTE 01",
    "story_title": "옷장은 계절이 아니라,\n태도로 채워집니다.",
    "story_subtitle": "MONO ATELIER가 옷을 만드는 기준",
    "story_body": "한 벌의 코트가 계절을 견디는 방식은 화려함이 아니라 균형에 있습니다. 어깨선, 소매의 길이, 단추 하나의 간격까지.\n\n우리는 사진보다 실물에서 더 좋아 보이는 옷을 만듭니다. 유행을 따라가기보다 오래 입을 수 있는 실루엣을 고르고, 피부에 닿는 소재부터 확인합니다.",
    "story_tags": ["좋은 소재", "단정한 실루엣", "오래 입는 옷", "서울 제작"],
    "brand_story_enabled": True,          # v1.9.9 메인페이지 브랜드 스토리 노출 ON/OFF(기본 ON)
    # v1.9.10 상품 섹션(「이번 시즌, 새로 도착한 옷」) 헤더 — 관리자 「메인/사이트 → 상품 섹션」에서 편집
    "shop_eyebrow": "SHOP — NEW ARRIVALS",
    "shop_title": "이번 시즌, 새로 도착한 옷",
    "shop_desc": "단정한 실루엣과 좋은 소재. 유행보다 오래 입는 옷을 제안합니다.",
    # v1.9.14 — 사이트 타이틀(상단 로고·브라우저 탭 제목)과 푸터 카피라이트 — 관리자 「메인/사이트 → 타이틀/푸터」
    "site_title": "MONO ATELIER",
    "page_title": "MONO ATELIER — 모노 아틀리에",
    "footer_copyright": "© 2026 MONO ATELIER. ALL RIGHTS RESERVED.",
    "company_name": "모노 아뜰리에",
    "company_ceo": "홍길동",
    "company_reg_no": "000-00-00000",
    "company_mail_order_no": "제2026-서울송파-0000호",
    "company_address": "서울특별시 송파구 올림픽로 300 101동 1203호",
    "company_phone": "02-0000-0000",
    "company_email": "help@mono.kr",
    "email_auth_mode": "test",           # 회원가입 이메일 인증: test(화면에 인증번호 표시) | api(설정 URL 로 발송)
    "email_api_url": "",                   # 이메일 발송 API(Resend·Brevo·SMTP 백엔드 프록시)
    "sms_enabled": True,                   # 주문 완료 SMS 발송 여부
    "sms_mode": "test",                    # test(로그만 기록) | api(Webhook·SMS API 호출)
    "sms_api_url": "",                     # SMS 발송 Webhook/API URL
    "sms_sender": "02-0000-0000",          # 발신번호
    # v1.9.5 FAQ 카테고리(코드 목록) — 관리자 「FAQ 관리 → FAQ 카테고리 관리」에서 추가·삭제·순서 변경
    "faq_categories": ["배송", "주문/결제", "교환/반품", "회원/포인트", "상품", "기타"],
    # v1.9.13 — 상품 뱃지 코드 목록(관리자 「코드 관리 > 뱃지 관리」). 상품 등록·쿠폰 조건이 이 목록을 본다.
    "product_badges": ["BEST", "NEW", "SALE", "LIMITED"],
    # v1.9.13 — 사이트 전용 미디어(상품 사진과 분리). 히어로/스토리 각각 업로드·URL·삭제·선택.
    "hero_images": ["hero.webp", "coat.webp", "knit.webp", "trench.webp"],
    "story_images": ["coat.webp", "coat-fabric.webp", "knit-detail.webp", "trench.webp"],
    # v1.9.13 — 최근 N개월(기본 6) 실구매 금액 기준 멤버십 등급(원 이상)
    "member_grade_rules": {"months": 6,
                           "thresholds": {"NORMAL": 0, "SILVER": 200000, "GOLD": 400000, "VIP": 800000}},
    "updated_at": "2026-11-28T09:00:00+09:00",
}

# v1.9.10 — 홈 4칸 구성: 배송 안내 · 교환·반품 안내 · (FAQ 게시판) · 고객센터
#   「무료배송·당일출고」 칸은 FAQ 게시판으로 대체되어 HELP 항목에서 뺀다(내용은 「배송 안내」에 포함).
HELP_TOPICS = [
    {"id": "help_delivery", "title": "배송 안내", "sort_order": 1,
     "body": "평일 오후 2시 이전 결제 시 당일 출고됩니다.\n100,000원 이상 구매 시 무료배송이며, 미만은 배송비 3,000원입니다.\n제주·도서산간 지역은 추가 배송비가 발생할 수 있습니다."},
    {"id": "help_exchange", "title": "교환·반품 안내", "sort_order": 2,
     "body": "수령 후 7일 이내 교환·반품 신청이 가능합니다.\n제품 하자·오배송은 판매자 귀책으로 배송비가 무료이며, 단순 변심은 반품 3,000원 · 교환(왕복) 6,000원입니다.\n교환·반품은 마이페이지 → 주문 내역에서 신청할 수 있습니다."},
    {"id": "help_faq", "title": "고객센터", "sort_order": 3,
     "body": "고객센터 운영 시간: 평일 10:00 – 17:00\n점심 12:30 – 13:30, 주말·공휴일 휴무\n전화 02-0000-0000 · 이메일 help@mono.kr\n자주 묻는 질문은 홈 HELP 4칸의 「FAQ」에서 확인할 수 있습니다."},
]

# ------------------------------------------------- v1.9.1 주문 SMS 발송 로그
# 테스트 모드(sms_mode='test')에서 실제 발송 없이 남긴 기록 — 관리자 「데이터 관리」와 주문 상세에서 확인한다.
sms_logs = [
    {
        "id": "sms_001", "order_id": "o_001", "user_id": "u_001",
        "phone": "010-0000-0000",
        "message": "[MONO ATELIER] 홍길동님 주문이 접수되었습니다. MA20261112-4821 · 캐시미어 리브 니트 외 1건 · 결제 278,000원. 배송은 준비 후 순차적으로 진행됩니다.",
        "kind": "order_created", "status": "test", "mode": "test", "sender": "02-0000-0000",
        "api_url": "", "created_at": "2026-11-12T10:24:00+09:00",
    },
]

seed = {
    "meta": {
        "app": "MONO ATELIER",
        "schema_version": 14,
        "generated_at": "2026-11-27T16:10:00+09:00",
        "grades": ["NORMAL", "SILVER", "GOLD", "VIP"],
        "currency": "KRW",
        "free_shipping_threshold": FREE_SHIPPING,
        "shipping_fee": SHIPPING_FEE,
        "claim_return_fee": SHIPPING_FEE,
        "claim_exchange_fee": SHIPPING_FEE * 2,
        "password_hashing": "sha256('mono-atelier$' + password) — demo only",
    },
    "users": users,
    "categories": categories,
    "products": products,
    "product_images": product_images,
    "product_variants": variants,
    "cart_items": [],
    "orders": orders,
    "order_items": order_items,
    "order_claims": claims,
    "coupons": coupons,
    "product_reviews": product_reviews,
    "product_qnas": product_qnas,
    "review_votes": review_votes,
    "point_policies": point_policies,
    "point_logs": point_logs,
    "faqs": faqs,
    "sms_logs": sms_logs,
    "dispatch_logs": dispatch_logs,
    "site_settings": SITE_SETTINGS,
    "help_topics": HELP_TOPICS,
}

# sanity check seed integrity
assert len({p["id"] for p in products}) == len(products)
assert len({v["id"] for v in variants}) == len(variants)
for v in variants:
    assert any(p["id"] == v["product_id"] for p in products), v
for oi in order_items:
    assert any(o["id"] == oi["order_id"] for o in orders), oi
    if not any(v["id"] == oi["variant_id"] for v in variants):
        raise SystemExit("order item variant missing: " + oi["variant_id"])
    # 주문 스냅샷의 컬러·사이즈는 실제 옵션과 일치해야 한다(교환 옵션 선택의 기준)
    _v = next(v for v in variants if v["id"] == oi["variant_id"])
    assert (_v["color"], _v["size"]) == (oi["color"], oi["size"]), (oi["id"], _v["color"], _v["size"], oi["color"], oi["size"])
for o in orders:
    items = [i for i in order_items if i["order_id"] == o["id"]]
    subtotal = sum(i["unit_price"] * i["quantity"] for i in items)
    assert subtotal + o["shipping_fee"] - o.get("discount_amount", 0) == o["total_amount"], o
for p in products:
    assert (ASSETS / p["image"]).exists(), p["image"]
    for img in p["images"]:
        assert (ASSETS / img).exists(), img
    assert p["images"][0] == p["image"]
    assert any(c["id"] == p["category"] for c in categories), p["category"]
    th = p["free_shipping_threshold"]
    assert th is None or (isinstance(th, int) and th >= 0), (p["id"], th)
for pi in product_images:
    assert (ASSETS / pi["image"]).exists(), pi["image"]
    assert any(p["id"] == pi["product_id"] for p in products), pi
assert len({c["code"] for c in coupons}) == len(coupons)
assert {o["coupon_code"] for o in orders if o.get("coupon_code")} <= {c["code"] for c in coupons}
# 발급 대상(전용 쿠폰) — 빈 배열 = 전체 공용, 지정한 회원은 반드시 users 에 존재해야 한다
for c in coupons:
    assert isinstance(c.get("target_user_ids"), list), c["code"]
    for uid in c["target_user_ids"]:
        assert any(u["id"] == uid for u in users), (c["code"], uid)
    assert isinstance(c.get("target_grades"), list), c["code"]
    for g in c["target_grades"]:
        assert g in ("NORMAL", "SILVER", "GOLD", "VIP"), (c["code"], g)
# 회원 등급 — 시드 회원 모두 허용된 등급을 가진다
for u in users:
    assert u.get("grade") in ("NORMAL", "SILVER", "GOLD", "VIP"), (u["id"], u.get("grade"))
assert any(u.get("grade") in ("GOLD", "VIP") for u in users if u["role"] == "customer"), \
    "등급별 쿠폰을 확인할 수 있는 GOLD/VIP 시드 회원이 필요"
# 카테고리 — id 고유·순서 중복 없이, 모든 상품 카테고리가 존재
assert len({c["id"] for c in categories}) == len(categories)
assert len({c["sort_order"] for c in categories}) == len(categories)
# v1.9.1 — 카테고리별 사이즈 코드: 비어있지 않은 문자열, 중복 없음
for c in categories:
    assert isinstance(c.get("size_codes"), list) and len(c["size_codes"]) >= 1, c["id"]
    assert all(isinstance(s, str) and s.strip() and len(s) <= 8 for s in c["size_codes"]), c["id"]
    assert len(set(c["size_codes"])) == len(c["size_codes"]), c["id"]
for p in products:
    assert p["badge"] is None or (isinstance(p["badge"], str) and 1 <= len(p["badge"].strip()) <= 16), p
# 모델 정보: 선택 항목 — 있으면 짧은 문구(60자 이내), 없으면 None
def _model_info_ok(v):
    return v is None or (isinstance(v, str) and 1 <= len(v.strip()) <= 60)


assert all(_model_info_ok(p.get("model_info")) for p in products), \
    [p["id"] for p in products if not _model_info_ok(p.get("model_info"))]
assert sum(1 for p in products if p.get("model_info")) >= 10, "모델 정보가 있는 시드 상품이 너무 적음"

# 교환/반품 클레임 시드 무결성 — 주문·회원 FK, 한 주문당 클레임 1건, 배송비 정책(판매자 귀책 0원 / 왕복·편도)
REASON_SELLER = {"defect": True, "wrong_item": True, "change_of_mind": False, "size_color": False}
assert len({c["id"] for c in claims}) == len(claims)
assert len({c["order_id"] for c in claims}) == len(claims), "한 주문에 교환/반품은 1건만 접수"
for c in claims:
    assert any(o["id"] == c["order_id"] for o in orders), c
    assert any(u["id"] == c["user_id"] for u in users), c
    assert c["claim_type"] in ("return", "exchange"), c
    assert c["reason_category"] in REASON_SELLER, c
    assert c["payment_status"] in ("free", "paid", "pending"), c
    assert c["status"] in ("requested", "approved", "completed", "rejected"), c
    want = 0 if REASON_SELLER[c["reason_category"]] else (
        SHIPPING_FEE * 2 if c["claim_type"] == "exchange" else SHIPPING_FEE)
    assert c["shipping_fee"] == want, (c["id"], c["shipping_fee"], want)
    assert (c["payment_status"] == "free") == (want == 0), c["id"]
    assert (c["claim_type"] == "exchange") == bool(c.get("exchange_option")), c["id"]
    order = next(o for o in orders if o["id"] == c["order_id"])
    assert order["status"] in ("shipping", "delivered"), c["id"]
assert any(o["status"] == "delivered" and not any(c["order_id"] == o["id"] for c in claims)
           for o in orders), "데모에서 바로 신청해 볼 수 있는 배송완료 주문이 필요"

# ------------------------------------------------- v1.9 seed 무결성 (리뷰·포인트·FAQ)
GRADE_KEYS = ("NORMAL", "SILVER", "GOLD", "VIP")
assert [p["grade"] for p in point_policies] == list(GRADE_KEYS), [p["grade"] for p in point_policies]
for p in point_policies:
    assert 0 < p["confirm_rate"] <= 10 and 0 < p["photo_rate"] <= 10, p
    assert p["confirm_rate"] <= p["photo_rate"], p
assert len({r["id"] for r in product_reviews}) == len(product_reviews)
assert len({(r["order_item_id"], r.get("attempt", 1)) for r in product_reviews}) == len(product_reviews), \
    "주문항목당 리뷰 1건(재작성은 차수 2로 별도 행)"
for r in product_reviews:
    oi = next((x for x in order_items if x["id"] == r["order_item_id"]), None)
    assert oi, r
    v = next(v for v in variants if v["id"] == oi["variant_id"])
    assert v["product_id"] == r["product_id"], (r["id"], "상품 불일치")
    assert oi["order_id"] and next(o for o in orders if o["id"] == oi["order_id"])["user_id"] == r["user_id"]
    assert 1 <= r["rating"] <= 5, r
    assert len(r["content"].strip()) >= 5, r
    for m in r["media"]:
        assert m["type"] in ("image", "video"), m
        if m["type"] == "image" and not str(m["src"]).startswith("data:"):
            assert (ASSETS / m["src"]).exists(), m["src"]
assert sum(1 for r in product_reviews if r["media"]) >= 2, "사진 리뷰 시드 필요"
# v1.9.1 — 리뷰 검수 상태· 반려 필드 / 코트(p_001) 리뷰 6건 이상(5개씩 페이징 확인)
for r in product_reviews:
    assert r.get("status") in ("published", "rejected"), r["id"]
    assert isinstance(r.get("reclaimed_points"), int) and r["reclaimed_points"] >= 0, r["id"]
    if r["status"] == "published":
        assert not r.get("reclaimed_points"), r["id"]
assert sum(1 for r in product_reviews if r["product_id"] == "p_001" and r["status"] == "published") >= 11, \
    "v1.9.12 — 코트(p_001) 리뷰 11건 이상(5건씩 3페이지 확인)"
assert len(product_reviews) >= 10, "v1.9.12 — 상품 리뷰 전체 10건 이상"
assert any(h["title"] == "고객센터" for h in HELP_TOPICS), "HELP 고객센터 항목 제목"
assert not any("· FAQ" in h["title"] for h in HELP_TOPICS), "HELP 제목에 FAQ 중복 금지"
# v1.9.10 — 무료배송·당일출고 칸은 FAQ 게시판으로 대체(홈 4칸과 같은 3항목)
assert len(HELP_TOPICS) == 3 and not any("무료배송" in h["title"] or "당일출고" in h["title"] for h in HELP_TOPICS), \
    "HELP 항목 3개(무료배송·당일출고 제외)"
assert [h["sort_order"] for h in HELP_TOPICS] == [1, 2, 3]

# ------------------------------------------------- v1.9.2 리뷰 재작성·발송 로그
for _oi in order_items:
    assert isinstance(_oi.get("review_attempts"), int) and _oi["review_attempts"] >= 0, _oi["id"]
    assert _oi.get("rewrite_used") in (0, 1), _oi["id"]
    _cnt = sum(1 for r in product_reviews if r["order_item_id"] == _oi["id"])
    assert _oi["review_attempts"] == _cnt, ("review_attempts", _oi["id"], _oi["review_attempts"], _cnt)
    assert _oi["review_attempts"] <= 2, _oi["id"]
for _r in product_reviews:
    assert _r.get("attempt") in (1, 2), (_r["id"], _r.get("attempt"))
assert not any(r.get("attempt", 1) == 2 for r in product_reviews), \
    "시드는 1차 리뷰만 — 재작성(2차)은 E2E 에서 생성해 검증"
assert len({d["id"] for d in dispatch_logs}) == len(dispatch_logs)
for _d in dispatch_logs:
    assert _d["channel"] in ("sms", "email"), _d["id"]
    assert _d["status"] in ("test", "sent", "blocked", "failed"), _d["id"]
    assert _d["mode"] in ("test", "api"), _d["id"]
    assert _d["to"].strip() and _d["summary"].strip(), _d["id"]
    if _d["channel"] == "sms":
        assert any(o["id"] == _d["order_id"] for o in orders), _d["id"]
assert any(d["channel"] == "sms" for d in dispatch_logs), "SMS 발송 로그 시드 필요"
assert any(d["channel"] == "email" for d in dispatch_logs), "이메일 발송 로그 시드 필요"
assert any(d["status"] == "blocked" for d in dispatch_logs), "차단(blocked) 사례 시드 필요"
# v1.9.1 — 알림 설정·SMS 로그 시드
assert SITE_SETTINGS["email_auth_mode"] in ("test", "api"), SITE_SETTINGS["email_auth_mode"]
assert SITE_SETTINGS["sms_mode"] in ("test", "api"), SITE_SETTINGS["sms_mode"]
assert isinstance(SITE_SETTINGS["sms_enabled"], bool)
assert len({s["id"] for s in sms_logs}) == len(sms_logs)
for _s in sms_logs:
    assert _s["status"] in ("test", "sent", "failed", "skipped"), _s["id"]
    assert _s["mode"] in ("test", "api"), _s["id"]
    assert any(o["id"] == _s["order_id"] for o in orders), _s["id"]
    assert _s["phone"] and _s["message"].startswith("[MONO ATELIER]"), _s["id"]
# 포인트: 등급별 적립률로 계산한 값과 일치 + 로그 합계 = 회원 보유 포인트
_pol = {p["grade"]: p for p in point_policies}
for _r in product_reviews:
    _oi = next(x for x in order_items if x["id"] == _r["order_item_id"])
    _user = next(u for u in users if u["id"] == _r["user_id"])
    if _oi.get("photo_bonus"):
        _want = int(_oi["unit_price"] * _oi["quantity"] * _pol[_user["grade"]]["photo_rate"] / 100)
        assert _oi["photo_bonus"] == _want, (_r["id"], _oi["photo_bonus"], _want)
for _oi in order_items:
    if _oi.get("confirm_points"):
        _user = next(u for u in users if u["id"] == next(o for o in orders if o["id"] == _oi["order_id"])["user_id"])
        _want = int(_oi["unit_price"] * _oi["quantity"] * _pol[_user["grade"]]["confirm_rate"] / 100)
        assert _oi["confirm_points"] == _want, (_oi["id"], _oi["confirm_points"], _want)
        assert _oi.get("confirmed_at"), _oi["id"]
for _u in users:
    _sum = sum(l["amount"] for l in point_logs if l["user_id"] == _u["id"])
    assert (_u.get("points") or 0) == _sum, (_u["id"], _u.get("points"), _sum)
assert point_logs and all(l["amount"] != 0 for l in point_logs)
assert len({f["id"] for f in faqs}) == len(faqs)
assert len({f["category"] for f in faqs}) >= 3, "FAQ 카테고리 최소 3종"
for f in faqs:
    assert f["question"].strip() and f["answer"].strip(), f
    assert 1 <= len(f["question"]) <= 120 and len(f["answer"]) <= 800, f
assert [f["sort_order"] for f in faqs] == list(range(1, len(faqs) + 1)), "FAQ 노출순서 중복 없음"
# v1.9.5 — 관리 목록(SITE_SETTINGS['faq_categories'])이 모든 FAQ 카테고리를 포함해야 한다
assert len({f["category"] for f in faqs} - set(SITE_SETTINGS["faq_categories"])) == 0, "FAQ 카테고리 관리 목록 누락"
assert len(set(SITE_SETTINGS["faq_categories"])) == len(SITE_SETTINGS["faq_categories"]), "FAQ 카테고리 중복"
assert SITE_SETTINGS["shop_title"] and SITE_SETTINGS["shop_eyebrow"], "상품 섹션 헤더 문구"
assert SITE_SETTINGS["top_banner_enabled"] is True, "상단 안내 띠 기본 노출"
assert SITE_SETTINGS["story_image"] and (ASSETS / SITE_SETTINGS["story_image"]).exists()
assert isinstance(SITE_SETTINGS["story_tags"], list) and len(SITE_SETTINGS["story_tags"]) >= 2
# v1.9.13 — 사이트 전용 미디어·뱃지 코드·멤버십 기준
for _kind in ("hero_images", "story_images"):
    _list = SITE_SETTINGS[_kind]
    assert isinstance(_list, list) and len(_list) >= 2, _kind
    assert len(set(_list)) == len(_list), _kind
    for _img in _list:
        assert (ASSETS / _img).exists(), (_kind, _img)
assert SITE_SETTINGS["hero_image"] in SITE_SETTINGS["hero_images"]
assert SITE_SETTINGS["story_image"] in SITE_SETTINGS["story_images"]
assert SITE_SETTINGS["product_badges"] == ["BEST", "NEW", "SALE", "LIMITED"]
for _c in coupons:
    assert isinstance(_c.get("target_categories"), list), _c["code"]
    for _cid in _c["target_categories"]:
        assert any(x["id"] == _cid for x in categories), (_c["code"], _cid)
    assert isinstance(_c.get("target_badges"), list), _c["code"]
    for _b in _c["target_badges"]:
        assert _b in SITE_SETTINGS["product_badges"], (_c["code"], _b)
# v1.9.13 — 복합 조건 쿠폰(GOLD20)은 실제 판매 상품(잡의·야우터 + BEST)과 매칭되어야 한다
_gold = next(c for c in coupons if c["code"] == "GOLD20")
assert _gold["target_grades"] == ["GOLD"]
assert _gold["target_categories"] and _gold["target_badges"]
assert any(p["category"] in _gold["target_categories"] and p.get("badge") in _gold["target_badges"]
           and p["is_active"] for p in products), "GOLD20 조건과 매칭되는 판매 상품이 필요"
_rules = SITE_SETTINGS["member_grade_rules"]
assert _rules["months"] == 6 and set(_rules["thresholds"]) == {"NORMAL", "SILVER", "GOLD", "VIP"}
assert _rules["thresholds"]["NORMAL"] == 0
assert (_rules["thresholds"]["SILVER"] < _rules["thresholds"]["GOLD"] < _rules["thresholds"]["VIP"])
assert all(len(p.get("postcode", "")) <= 10 for p in users)
assert any(o.get("postcode") for o in orders)

# v1.9.11 — 상품 Q&A · 리뷰 추천/비추천 시드 무결성
QNA_TYPES = ("product", "delivery", "claim", "etc")
assert len(product_qnas) >= 10, len(product_qnas)
assert len({q["id"] for q in product_qnas}) == len(product_qnas)
for q in product_qnas:
    assert any(p["id"] == q["product_id"] for p in products), q["id"]
    assert any(u["id"] == q["user_id"] for u in users), q["id"]
    assert q["qna_type"] in QNA_TYPES, q["id"]
    assert q["title"].strip() and 2 <= len(q["title"]) <= 80, q["id"]
    assert q["content"].strip(), q["id"]
    assert q["is_secret"] in (0, 1), q["id"]
    assert q["status"] in ("pending", "answered"), q["id"]
    # 답변 유무와 상태·답변일시는 항상 같이 움직인다
    assert (q["status"] == "answered") == bool(str(q["answer"]).strip()), q["id"]
    if q["status"] == "answered":
        assert q["answered_by"] and q["answered_at"], q["id"]
        assert any(u["id"] == q["answered_by"] and u["role"] == "admin" for u in users), q["id"]
    else:
        assert not q["answered_by"] and not q["answered_at"], q["id"]
assert any(q["status"] == "answered" for q in product_qnas), "답변완료 예시 필요"
assert any(q["status"] == "pending" for q in product_qnas), "미답변 예시 필요"
assert any(q["is_secret"] == 1 for q in product_qnas), "비밀글 예시 필요"
assert any(q["is_secret"] == 0 for q in product_qnas), "공개글 예시 필요"
# v1.9.12 — 대표 상품 코트(p_001) Q&A 11건 이상(5건씩 3페이지) · 전체 10건 이상
assert len(product_qnas) >= 10, "v1.9.12 — 상품 Q&A 전체 10건 이상"
assert sum(1 for q in product_qnas if q["product_id"] == "p_001") >= 11, \
    "v1.9.12 — 코트(p_001) Q&A 11건 이상(5건씩 3페이지 확인)"
assert len({q["product_id"] for q in product_qnas}) >= 2, "Q&A 가 여러 상품에 있어야 한다"
assert len({(v["review_id"], v["user_id"]) for v in review_votes}) == len(review_votes), \
    "리뷰 1건에 회원 1명은 한 표만"
assert len({v["id"] for v in review_votes}) == len(review_votes)
for v in review_votes:
    _rev = next((r for r in product_reviews if r["id"] == v["review_id"]), None)
    assert _rev is not None, v["id"]
    assert v["user_id"] != _rev["user_id"], (v["id"], "본인 리뷰 추천 금지")
    assert v["vote"] in ("up", "down"), v["id"]
assert any(v["vote"] == "down" for v in review_votes), "비추천 예시 필요"
assert len({r["review_id"] for r in review_votes}) >= 5, "추천순 정렬을 확인할 투표가 여러 리뷰에 필요"

# ---------------------------------------------------------------- schema DDL
SCHEMA_SQL = """-- MONO ATELIER — SQLite schema
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
                -- 회원 등급 — 쿠폰 발급 대상(등급별)·포인트 적립률에 사용
  points        INTEGER NOT NULL DEFAULT 0 CHECK (points >= 0),   -- 보유 포인트(원 단위 1P = 1원)
  postcode      TEXT NOT NULL DEFAULT '',                          -- 우편번호(카카오 우편번호 서비스)
  created_at    TEXT NOT NULL
);

-- 카테고리 — 관리자 콘솔에서 추가·이름 수정·삭제·순서 변경 (products.category 가 참조)
CREATE TABLE categories (
  id         TEXT PRIMARY KEY,
  label      TEXT NOT NULL,
  en         TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  size_codes TEXT NOT NULL DEFAULT '[]',      -- JSON 배열: 카테고리별 사이즈 코드 (예: ["95","100","105","S","M","L","XL"])
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
                 -- v1.9.8: 사용 여부(0 = 숨김 — 스토어 카테고리 필터에서 빠지고 상품 등록 목록에는 남는다)
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
  points_used      INTEGER NOT NULL DEFAULT 0 CHECK (points_used >= 0),   -- 결제에 사용한 포인트
  postcode         TEXT NOT NULL DEFAULT '',                              -- 배송지 우편번호
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
  quantity     INTEGER NOT NULL CHECK (quantity > 0),
  confirmed_at TEXT,                              -- 구매확정 시각 (NULL = 미확정, 중복 확정 차단)
  confirm_points INTEGER NOT NULL DEFAULT 0 CHECK (confirm_points >= 0),  -- 구매확정 적립 포인트
  photo_bonus    INTEGER NOT NULL DEFAULT 0 CHECK (photo_bonus >= 0),     -- 포토·영상 리뷰 추가 적립 포인트
  photo_bonus_at TEXT,                                                      -- 추가 적립 시각 (주문항목당 1회)
  review_attempts INTEGER NOT NULL DEFAULT 0 CHECK (review_attempts BETWEEN 0 AND 2),
                  -- v1.9.2 리뷰 작성 횟수 (1 = 최초, 2 = 반려 후 재작성)
  rewrite_used   INTEGER NOT NULL DEFAULT 0 CHECK (rewrite_used IN (0,1))
                  -- v1.9.2 리뷰가 반려·포인트 회수된 뒤 1회 재작성 기회를 이미 썼는지
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
  admin_memo      TEXT NOT NULL DEFAULT '',                 -- v1.9.8: 관리자 처리 메모(고객 화면 미노출)
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
  target_categories TEXT NOT NULL DEFAULT '[]',             -- v1.9.13 JSON 배열: 사용 가능 상품 카테고리 id ([] = 조건 없음)
  target_badges    TEXT NOT NULL DEFAULT '[]',              -- v1.9.13 JSON 배열: 사용 가능 상품 뱃지 코드 ([] = 조건 없음)
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
  top_banner_text      TEXT NOT NULL DEFAULT '',                -- v1.9.3 상단 안내 띠 문구(비우면 띠 숨김)
  top_banner_sub       TEXT NOT NULL DEFAULT '',                -- v1.9.3 상단 띠 보조 문구(비우면 숨김)
  top_banner_enabled   INTEGER NOT NULL DEFAULT 1 CHECK (top_banner_enabled IN (0,1)),
                                                               -- v1.9.10 상단 안내 띠 노출(0 = 숨김)
  hero_image           TEXT NOT NULL,                           -- 대표 배너 이미지(asset 파일명 또는 업로드 Data URL)
  hero_eyebrow         TEXT NOT NULL DEFAULT '',                -- 상단 뱃지 문구
  hero_title           TEXT NOT NULL,                           -- 메인 타이틀
  hero_subtitle        TEXT NOT NULL DEFAULT '',                -- 서브 문구
  hero_cta_label       TEXT NOT NULL DEFAULT '컬렉션 보기',
  hero_cta2_label      TEXT NOT NULL DEFAULT '브랜드 스토리',
  hero_effect          TEXT NOT NULL DEFAULT 'none'
                       CHECK (hero_effect IN ('none','zoom','fade','slide')),
  hero_overlay         INTEGER NOT NULL DEFAULT 42 CHECK (hero_overlay BETWEEN 0 AND 90),
  story_image          TEXT NOT NULL DEFAULT '',                -- 브랜드 스토리 대표 이미지
  story_eyebrow        TEXT NOT NULL DEFAULT '',                -- 스토리 상단 뱃지
  story_title          TEXT NOT NULL DEFAULT '',                -- 스토리 제목(줄바꿈 허용)
  story_subtitle       TEXT NOT NULL DEFAULT '',                -- 스토리 부제
  story_body           TEXT NOT NULL DEFAULT '',                -- 스토리 본문(줄바꿈 허용)
  story_tags           TEXT NOT NULL DEFAULT '[]',              -- JSON 배열: 핵심 가치/태그
  brand_story_enabled  INTEGER NOT NULL DEFAULT 1 CHECK (brand_story_enabled IN (0,1)),
                                                               -- v1.9.9 메인페이지 브랜드 스토리 노출(0 = 홈에서 숨김)
  shop_eyebrow         TEXT NOT NULL DEFAULT 'SHOP — NEW ARRIVALS',   -- v1.9.10 상품 섹션 뱃지·영문 문구
  shop_title           TEXT NOT NULL DEFAULT '이번 시즌, 새로 도착한 옷',  -- v1.9.10 상품 섹션 제목
  shop_desc            TEXT NOT NULL DEFAULT '',                -- v1.9.10 상품 섹션 설명(비우면 기본 문구)
  site_title           TEXT NOT NULL DEFAULT 'MONO ATELIER',    -- v1.9.14 상단 로고 텍스트(헤더·푸터 브랜드명)
  page_title           TEXT NOT NULL DEFAULT 'MONO ATELIER — 모노 아틀리에',  -- v1.9.14 브라우저 탭 제목(<title>)
  footer_copyright     TEXT NOT NULL DEFAULT '© 2026 MONO ATELIER. ALL RIGHTS RESERVED.',  -- v1.9.14 푸터 카피라이트
  brand_blurb          TEXT NOT NULL DEFAULT '',                -- 푸터 브랜드 소개
  company_name         TEXT NOT NULL DEFAULT '',                -- 상호
  company_ceo          TEXT NOT NULL DEFAULT '',                -- 대표자
  company_reg_no       TEXT NOT NULL DEFAULT '',                -- 사업자등록번호
  company_mail_order_no TEXT NOT NULL DEFAULT '',               -- 통신판매업 신고번호
  company_address      TEXT NOT NULL DEFAULT '',                -- 주소
  company_phone        TEXT NOT NULL DEFAULT '',                -- 고객센터 전화
  company_email        TEXT NOT NULL DEFAULT '',                -- 고객센터 이메일
  email_auth_mode      TEXT NOT NULL DEFAULT 'test'
                       CHECK (email_auth_mode IN ('test','api')),
                                                               -- 회원가입 이메일 인증 모드
  email_api_url        TEXT NOT NULL DEFAULT '',                -- 이메일 발송 API URL (Resend·Brevo·SMTP 프록시)
  sms_enabled          INTEGER NOT NULL DEFAULT 1 CHECK (sms_enabled IN (0,1)),   -- 주문 완료 SMS 발송
  sms_mode             TEXT NOT NULL DEFAULT 'test' CHECK (sms_mode IN ('test','api')),
                                                               -- 테스트(로그만) / 실서버 API
  sms_api_url          TEXT NOT NULL DEFAULT '',                -- SMS Webhook/API URL
  sms_sender           TEXT NOT NULL DEFAULT '',                -- 발신번호
  faq_categories       TEXT NOT NULL DEFAULT '[]',              -- v1.9.5 JSON 배열: FAQ 카테고리 목록(관리자에서 추가·삭제·순서)
  product_badges       TEXT NOT NULL DEFAULT '["BEST","NEW","SALE","LIMITED"]',
                                                               -- v1.9.13 JSON 배열: 상품 뱃지 코드(관리자 「코드 관리 > 뱃지 관리」)
  hero_images          TEXT NOT NULL DEFAULT '[]',              -- v1.9.13 JSON 배열: 히어로 배너 전용 사진 목록(상품 사진과 분리)
  story_images         TEXT NOT NULL DEFAULT '[]',              -- v1.9.13 JSON 배열: 브랜드 스토리 전용 사진 목록
  member_grade_rules   TEXT NOT NULL DEFAULT '{}',              -- v1.9.13 JSON 객체: {months, thresholds{NORMAL,SILVER,GOLD,VIP}}
  updated_at           TEXT NOT NULL
);

-- ===================================================== 주문 SMS 발송 로그 (v1.9.1)
CREATE TABLE sms_logs (
  id         TEXT PRIMARY KEY,
  order_id   TEXT REFERENCES orders(id) ON DELETE SET NULL,
  user_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
  phone      TEXT NOT NULL,
  message    TEXT NOT NULL,
  kind       TEXT NOT NULL DEFAULT 'order_created',   -- 주문 완료 알림
  status     TEXT NOT NULL DEFAULT 'test' CHECK (status IN ('test','sent','failed','skipped')),
  mode       TEXT NOT NULL DEFAULT 'test' CHECK (mode IN ('test','api')),
  sender     TEXT NOT NULL DEFAULT '',
  api_url    TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX idx_sms_logs_order ON sms_logs(order_id, created_at DESC);

-- 푸터 HELP 메뉴 — 클릭하면 안내 모달로 열리는 항목(관리자가 제목·본문 편집)
CREATE TABLE help_topics (
  id         TEXT PRIMARY KEY,
  title      TEXT NOT NULL,
  body       TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_help_topics_sort ON help_topics(sort_order);

-- ===================================================== 상품 리뷰 (v1.9)
-- 구매한 주문항목(order_item_id) 하나당 리뷰 1건 — 별점·내용·사진/동영상(JSON 배열)
--   media = [{"type":"image"|"video","src":"asset 파일명 또는 data: URL","name":"파일명"}]
CREATE TABLE product_reviews (
  id            TEXT PRIMARY KEY,
  product_id    TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user_name     TEXT NOT NULL DEFAULT '',            -- 표시용 마스킹 이름 (예: 홍길*)
  order_item_id TEXT NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
  attempt       INTEGER NOT NULL DEFAULT 1 CHECK (attempt BETWEEN 1 AND 2),
                                                     -- v1.9.2 리뷰 차수(1 = 최초, 2 = 반려 후 재작성)
  rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  content       TEXT NOT NULL DEFAULT '',
  media         TEXT NOT NULL DEFAULT '[]',          -- JSON 배열 (사진 다중·동영상)
  status        TEXT NOT NULL DEFAULT 'published'
                CHECK (status IN ('published','rejected')),
                -- 관리자 리뷰 검수: rejected = 스토어 비노출
  rejected_reason TEXT,                              -- 반려 사유 (관리자 입력)
  reclaimed_points INTEGER NOT NULL DEFAULT 0 CHECK (reclaimed_points >= 0),
                                                     -- 반려 시 회수한 포토·영상 리뷰 포인트 (중복 회수 방지)
  rejected_at   TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT,
  UNIQUE (order_item_id, attempt)                    -- 주문항목당 차수별 1건(재작성은 attempt 2)
);

-- ===================================================== 상품 Q&A (v1.9.11)
-- 상품 상세의 「상품 Q&A」 — 로그인한 회원이 상품별로 문의하고 관리자가 답변한다.
--   qna_type: product(상품 문의) / delivery(배송 문의) / claim(교환·반품) / etc(기타)
--   is_secret = 1 이면 작성자 본인과 관리자만 본문을 볼 수 있고, 다른 회원에게는 「비밀글입니다」로 보인다.
--   status = answer 가 비어 있으면 pending(미답변), 채워지면 answered(답변완료)
CREATE TABLE product_qnas (
  id          TEXT PRIMARY KEY,
  product_id  TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user_name   TEXT NOT NULL DEFAULT '',              -- 표시용 마스킹 이름 (예: 홍길*)
  qna_type    TEXT NOT NULL DEFAULT 'product'
              CHECK (qna_type IN ('product','delivery','claim','etc')),
  title       TEXT NOT NULL,
  content     TEXT NOT NULL DEFAULT '',
  is_secret   INTEGER NOT NULL DEFAULT 0 CHECK (is_secret IN (0,1)),
  answer      TEXT NOT NULL DEFAULT '',
  answered_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  answered_at TEXT,
  status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','answered')),
  created_at  TEXT NOT NULL,
  updated_at  TEXT
);
CREATE INDEX idx_qnas_product ON product_qnas(product_id, created_at DESC);
CREATE INDEX idx_qnas_status ON product_qnas(status, created_at DESC);

-- ===================================================== 리뷰 추천/비추천 (v1.9.11)
-- 리뷰 1건에 회원 1명이 추천(up) 또는 비추천(down) 하나만 남길 수 있다(UNIQUE).
--   본인이 쓴 리뷰에는 투표할 수 없다(앱에서 차단). 추천 수 = COUNT(vote='up').
CREATE TABLE review_votes (
  id         TEXT PRIMARY KEY,
  review_id  TEXT NOT NULL REFERENCES product_reviews(id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  vote       TEXT NOT NULL CHECK (vote IN ('up','down')),
  created_at TEXT NOT NULL,
  UNIQUE (review_id, user_id)
);
CREATE INDEX idx_review_votes_review ON review_votes(review_id, vote);
CREATE INDEX idx_review_votes_user ON review_votes(user_id);

-- ===================================================== 포인트 정책 (v1.9)
-- 관리자 「포인트/회원」에서 등급별 적립률(%)을 수정한다.
CREATE TABLE point_policies (
  grade        TEXT PRIMARY KEY CHECK (grade IN ('NORMAL','SILVER','GOLD','VIP')),
  confirm_rate REAL NOT NULL DEFAULT 0.5 CHECK (confirm_rate >= 0 AND confirm_rate <= 10),
  photo_rate   REAL NOT NULL DEFAULT 1.0 CHECK (photo_rate >= 0 AND photo_rate <= 10),
  updated_at   TEXT NOT NULL
);

-- ===================================================== 포인트 내역 (v1.9)
-- amount 양수 = 적립, 음수 = 사용. users.points 는 이 표의 합계와 일치해야 한다.
CREATE TABLE point_logs (
  id            TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type          TEXT NOT NULL CHECK (type IN ('signup','confirm','photo_review','use','refund','adjust','review','review_reclaim')),
  amount        INTEGER NOT NULL CHECK (amount <> 0),
  base_amount   INTEGER NOT NULL DEFAULT 0,          -- 적립 기준 금액(상품 실결제 금액)
  rate          REAL NOT NULL DEFAULT 0,             -- 적용 적립률(%)
  order_id      TEXT,
  order_item_id TEXT,
  review_id     TEXT,
  description   TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL
);

-- ===================================================== FAQ 게시판 (v1.9)
CREATE TABLE faqs (
  id         TEXT PRIMARY KEY,
  category   TEXT NOT NULL DEFAULT '기타',
  question   TEXT NOT NULL,
  answer     TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  created_at TEXT NOT NULL
);

CREATE INDEX idx_reviews_product ON product_reviews(product_id, created_at DESC);
CREATE INDEX idx_reviews_user ON product_reviews(user_id);
CREATE INDEX idx_reviews_item ON product_reviews(order_item_id, attempt);
-- ===================================================== 발송 로그 (v1.9.2)
-- SMS(주문 완료 안내) + 이메일 인증번호 발송 기록을 한 표에 남긴다.
--   status: test(테스트) / sent(발송) / blocked(쿨다운·과다 발송 차단) / failed(실패)
CREATE TABLE dispatch_logs (
  id         TEXT PRIMARY KEY,
  channel    TEXT NOT NULL CHECK (channel IN ('sms','email')),
  to_addr    TEXT NOT NULL,                              -- 수신번호 또는 이메일 주소
  kind       TEXT NOT NULL DEFAULT 'order_created',      -- order_created | email_otp | email_resend
  summary    TEXT NOT NULL DEFAULT '',                   -- 본문 요약(인증번호 자체는 저장하지 않음)
  status     TEXT NOT NULL DEFAULT 'test' CHECK (status IN ('test','sent','blocked','failed')),
  mode       TEXT NOT NULL DEFAULT 'test' CHECK (mode IN ('test','api')),
  order_id   TEXT REFERENCES orders(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_dispatch_recipient ON dispatch_logs(channel, to_addr, created_at DESC);
CREATE INDEX idx_dispatch_created ON dispatch_logs(created_at DESC);
CREATE INDEX idx_point_logs_user ON point_logs(user_id, created_at DESC);
CREATE INDEX idx_point_logs_order ON point_logs(order_id);
CREATE INDEX idx_faqs_sort ON faqs(sort_order);

-- 회원별 포인트 요약 (보유 포인트 = 적립 − 사용)
CREATE VIEW v_member_points AS
SELECT u.id AS user_id, u.name, u.email, u.grade, u.points,
       COALESCE(SUM(CASE WHEN l.amount > 0 THEN l.amount ELSE 0 END), 0) AS earned_total,
       COALESCE(SUM(CASE WHEN l.amount < 0 THEN -l.amount ELSE 0 END), 0) AS used_total
FROM users u
LEFT JOIN point_logs l ON l.user_id = u.id
GROUP BY u.id;

-- 상품별 리뷰 요약 (평균 별점·리뷰 수·포토리뷰 수)
CREATE VIEW v_product_reviews AS
SELECT p.id AS product_id, p.product_code, p.name,
       COUNT(r.id) AS review_count,
       ROUND(COALESCE(AVG(r.rating), 0), 2) AS avg_rating,
       SUM(CASE WHEN r.media <> '[]' THEN 1 ELSE 0 END) AS photo_review_count
FROM products p
LEFT JOIN product_reviews r ON r.product_id = p.id AND r.status = 'published'
GROUP BY p.id;
"""

# ------------------------------------------------------------------- outputs
DATA.mkdir(parents=True, exist_ok=True)
(ROOT / "data").mkdir(exist_ok=True)
seed_text = json.dumps(seed, ensure_ascii=False, indent=2)
(DATA / "schema-seed.json").write_text(seed_text + "\n", encoding="utf-8")
(DATA / "schema.sql").write_text(SCHEMA_SQL, encoding="utf-8")

styles = (SRC / "styles.css").read_text(encoding="utf-8")
app_js = (SRC / "app.js").read_text(encoding="utf-8")
template = (SRC / "index.template.html").read_text(encoding="utf-8")

asset_files = sorted(p.name for p in ASSETS.glob("*.webp"))
missing = [p["image"] for p in products if p["image"] not in asset_files]
assert not missing, missing

seed_js = json.dumps(seed, ensure_ascii=False, separators=(",", ":"))
js_index = (app_js
            .replace("__SEED__", seed_js)
            .replace("__EMBEDDED_IMAGES__", "{}")
            .replace("__APP_VERSION__", APP_VERSION))
html_index = (template
              .replace("/*__STYLES__*/", styles)
              .replace("/*__APP_JS__*/", js_index))

(ROOT / "index.html").write_text(html_index, encoding="utf-8")

# single-file preview with embedded images
embedded = {}
for name in asset_files:
    raw = (ASSETS / name).read_bytes()
    embedded[name] = "data:image/webp;base64," + base64.b64encode(raw).decode("ascii")
js_preview = (app_js
              .replace("__SEED__", seed_js)
              .replace("__EMBEDDED_IMAGES__", json.dumps(embedded))
              .replace("__APP_VERSION__", APP_VERSION))
html_preview = (template
                .replace("/*__STYLES__*/", styles)
                .replace("/*__APP_JS__*/", js_preview))

DOWNLOADS.mkdir(parents=True, exist_ok=True)
(DOWNLOADS / "fashion-shop-preview.html").write_text(html_preview, encoding="utf-8")

# 개인정보 보호: 공개 저장소에 실명·연락처·실주소가 올라가지 않도록 산출물을 검사한다.
for label, text in (("schema-seed.json", seed_text), ("index.html", html_index),
                    ("fashion-shop-preview.html", html_preview)):
    leaked = [pat for pat in PRIVATE_PATTERNS if pat in text]
    phones = sorted(set(MOBILE_RE.findall(text)) - ALLOWED_PHONES)
    rrn = RRN_RE.findall(text)
    if leaked or phones or rrn:
        raise SystemExit(
            f"개인정보 보호 검사 실패 — {label}: 패턴 {leaked} · 휴대전화 {phones} · 주민번호 {len(rrn)}건")

print("privacy check      ok (실명·연락처·실주소 0건)")
print("seed rows:", {k: len(v) for k, v in seed.items() if isinstance(v, list)})
print("index.html          %8.1f KB" % (len(html_index.encode()) / 1024))
print("fashion-shop-preview %7.1f KB" % (len(html_preview.encode()) / 1024))
print("assets embedded:", len(embedded))
