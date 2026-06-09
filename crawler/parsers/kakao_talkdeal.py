"""카카오 톡딜(식품) 파서. sales_qty = 주문수(order_count)."""

from __future__ import annotations

from playwright.sync_api import Page

from ..models import ProductRank
from ..utils import clean, compute_discount, to_count, to_float, to_int, to_percent
from .base import BaseParser
from .extract_js import evaluate_cards

CONFIG = {
    "cardSelectors": [
        "a[href*='/product/']",
        "ul li[class*='item']",
        "[class*='productCard']",
        "[class*='ProductItem']",
    ],
    "fields": {
        "name": ["[class*='name']", "[class*='title']", "strong"],
        "listPrice": ["del", "s", "[class*='origin']", "[class*='regular']"],
        "salePrice": ["[class*='salePrice']", "[class*='price'] strong", "[class*='discountedPrice']", "em[class*='price']"],
        "discount": ["[class*='discountRate']", "[class*='rate']", "[class*='percent']"],
        # 주문수: '주문 1,234' / '1.2만 주문' 등
        "orderCount": ["[class*='order']", "[class*='purchase']", "[class*='count']", "[class*='qty']"],
        "salesQty": ["[class*='order']", "[class*='purchase']"],
        "reviewCount": ["[class*='review']"],
        "rating": ["[class*='rating']", "[class*='star']", "[class*='score']"],
    },
    "linkSelectors": ["a[href*='/product/']", "a"],
    "soldOut": {"selectors": ["[class*='soldout']", "[class*='soldOut']"], "keywords": ["품절", "마감"]},
    "ad": {"selectors": ["[class*='ad']"], "keywords": ["광고", "AD"]},
    "limit": 60,
}


class KakaoTalkdealParser(BaseParser):
    name = "kakao_talkdeal"

    def extract(self, page: Page, top_n: int) -> list[ProductRank]:
        cfg = {**CONFIG, "limit": max(top_n * 2, 60)}
        cards = evaluate_cards(page, cfg)
        rows: list[ProductRank] = []
        for i, c in enumerate(cards, start=1):
            list_price = to_int(c.get("listPrice"))
            sale_price = to_int(c.get("salePrice"))
            discount = to_percent(c.get("discount")) or compute_discount(list_price, sale_price)
            order_count = to_count(c.get("orderCount"))
            rows.append(
                ProductRank(
                    rank=i,
                    product_name=clean(c.get("name")),
                    list_price=list_price,
                    sale_price=sale_price,
                    discount_rate=discount,
                    sales_qty=order_count,           # 톡딜: 주문수
                    order_count=order_count,
                    review_count=to_int(c.get("reviewCount")),
                    rating=to_float(c.get("rating")),
                    is_sold_out=bool(c.get("isSoldOut")),
                    is_ad=bool(c.get("isAd")),
                    product_url=self.absolutize(c.get("href")),
                )
            )
        return rows
