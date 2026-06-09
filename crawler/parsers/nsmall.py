"""NS몰(NS홈쇼핑) 모바일 카테고리 파서. sales_qty = 구매수(purchase_count)."""

from __future__ import annotations

from playwright.sync_api import Page

from ..models import ProductRank
from ..utils import clean, compute_discount, to_count, to_float, to_int, to_percent
from .base import BaseParser
from .extract_js import evaluate_cards

CONFIG = {
    "cardSelectors": [
        "ul.goods-list > li",
        "[class*='goods'] li",
        "ul li[class*='item']",
        "[class*='product-item']",
    ],
    "fields": {
        "name": [".goods-name", "[class*='name']", "[class*='title']", "a[title]"],
        "listPrice": [".price-origin", "del", "s", "[class*='origin']"],
        "salePrice": [".price-sale .num", "[class*='salePrice']", "[class*='price'] strong", "em[class*='price']"],
        "discount": [".dc-rate", "[class*='discount']", "[class*='rate']"],
        # 구매수: '구매 1,234' / '1.2만' 등
        "salesQty": ["[class*='purchase']", "[class*='buy']", "[class*='sale-cnt']", "[class*='count']"],
        "reviewCount": ["[class*='review']"],
        "rating": ["[class*='rating']", "[class*='star']", "[class*='score']"],
    },
    "linkSelectors": ["a[href*='/product']", "a[href*='goods']", "a"],
    "soldOut": {"selectors": ["[class*='soldout']", "[class*='soldOut']"], "keywords": ["품절", "일시품절"]},
    "ad": {"selectors": ["[class*='ad']"], "keywords": ["광고"]},
    "limit": 40,
}


class NsmallParser(BaseParser):
    name = "nsmall"

    def extract(self, page: Page, top_n: int) -> list[ProductRank]:
        cfg = {**CONFIG, "limit": max(top_n * 2, 40)}
        cards = evaluate_cards(page, cfg)
        rows: list[ProductRank] = []
        for i, c in enumerate(cards, start=1):
            list_price = to_int(c.get("listPrice"))
            sale_price = to_int(c.get("salePrice"))
            discount = to_percent(c.get("discount")) or compute_discount(list_price, sale_price)
            purchase = to_count(c.get("salesQty"))
            rows.append(
                ProductRank(
                    rank=i,
                    product_name=clean(c.get("name")),
                    list_price=list_price,
                    sale_price=sale_price,
                    discount_rate=discount,
                    sales_qty=purchase,              # NS: 구매수
                    review_count=to_int(c.get("reviewCount")),
                    rating=to_float(c.get("rating")),
                    is_sold_out=bool(c.get("isSoldOut")),
                    is_ad=bool(c.get("isAd")),
                    product_url=self.absolutize(c.get("href")),
                    image_url=self.absolutize(c.get("img")),
                )
            )
        return rows
