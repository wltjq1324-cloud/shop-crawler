"""G마켓 베스트 파서. sales_qty 는 수집하지 않음(NULL)."""

from __future__ import annotations

from playwright.sync_api import Page

from ..models import ProductRank
from ..utils import clean, compute_discount, to_float, to_int, to_percent
from .base import BaseParser
from .extract_js import evaluate_cards

CONFIG = {
    "cardSelectors": [
        "div.best-list ul li",
        "ul.best-list li",
        ".section__inner .box__item",
        "[class*='best'] li",
    ],
    "fields": {
        "name": ["a.itemname", ".text__item", ".box__item-title", "a[title]"],
        "listPrice": [".box__price-original", ".text__price-original", "del", "s"],
        "salePrice": [".box__price-seller .text__value", ".text__price", "strong.price", ".box__price-seller"],
        "discount": [".box__discount", ".text__discount", "[class*='discount']"],
        "reviewCount": [".text__review", "[class*='review']"],
        "rating": [".text__score", "[class*='rating']", "[class*='star']"],
    },
    "linkSelectors": ["a.itemname", "a.link__item", "a"],
    "soldOut": {"selectors": [".box__soldout", ".ico-soldout"], "keywords": ["품절", "SOLD OUT"]},
    "ad": {"selectors": [".box__ad", ".ico-ad"], "keywords": ["광고"]},
    "limit": 60,
}


class GmarketParser(BaseParser):
    name = "gmarket"

    def extract(self, page: Page, top_n: int) -> list[ProductRank]:
        cfg = {**CONFIG, "limit": max(top_n * 2, 60)}
        cards = evaluate_cards(page, cfg)
        rows: list[ProductRank] = []
        for i, c in enumerate(cards, start=1):
            list_price = to_int(c.get("listPrice"))
            sale_price = to_int(c.get("salePrice"))
            discount = to_percent(c.get("discount")) or compute_discount(list_price, sale_price)
            rows.append(
                ProductRank(
                    rank=i,
                    product_name=clean(c.get("name")),
                    list_price=list_price,
                    sale_price=sale_price,
                    discount_rate=discount,
                    sales_qty=None,                 # 지마켓: 미수집
                    review_count=to_int(c.get("reviewCount")),
                    rating=to_float(c.get("rating")),
                    is_sold_out=bool(c.get("isSoldOut")),
                    is_ad=bool(c.get("isAd")),
                    product_url=self.absolutize(c.get("href")),
                )
            )
        return rows
