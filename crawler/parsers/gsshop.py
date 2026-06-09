"""GS샵 NOW 베스트 파서. sales_qty 는 수집하지 않음(NULL)."""

from __future__ import annotations

from playwright.sync_api import Page

from ..models import ProductRank
from ..utils import clean, compute_discount, to_float, to_int, to_percent
from .base import BaseParser
from .extract_js import evaluate_cards

CONFIG = {
    "cardSelectors": [
        "ul.prd-list > li",
        ".prd-list li",
        "[class*='product'] li",
        "ul[class*='best'] li",
    ],
    "fields": {
        "name": [".prd-name", ".name", "[class*='prd-name']", "a[title]"],
        "listPrice": [".price-normal", "del", "s", "[class*='origin']"],
        "salePrice": [".price-sell .num", ".price-sell", ".price .num", "strong[class*='price']", "[class*='sell']"],
        "discount": [".rate", ".sale-rate", "[class*='discount']", "[class*='rate']"],
        "reviewCount": [".review-count", "[class*='review']"],
        "rating": [".star-rating", "[class*='rating']", "[class*='star']"],
    },
    "linkSelectors": ["a.prd-link", "a"],
    "soldOut": {"selectors": [".soldout", ".ico-soldout"], "keywords": ["품절", "일시품절"]},
    "ad": {"selectors": [".ad-mark"], "keywords": ["광고"]},
    "limit": 60,
}


class GsshopParser(BaseParser):
    name = "gsshop"

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
                    sales_qty=None,                 # GS샵: 미수집
                    review_count=to_int(c.get("reviewCount")),
                    rating=to_float(c.get("rating")),
                    is_sold_out=bool(c.get("isSoldOut")),
                    is_ad=bool(c.get("isAd")),
                    product_url=self.absolutize(c.get("href")),
                    image_url=self.absolutize(c.get("img")),
                )
            )
        return rows
