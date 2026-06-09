"""파싱 결과 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class ProductRank:
    """순위 1~N 상품 한 건."""

    rank: int
    product_name: str | None = None
    product_id: str | None = None
    list_price: int | None = None        # 정가
    sale_price: int | None = None        # 판매가
    discount_rate: int | None = None     # 할인율(%)
    sales_qty: int | None = None         # 톡딜 주문수 / NS 구매수 (지마켓·GS샵 NULL)
    order_count: int | None = None       # 주문수
    review_count: int | None = None      # 리뷰수
    rating: float | None = None          # 평점
    is_sold_out: bool | None = None      # 품절 여부
    is_ad: bool | None = None            # 광고 여부
    product_url: str | None = None

    @classmethod
    def csv_header(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def csv_row(self) -> list[object]:
        out: list[object] = []
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, bool):
                v = int(v)
            out.append("" if v is None else v)
        return out
