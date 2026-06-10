"""카카오 톡딜(식품) 파서. sales_qty = 주문수(order_count)."""

from __future__ import annotations

from playwright.sync_api import Page

from ..models import ProductRank
from ..utils import clean, compute_discount, to_count, to_float, to_int, to_percent
from .base import BaseParser
from .extract_js import evaluate_cards

# 실제 store.kakao.com 톡딜 마크업(2026-06 확인) 기준 셀렉터.
CONFIG = {
    "cardSelectors": [
        "div.item_product",
        ".item_product",
        "app-view-product",
    ],
    "fields": {
        "name": [".name_product", ".tit_store"],
        "listPrice": [".txt_regular"],                      # 정가(판매가격)
        "salePrice": [".txt_price", ".txt_sale", ".group_price .emph_price"],  # 톡딜가
        "discount": [".txt_dc", ".num_rate"],               # 보통 미표기 → 가격으로 역산
        "orderCount": [".badge_other.on", ".ico_order"],         # '주문중 2.4만'
        "salesQty": [".badge_other.on", ".ico_order"],
        "reviewCount": [".txt_review"],
        "rating": [],                                        # 톡딜은 평점 대신 만족률(별도)
    },
    "imgSelectors": ["img.thumb_g", ".area_thumb img", "img"],
    "linkSelectors": ["a.link_thumb", "a.link_product", "a[href*='/products/']", "a"],
    "soldOut": {"selectors": [], "keywords": ["품절", "마감", "판매종료"]},
    "ad": {"selectors": [], "keywords": []},
    "limit": 80,
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
                    image_url=self.absolutize(c.get("img")),
                )
            )
        return rows
